"""하루 1회 추세 기반 자동매매 (비동기) — Phase 2 다종목 흐름.

화이트리스트(AAPL + 반도체 10종목)를 한 사이클에 묶어 처리한다:

한 사이클:
  1)  state 로드 + paused 검사
  2)  KIS 클라이언트 + Portfolio 초기화(자동 잔고 sync, 실패 시 sync_failed=True)
  3)  1차 패스: 전 종목 일봉 + compute_trend 수집(above_sma20 동시 — breadth 용). 종목 예외 격리.
  4)  sector.compute_macro_bias(SMH 1콜 + breadth) → max_buys_for_bias 로 그날 신규 매수 상한 N
  5)  researcher.decide_parallel(종목당 1콜 비동기 병렬 + macro_bias 사실블록 주입) → {symbol: advice}
  6)  select_picks: conf≥CONFIDENCE_THRESHOLD BUY 상위 N(risk_off→0) + SELL(N 무관) — 코드가 픽 결정
  7)  픽별 _process_pick: qty/limit → safety_gate(8 검사) → staged → 텔레그램 단건 승인 →
      Rank 2(정규장 중이면 즉시 제출, 아니면 pending 큐잉 → submission_loop 가 개장 직후 제출)
  *)  모든 단계 결과는 audit.log_cycle 한 줄로 박제. flagged(외부 ticker 환각)는 별도 로그.

트리거 시각: 한국시간 07:30 (= 미국 EDT 18:30 / EST 17:30, 둘 다 애프터마켓 → Rank 2 승인-제출 분리).
설계 의도: 유니버스/추세/macro_bias/N/cap/배분은 코드가, 방향 해석만 LLM이. 사람이 텔레그램으로 최종 승인.
⚠️ 모의투자 기본. LLM 제안은 투자 추천이 아니며 사람 승인을 거칩니다.

실행: python daily_trader.py
"""
import asyncio
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from kis import universe
from kis.audit import log_cycle
from kis.client import KISClient, parse_balance_positions
from kis.signals import classify_strength, compute_vol_factor
from kis.state import is_paused, load_state, update_state
from portfolio import Portfolio
from researcher import decide_parallel
from safety_gate import Pick, evaluate
from sector import compute_macro_bias, max_buys_for_bias

load_dotenv()

# ===== 운영 파라미터 =====
CONFIDENCE_THRESHOLD = 80      # LLM 확신도 임계
APPROVAL_TIMEOUT = 1800        # 텔레그램 승인 대기(초). 무응답 시 자동 거절(30분)
RUN_HOUR = 7                   # 매일 실행 시각(한국시간 24h). 미국 정규장 마감 직후.
RUN_MINUTE = 30
# Rank 2(승인-제출 분리): 07:30 승인 → 미국 정규장 개장 직후 제출. 09:35 ET = ~22:35 KST(DST)/23:35(표준).
SUBMIT_HOUR_ET = 9
SUBMIT_MINUTE_ET = 35
PENDING_TTL_HOURS = 18         # 승인 후 이 시간 내 미제출 시 만료(주말/장애로 stale된 승인 폐기)

# signal_strength 임계값/분류 로직은 kis/signals.py (단일 진실 소스, tune_thresholds 와 공유).

# safety_gate가 사용하는 운영 상수. DEFAULT_CONSTANTS와 동일하지만 명시적으로 한 번 더 보임.
CONSTANTS = {
    "MAX_POSITION_PER_SYMBOL_USD": 2000,
    "MAX_TOTAL_EXPOSURE_USD":      10000,
    "MAX_SECTOR_EXPOSURE_PCT":     40,
    "MAX_NEW_BUYS_PER_DAY":        3,
    "REBUY_COOLDOWN_DAYS":         3,
    "DAILY_TOTAL_BUDGET_USD":      600,
    "DAILY_LOSS_LIMIT_USD":        -500,
    "MAX_CONSECUTIVE_ERRORS":      3,
}

# 종목별 매수 예산(allocate_budget으로 비례 분배 전 1종목 가정값). Phase 1 단일 종목 운영용.
PER_PICK_BUDGET_USD = 200.0

CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

ET = ZoneInfo("America/New_York")  # 미국 정규장 시간 판정용(DST 자동 처리)


def compute_trend(closes: list[float]) -> dict:
    """일봉 종가 리스트로 추세 지표를 계산해 dict로 반환."""
    n = len(closes)
    price = closes[-1]

    def sma(k):
        return round(sum(closes[-k:]) / k, 2) if n >= k else None

    sma5, sma20, sma60 = sma(5), sma(20), sma(60)
    change_5d_pct = round((price / closes[-6] - 1) * 100, 2) if n >= 6 else None

    # 추세 강도 라벨 (kis.signals.classify_strength — daily_trader/tune_thresholds 공유).
    #   ⚠️ '추세 강도/변동성' 라벨이지 '방향' 신호가 아니다. 방향(매수/매도)은 LLM 이
    #      price·sma5·sma20·change_5d_pct 데이터로만 판단한다(llm_advisor SYSTEM_PROMPT 참고).
    #   P2(2026-06-10): score 를 종목 자체 trailing 20d vol 로 정규화 → 종목 가로 weak 균일.
    #   임계값 정의/근거는 kis/signals.py, 분포 분석은 tools/tune_thresholds.py 참고.
    vol_factor = compute_vol_factor(closes)
    if sma5 is None or sma20 is None or change_5d_pct is None:
        signal_strength = "weak"  # 데이터 부족 시 보수적
    else:
        spread_pct = abs(sma5 - sma20) / price * 100
        chg = abs(change_5d_pct)
        signal_strength = classify_strength(spread_pct, chg, vol_factor)

    return {
        "price": round(price, 2),
        "sma5": sma5,
        "sma20": sma20,
        "sma60": sma60,
        "above_sma20": (price > sma20) if sma20 else None,
        "sma5_above_sma20": (sma5 > sma20) if (sma5 and sma20) else None,
        "change_5d_pct": change_5d_pct,
        "signal_strength": signal_strength,
        "vol_factor": round(vol_factor, 3),
        "samples": n,
    }


async def ask_approval(bot, summary: str) -> str:
    fut: asyncio.Future = asyncio.get_event_loop().create_future()
    bot.application_decision = fut
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ 승인", callback_data="approve"),
        InlineKeyboardButton("❌ 거절", callback_data="reject"),
    ]])
    await bot.send_message(chat_id=CHAT_ID, text=summary, reply_markup=keyboard)
    try:
        return await asyncio.wait_for(fut, timeout=APPROVAL_TIMEOUT)
    except asyncio.TimeoutError:
        await bot.send_message(chat_id=CHAT_ID, text="⏱️ 무응답 → 자동 거절")
        return "timeout"


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass
    choice = query.data
    label = "✅ 승인됨" if choice == "approve" else "❌ 거절됨"
    await query.edit_message_text(f"{query.message.text}\n\n— {label}")
    fut = getattr(context.bot, "application_decision", None)
    if fut and not fut.done():
        fut.set_result(choice)


def select_picks(decisions: dict[str, dict], max_buys: int,
                 threshold: int = CONFIDENCE_THRESHOLD) -> tuple[list[str], list[str]]:
    """LLM 결정 dict({symbol: advice}) → (선정 BUY 종목 리스트, SELL 종목 리스트). 순수 함수.

    - BUY: action=='buy' AND confidence>=threshold 인 종목을 confidence 내림차순 정렬해
      상위 max_buys 개만 선정(macro_bias 기반 N 제한). max_buys<=0 이면 BUY 전면 컷(risk_off/unknown).
    - SELL: action=='sell' AND confidence>=threshold (N 제한 없음 — 청산은 국면과 무관히 허용).
    - 그 외(hold/저신뢰/flagged 로 hold 강등된 것)는 제외.
    동률 confidence 는 symbol 알파벳 순으로 결정적 정렬(재현성).
    """
    buys, sells = [], []
    for sym, adv in decisions.items():
        action = adv.get("action")
        conf = adv.get("confidence", 0)
        if action == "buy" and conf >= threshold:
            buys.append((sym, conf))
        elif action == "sell" and conf >= threshold:
            sells.append(sym)
    buys.sort(key=lambda x: (-x[1], x[0]))
    selected_buys = [s for s, _ in buys[:max(0, max_buys)]]
    return selected_buys, sorted(sells)


def _has_unexpired_pending(state: dict, sym: str, side: str, now_et: datetime) -> bool:
    """state.pending_orders 에 같은 (symbol, side) 의 만료 안 된 승인이 이미 있는지.

    승인-제출 분리(Rank 2)에서 미제출 pending 이 남아있는데(주말/장애) 다음 사이클이 같은 종목을
    다시 큐잉하면 중복 승인·제출 위험(precommit review #6). 큐잉 전 이 검사로 중복을 막는다.
    """
    for p in (state.get("pending_orders") or []):
        if p.get("symbol") == sym and p.get("side") == side:
            try:
                age_h = (now_et - datetime.fromisoformat(p.get("approved_at", ""))).total_seconds() / 3600
            except (ValueError, TypeError):
                age_h = 0.0
            if age_h < PENDING_TTL_HOURS:
                return True
    return False


def _maybe_autopause(state: dict) -> str | None:
    """consecutive_errors 가 임계 도달이면 24h paused_until 을 무장하고 그 ISO 를 반환(아니면 None).

    문서(DESIGN §6 안전장치)의 dead-man 자동 정지가 그동안 카운터만 올리고 강제는 안 됐다
    (precommit review #7/#15). 이 함수가 실제 정지를 건다."""
    if state.get("consecutive_errors", 0) >= CONSTANTS["MAX_CONSECUTIVE_ERRORS"]:
        until = (datetime.now(ET) + timedelta(hours=24)).isoformat(timespec="seconds")
        update_state(lambda s: s.update({"paused_until": until}))
        return until
    return None


async def daily_cycle(bot):
    """한 사이클: 전 종목 추세 수집 → macro_bias(N 결정) → decide_parallel → N 제한 픽 →
    종목별 safety_gate → 승인 → Rank 2 제출. 종목 단위 예외는 격리한다."""
    # 1) state 로드 + paused 검사
    state = load_state()
    if is_paused(state):
        msg = f"BOT PAUSED (paused_until={state.get('paused_until')}) → 사이클 skip"
        print("  " + msg)
        await bot.send_message(chat_id=CHAT_ID, text=f"⏸️ {msg}")
        log_cycle("cycle_skipped", {"reason": "paused"})
        return

    # 1b) dead-man 자동 정지: 연속 오류 임계 도달 시 24h pause 무장 후 종료.
    until = _maybe_autopause(state)
    if until:
        msg = (f"연속 오류 {state.get('consecutive_errors')}회 ≥ {CONSTANTS['MAX_CONSECUTIVE_ERRORS']} "
               f"→ 24h 자동 정지(paused_until={until})")
        print("  " + msg)
        await bot.send_message(chat_id=CHAT_ID, text=f"🛑 {msg}")
        log_cycle("auto_paused", {"reason": "consecutive_errors",
                                  "consecutive_errors": state.get("consecutive_errors"), "paused_until": until})
        return

    # 1c) 미국 비거래일(ET 주말) 스킵: 07:30 KST 일·월 = ET 토·일 → 직전 세션 stale + pending 중복 방지.
    if datetime.now(ET).weekday() >= 5:
        print("  ET 주말(미국 비거래일) → 사이클 skip")
        log_cycle("cycle_skipped", {"reason": "et_weekend"})
        return

    # 2) 클라이언트 + Portfolio (생성 시 자동 sync — 실패 시 sync_failed=True로 BUY 전면 차단)
    client = KISClient()
    pf = Portfolio(client)

    # 3) 1차 패스: 전 종목 일봉 + 추세 수집(종목별 예외 격리). breadth 용 above_sma20 동시 수집.
    trends: dict[str, dict] = {}          # {symbol: trend}
    exch_of: dict[str, str] = {}          # {symbol: exchange}
    above_flags: list[bool] = []
    for sym_meta in universe.list_all():
        sym, exch = sym_meta.symbol, sym_meta.exchange
        try:
            closes = client.get_daily_prices(sym, exch, days=60)
            if len(closes) < 20:
                print(f"  [{sym}] 일봉 부족({len(closes)}) → skip")
                log_cycle("cycle_skipped", {"symbol": sym, "reason_skip": "insufficient_candles",
                                            "samples": len(closes)})
                continue
            trend = compute_trend(closes)
            trends[sym] = trend
            exch_of[sym] = exch
            # breadth 는 '반도체 섹터' 국면용 → 반도체 멤버만 집계(AAPL=megacap_tech 제외, review #9).
            if sym_meta.sector == "semiconductor" and trend.get("above_sma20") is not None:
                above_flags.append(bool(trend["above_sma20"]))
            print(f"  [{sym}] price={trend['price']} signal={trend['signal_strength']} "
                  f"vol_factor={trend.get('vol_factor', 1.0)} above20={trend.get('above_sma20')}")
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            print(f"  [{sym} 추세 수집 오류] {err}")
            log_cycle("error", {"symbol": sym, "error": err, "stage": "trend"})

    if not trends:
        await bot.send_message(chat_id=CHAT_ID, text="ℹ️ 추세 수집 가능 종목 0개(휴장/운영시간 외?) → 사이클 종료.")
        log_cycle("cycle_skipped", {"reason": "no_trends"})
        return

    # 4) macro_bias(SMH 1콜 + breadth) → 그날 신규 매수 상한 N.
    macro = compute_macro_bias(client, member_above_sma20=above_flags)
    n_buys = max_buys_for_bias(macro["bias"])
    macro_line = (
        f"🧭 매크로 bias={macro['bias']} → 신규매수 상한 N={n_buys}\n"
        f"SMH ${macro.get('smh_price')} (SMA20 {macro.get('smh_sma20')}/SMA50 {macro.get('smh_sma50')}) "
        f"| breadth {macro.get('breadth_pct')}%"
    )
    print("  " + macro_line.replace("\n", " "))

    # 5) 종목별 LLM 결정 비동기 병렬(종목당 1콜 + macro_bias 사실 블록 주입).
    decisions = await decide_parallel(trends, macro)
    for sym, adv in decisions.items():
        flagged = adv.get("flagged") or []
        if flagged:
            log_cycle("reason_foreign_ticker", {"symbol": sym, "flagged": flagged, "reason": adv.get("reason", "")})
            print(f"  [{sym}] ⚠️ reason 외부 ticker {flagged} → hold 강등")

    # 6) 코드가 픽 결정(LLM 우선순위 사용 금지): conf>=threshold BUY 상위 N + SELL.
    selected_buys, sells = select_picks(decisions, n_buys, CONFIDENCE_THRESHOLD)
    summary_line = (
        f"{macro_line}\n선정: 매수 {selected_buys or '없음'} / 매도 {sells or '없음'} "
        f"(후보 {len(trends)}종목, 임계 conf≥{CONFIDENCE_THRESHOLD})"
    )
    await bot.send_message(chat_id=CHAT_ID, text=f"📋 점검 요약\n{summary_line}")
    log_cycle("cycle_summary", {"bias": macro["bias"], "n_buys": n_buys,
                                "selected_buys": selected_buys, "sells": sells,
                                "candidates": len(trends)})

    # 7) 선정 픽 처리(매도 먼저 — 노출 축소 우선, 그다음 매수). 픽 단위 예외 격리.
    for sym in sells + selected_buys:
        action = "sell" if sym in sells else "buy"
        try:
            await _process_pick(bot, client, pf, sym, exch_of[sym], trends[sym],
                                 action, decisions[sym]["confidence"], decisions[sym].get("reason", ""))
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            print(f"  [{sym} 픽 처리 오류] {err}")
            try:
                update_state(lambda s: s.update({"consecutive_errors": s.get("consecutive_errors", 0) + 1}))
            except Exception:
                pass
            try:
                log_cycle("error", {"symbol": sym, "error": err, "stage": "pick"})
            except Exception:
                pass
            try:
                await bot.send_message(chat_id=CHAT_ID, text=f"⚠️ {sym} 픽 처리 오류: {err}")
            except Exception:
                pass


async def _process_pick(bot, client: KISClient, pf: Portfolio, sym: str, exch: str,
                        trend: dict, action: str, conf: int, reason: str) -> None:
    """선정된 단일 픽 처리(qty/limit → safety_gate → 승인 → Rank 2 제출/큐잉)."""
    base_payload = {
        "symbol": sym, "price": trend["price"], "sma20": trend["sma20"],
        "signal_strength": trend["signal_strength"], "vol_factor": trend.get("vol_factor", 1.0),
        "action": action, "confidence": conf, "reason": reason,
    }

    # 7) qty/limit 계산 → Pick
    price = trend["price"]
    if action == "buy":
        qty = int(PER_PICK_BUDGET_USD // price)
        if qty < 1:
            await bot.send_message(chat_id=CHAT_ID, text=f"{sym} 예산 ${PER_PICK_BUDGET_USD}로 1주도 못 삼(주가 ${price}).")
            log_cycle("cycle_skipped", {**base_payload, "reason_skip": "budget_too_small"})
            return
        limit = round(price * 1.005, 2)
    else:  # sell
        held = pf.positions.get(sym, {}).get("qty", 0)
        if held <= 0:
            await bot.send_message(chat_id=CHAT_ID, text=f"{sym} 보유 수량 없음 → 매도 건너뜀.")
            log_cycle("cycle_skipped", {**base_payload, "reason_skip": "no_position"})
            return
        qty = held
        limit = round(price * 0.995, 2)
    pick = Pick(symbol=sym, side=action, qty=qty, limit_price=limit, confidence=conf, reason=reason)

    # 8) safety_gate — 8개 검사
    result = evaluate(pick, pf, pf.state, CONSTANTS)
    if not result.ok:
        await bot.send_message(chat_id=CHAT_ID, text=f"🛡️ {sym} 차단({result.check}): {result.reason}")
        log_cycle("cycle_skipped", {**base_payload, "qty": qty, "limit": limit,
                                    "reason_skip": result.reason, "check": result.check})
        return

    # 9) staged_buys 누적 (BUY만 — 같은 사이클 누적이 cap 검사에 합산됨)
    if action == "buy":
        pf.record_staged_buy(sym, qty, limit)

    # 10) 텔레그램 단건 승인
    summary = (
        f"🤖 매매 승인 ({client.settings.env})\n\n"
        f"종목: {sym}\n동작: {'매수' if action=='buy' else '매도'} {qty}주\n"
        f"지정가: ${limit} (현재 ${price})\n"
        f"확신도: {conf}\n사유: {reason}\n"
        f"추세: signal={trend['signal_strength']}, SMA5>SMA20={trend['sma5_above_sma20']}, 5일 {trend['change_5d_pct']}%\n"
        f"현재 노출: ${pf.total_exposure_usd():.0f}"
    )
    decision = await ask_approval(bot, summary)
    if decision != "approve":
        print(f"  [{sym}] 승인 안 됨({decision}).")
        # 비승인 BUY 는 staged 해제 — 안 하면 같은 사이클 뒤 픽들의 cap/예산 검사를 phantom 오염(review #1).
        if action == "buy":
            pf.unstage_buy(sym)
        log_cycle("cycle_skipped", {**base_payload, "qty": qty, "limit": limit,
                                    "reason_skip": f"user_{decision}"})
        return

    # 11) Rank 2(승인-제출 분리): 07:30은 정규장 마감 후라 즉시주문이 거부됨(40580000 '장종료').
    #   정규장 중이면(수동 실행) 즉시 제출, 아니면 pending 큐잉 → submission_loop 가 개장 직후 제출.
    order_payload = {**base_payload, "qty": qty, "limit": limit}
    if us_regular_session_open():
        await _place_and_confirm(bot, client, pf, sym, action, qty, limit, exch, order_payload)
    else:
        # 중복 큐잉 방지: 같은 (종목, side) 만료 전 pending 이 이미 있으면 재큐잉 skip(review #6).
        if _has_unexpired_pending(load_state(), sym, action, datetime.now(ET)):
            print(f"  [{sym}] 이미 대기 중 pending → 재큐잉 skip")
            if action == "buy":
                pf.unstage_buy(sym)
            await bot.send_message(chat_id=CHAT_ID,
                                   text=f"↩️ {sym} {'매수' if action=='buy' else '매도'} 이미 대기 중 → 중복 큐잉 건너뜀.")
            log_cycle("order_dedup_skipped", {**order_payload})
            return
        po = {"symbol": sym, "side": action, "qty": qty, "limit": limit, "exchange": exch,
              "confidence": conf, "reason": reason,
              "approved_at": datetime.now(ET).isoformat(timespec="seconds")}
        update_state(lambda s: s.setdefault("pending_orders", []).append(po))
        await bot.send_message(
            chat_id=CHAT_ID,
            text=(f"✅ {sym} {'매수' if action=='buy' else '매도'} {qty}주 @ ${limit} 승인 → "
                  f"다음 미국 개장(~22:35 KST)에 제출 예정."))
        log_cycle("order_queued", order_payload)


def us_regular_session_open(now_et: datetime | None = None) -> bool:
    """미국 정규장(평일 09:30~16:00 ET) 개장 여부. ZoneInfo로 DST 자동 처리.

    ⚠️ 미국 공휴일/반장일은 보지 않는다(현 07:30 KST 스케줄은 항상 정규장 밖이라 무관).
    정규장 외에는 KIS가 주문을 거부(40580000 '장종료')하므로 주문 보류 판단에 쓴다.
    """
    now = now_et or datetime.now(ET)
    if now.weekday() >= 5:  # 토(5)/일(6)
        return False
    open_t = now.replace(hour=9, minute=30, second=0, microsecond=0)
    close_t = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return open_t <= now < close_t


def _broker_held_qty(client: KISClient, exch: str, sym: str) -> int | None:
    """KIS 잔고에서 종목 보유수량 조회. 실패 시 None(체결 확인 불가)."""
    try:
        raw = client.get_balance(exch)
    except Exception:
        return None
    if not isinstance(raw, dict) or raw.get("rt_cd") != "0":
        return None
    return int(parse_balance_positions(raw).get(sym, {}).get("qty", 0))


async def _place_and_confirm(bot, client: KISClient, pf: Portfolio, sym: str, side: str,
                             qty: int, limit: float, exch: str, payload: dict) -> None:
    """주문 전송 + 잔고 재조회로 실제 체결 확인 후에만 apply_fill (phantom-fill 방지).
    ⚠️ 정규장 중에만 호출할 것 — 정규장 외엔 KIS가 거부(40580000)."""
    pre_qty = int(pf.positions.get(sym, {}).get("qty", 0))
    res = client.order(sym, side, qty, limit, exch)
    rt = res.get("rt_cd")
    op = {**payload, "rt_cd": rt, "msg1": res.get("msg1", ""),
          "odno": (res.get("output") or {}).get("ODNO")}
    if rt != "0":
        if side == "buy":
            pf.unstage_buy(sym)  # 주문 거부 → staged 해제(phantom cap 오염 방지, review #1)
        update_state(lambda s: s.update({"consecutive_errors": s.get("consecutive_errors", 0) + 1}))
        log_cycle("cycle_error", op)
        return
    # rt_cd=="0"은 '접수'일 뿐 '체결'이 아니다 → 잔고 재조회로 실제 체결 확인 후에만 반영.
    await asyncio.sleep(3)  # 체결이 잔고에 반영될 시간
    post_qty = _broker_held_qty(client, exch, sym)
    if side == "buy":
        confirmed = post_qty is not None and post_qty >= pre_qty + qty
    else:
        confirmed = post_qty is not None and post_qty <= pre_qty - qty
    if confirmed:
        pf.apply_fill(sym, qty, side, limit)
        await bot.send_message(
            chat_id=CHAT_ID,
            text=f"📊 {sym} {'매수' if side=='buy' else '매도'} 체결 — 보유 {pf.positions.get(sym, {}).get('qty', 0)}주")
        log_cycle("cycle_complete", op)
    else:
        # 접수(rt_cd=0)됐으나 미체결 = 브로커에 살아있는 주문 → staged 를 '유지'한다(이번 사이클 남은
        #   픽 cap 에 실노출로 합산하는 게 보수적·정확). 체결 시에만 apply_fill 이 staged→positions 로 옮긴다.
        #   비승인/주문거부와 달리 여기서 unstage 하면 live 주문이 cap 에서 사라져 덜 안전.
        #   ⚠️ 잔여 갭(review #8): submit_open_orders 제출 루프는 staged 미사용이라 이 미체결 주문이 일일
        #   cap(state)에 안 잡힘 → open_orders 예약 회계는 후속 과제(CLAUDE.md 다음 할 일 참조).
        await bot.send_message(
            chat_id=CHAT_ID,
            text=f"🟡 {sym} 주문 접수(rt_cd=0)됐으나 체결 미확인(잔고 변화 없음) → 보유 반영 보류. ODNO={op['odno']}")
        log_cycle("cycle_accepted_unfilled", {**op, "pre_qty": pre_qty, "post_qty": post_qty})


def seconds_until_next_run() -> float:
    now = datetime.now()
    target = now.replace(hour=RUN_HOUR, minute=RUN_MINUTE, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def seconds_until_submit_window(now_et: datetime | None = None) -> float:
    """다음 제출 시각(평일 09:35 ET = 미국 개장 5분 후)까지 초. ZoneInfo로 DST 자동 처리."""
    now = now_et or datetime.now(ET)
    target = now.replace(hour=SUBMIT_HOUR_ET, minute=SUBMIT_MINUTE_ET, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    while target.weekday() >= 5:  # 주말 건너뜀
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def _submit_one(bot, client: KISClient, pf: Portfolio, po: dict) -> None:
    """pending 1건: 제출 직전 재검증(보유/safety_gate) 후 _place_and_confirm 으로 제출."""
    sym = po["symbol"]
    side = po["side"]
    qty = po["qty"]
    limit = po["limit"]
    exch = po.get("exchange", "NASD")
    conf = po.get("confidence", 0)
    reason = po.get("reason", "")
    if side == "sell" and pf.positions.get(sym, {}).get("qty", 0) <= 0:
        await bot.send_message(chat_id=CHAT_ID, text=f"{sym} 보유 없음 → 매도 제출 취소.")
        log_cycle("pending_skipped", {**po, "reason_skip": "no_position"})
        return
    pick = Pick(symbol=sym, side=side, qty=qty, limit_price=limit, confidence=conf, reason=reason)
    result = evaluate(pick, pf, pf.state, CONSTANTS)
    if not result.ok:
        await bot.send_message(chat_id=CHAT_ID, text=f"🛡️ {sym} 제출 직전 차단({result.check}): {result.reason}")
        log_cycle("pending_blocked", {**po, "check": result.check, "reason_skip": result.reason})
        return
    payload = {"symbol": sym, "action": side, "qty": qty, "limit": limit,
               "confidence": conf, "reason": reason}
    await _place_and_confirm(bot, client, pf, sym, side, qty, limit, exch, payload)


async def submit_open_orders(bot) -> None:
    """미국 개장 직후 호출 — pending_orders 를 검증·제출(Rank 2). 1회성: 처리 후 큐 비움."""
    st = load_state()
    if is_paused(st):
        print("  [submit] BOT PAUSED → 제출 보류")
        return
    pending = list(st.get("pending_orders") or [])
    if not pending:
        return
    if not us_regular_session_open():
        print("  [submit] 정규장 외 — 제출 보류")
        return
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] pending {len(pending)}건 제출 시작")
    client = KISClient()
    pf = Portfolio(client)
    now_et = datetime.now(ET)
    for po in pending:
        try:
            approved = datetime.fromisoformat(po.get("approved_at", ""))
            if (now_et - approved).total_seconds() > PENDING_TTL_HOURS * 3600:
                await bot.send_message(
                    chat_id=CHAT_ID,
                    text=f"⏳ {po.get('symbol')} 예약 만료(승인 {po.get('approved_at')}) → 제출 안 함.")
                log_cycle("pending_expired", po)
                continue
            await _submit_one(bot, client, pf, po)
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            print(f"  [submit {po.get('symbol')} 오류] {err}")
            try:
                update_state(lambda s: s.update({"consecutive_errors": s.get("consecutive_errors", 0) + 1}))
            except Exception:
                pass
            try:
                await bot.send_message(chat_id=CHAT_ID, text=f"⚠️ {po.get('symbol')} 제출 오류: {err}")
            except Exception:
                pass
    update_state(lambda s: s.update({"pending_orders": []}))  # 1회성 처리 완료 → 비움


async def submission_loop(bot) -> None:
    """미국 개장 직후 pending 제출 스케줄 루프 (main_loop 와 동시 실행)."""
    while True:
        wait = seconds_until_submit_window()
        print(f"[submit] 다음 제출 창까지 {wait/3600:.1f}시간 대기...")
        await asyncio.sleep(wait)
        try:
            await submit_open_orders(bot)
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            print(f"  [submit 전체 오류] {err}")
            try:
                await bot.send_message(chat_id=CHAT_ID, text=f"⚠️ 제출 루프 오류: {err}")
            except Exception:
                pass
        await asyncio.sleep(60)  # 같은 분에 중복 실행 방지


async def main_loop(app):
    bot = app.bot
    await bot.send_message(
        chat_id=CHAT_ID,
        text=(f"🚀 하루1회 자동매매 시작 (모의). 매일 {RUN_HOUR:02d}:{RUN_MINUTE:02d} KST 점검"
              f"(미국장 마감 후) → 승인 시 다음 개장(~22:35 KST)에 제출."))
    print("=== 하루 1회 자동매매 시작 ===")
    while True:
        wait = seconds_until_next_run()
        print(f"다음 실행까지 {wait/3600:.1f}시간 대기...")
        await asyncio.sleep(wait)
        try:
            print(f"[{datetime.now():%Y-%m-%d %H:%M}] 일일 사이클 시작")
            await daily_cycle(bot)
        except Exception as e:
            # daily_cycle 자체가 종목별 try/except로 격리하므로 여기 도달은 드물다
            # (state/Portfolio 초기화 단계 오류 등 cycle 전체가 깨지는 경우)
            err = f"{type(e).__name__}: {e}"
            print(f"  [전체 오류] {err}")
            try:
                update_state(lambda s: s.update({"consecutive_errors": s.get("consecutive_errors", 0) + 1}))
            except Exception:
                pass
            try:
                log_cycle("error", {"scope": "cycle_global", "error": err})
            except Exception:
                pass
            try:
                await bot.send_message(chat_id=CHAT_ID, text=f"⚠️ 오류: {err}")
            except Exception:
                pass
        await asyncio.sleep(60)  # 같은 분에 중복 실행 방지


def main():
    if not TOKEN or not CHAT_ID:
        raise SystemExit(".env 에 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 가 필요합니다.")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CallbackQueryHandler(on_button))

    async def runner():
        await app.initialize()
        await app.start()
        await app.updater.start_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
        try:
            await asyncio.gather(main_loop(app), submission_loop(app.bot))
        finally:
            await app.updater.stop()
            await app.stop()
            await app.shutdown()

    asyncio.run(runner())


if __name__ == "__main__":
    main()