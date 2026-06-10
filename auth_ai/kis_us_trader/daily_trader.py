"""하루 1회 추세 기반 자동매매 (비동기) — Phase 1 12단계 흐름.

Phase 1 운영: 화이트리스트(현재 AAPL 1개)를 순회해 각 종목에 대해
universe → trend → LLM → safety_gate(8 검사) → Portfolio staged → 텔레그램 승인 →
주문 → apply_fill → audit log 한 사이클.

한 사이클의 12단계:
  1)  state 로드 + paused 검사
  2)  KIS 클라이언트 + Portfolio 초기화(자동 잔고 sync, 실패 시 sync_failed=True)
  3)  universe.list_all() 순회
  4)  종목별 일봉 조회 + compute_trend
  5)  LLM(get_advice) → buy/sell/hold + confidence
  6)  hold/low_confidence 조기 종료
  7)  qty/limit_price 계산 → Pick 생성
  8)  safety_gate.evaluate(pick, portfolio, state, CONSTANTS) → 8 검사
  9)  통과 시 portfolio.record_staged_buy(BUY만)
  10) ask_approval(텔레그램 단건 승인, 기존 그대로)
  11) client.order → rt_cd=0이면 portfolio.apply_fill(positions+state 원자 갱신)
  12) audit.log_cycle 한 줄 append

트리거 시각: 한국시간 07:30 (= 미국 EDT 18:30 / EST 17:30).
설계 의도: 추세/cap/배분은 코드가, 해석/판단은 LLM이. 사람이 텔레그램으로 최종 승인.
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
from kis.signals import classify_strength
from kis.state import is_paused, load_state, update_state
from llm_advisor import get_advice
from portfolio import Portfolio
from safety_gate import Pick, evaluate

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
    #   임계값 정의/근거는 kis/signals.py, 분포 분석은 tools/tune_thresholds.py 참고.
    if sma5 is None or sma20 is None or change_5d_pct is None:
        signal_strength = "weak"  # 데이터 부족 시 보수적
    else:
        spread_pct = abs(sma5 - sma20) / price * 100
        chg = abs(change_5d_pct)
        signal_strength = classify_strength(spread_pct, chg)

    return {
        "price": round(price, 2),
        "sma5": sma5,
        "sma20": sma20,
        "sma60": sma60,
        "above_sma20": (price > sma20) if sma20 else None,
        "sma5_above_sma20": (sma5 > sma20) if (sma5 and sma20) else None,
        "change_5d_pct": change_5d_pct,
        "signal_strength": signal_strength,
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


async def daily_cycle(bot):
    """한 사이클 실행. universe 종목 각각에 대해 12단계 흐름 통과.
    종목 1개 실패가 다음 종목을 막지 않도록 종목 루프 내 예외는 격리."""
    # 1) state 로드 + paused 검사
    state = load_state()
    if is_paused(state):
        msg = f"BOT PAUSED (paused_until={state.get('paused_until')}) → 사이클 skip"
        print("  " + msg)
        await bot.send_message(chat_id=CHAT_ID, text=f"⏸️ {msg}")
        log_cycle("cycle_skipped", {"reason": "paused"})
        return

    # 2) 클라이언트 + Portfolio (생성 시 자동 sync — 실패 시 sync_failed=True로 BUY 전면 차단)
    client = KISClient()
    pf = Portfolio(client)

    # 3) 유니버스 순회 (Phase 1: AAPL 1개)
    for sym_meta in universe.list_all():
        sym = sym_meta.symbol
        exch = sym_meta.exchange
        try:
            await _process_symbol(bot, client, pf, sym, exch)
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            print(f"  [{sym} 사이클 오류] {err}")
            try:
                update_state(lambda s: s.update({"consecutive_errors": s.get("consecutive_errors", 0) + 1}))
            except Exception:
                pass
            try:
                log_cycle("error", {"symbol": sym, "error": err})
            except Exception:
                pass
            try:
                await bot.send_message(chat_id=CHAT_ID, text=f"⚠️ {sym} 사이클 오류: {err}")
            except Exception:
                pass


async def _process_symbol(bot, client: KISClient, pf: Portfolio, sym: str, exch: str) -> None:
    """단일 종목에 대한 12단계 처리. 모든 결과는 audit log 1줄로 남는다."""
    # 4) 일봉 + 추세
    closes = client.get_daily_prices(sym, exch, days=60)
    if len(closes) < 20:
        msg = f"{sym} 일봉 부족({len(closes)}개). 휴장/운영시간 외일 수 있음."
        print("  " + msg)
        await bot.send_message(chat_id=CHAT_ID, text=f"ℹ️ {msg}")
        log_cycle("cycle_skipped", {"symbol": sym, "reason_skip": "insufficient_candles", "samples": len(closes)})
        return

    trend = compute_trend(closes)
    print(f"  [{sym}] price={trend['price']} sma20={trend['sma20']} sma5>sma20={trend['sma5_above_sma20']} signal={trend['signal_strength']}")

    # 5) LLM
    advice = get_advice(sym, trend)
    action, conf, reason = advice["action"], advice["confidence"], advice["reason"]
    print(f"  [{sym}] LLM: {action} (확신도 {conf}) - {reason}")

    base_payload = {
        "symbol": sym,
        "price": trend["price"],
        "sma20": trend["sma20"],
        "signal_strength": trend["signal_strength"],
        "action": action,
        "confidence": conf,
        "reason": reason,
    }
    trend_ctx = (
        f"📈 signal={trend['signal_strength']} | 현재 ${trend['price']} / SMA20 ${trend['sma20']} "
        f"/ SMA5>SMA20={trend['sma5_above_sma20']} / 5일 {trend['change_5d_pct']}%"
    )

    # 6) hold / low_confidence 조기 종료
    if action == "hold":
        await bot.send_message(chat_id=CHAT_ID, text=f"😴 {sym} 관망(hold)\n{trend_ctx}\n사유: {reason}")
        log_cycle("cycle_skipped", {**base_payload, "reason_skip": "hold"})
        return
    if conf < CONFIDENCE_THRESHOLD:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=f"{sym} 신호 {action}이나 확신도 {conf} < {CONFIDENCE_THRESHOLD} → 건너뜀.\n{trend_ctx}\n사유: {reason}")
        log_cycle("cycle_skipped", {**base_payload, "reason_skip": "low_confidence"})
        return

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
        await bot.send_message(
            chat_id=CHAT_ID,
            text=f"🛡️ {sym} 차단({result.check}): {result.reason}")
        log_cycle("cycle_skipped", {**base_payload, "qty": qty, "limit": limit,
                                    "reason_skip": result.reason, "check": result.check})
        return

    # 9) staged_buys 누적 (BUY만)
    if action == "buy":
        pf.record_staged_buy(sym, qty, limit)

    # 10) 텔레그램 단건 승인 (기존 ask_approval 흐름 유지)
    summary = (
        f"🤖 매매 승인 ({client.settings.env})\n\n"
        f"종목: {sym}\n동작: {'매수' if action=='buy' else '매도'} {qty}주\n"
        f"지정가: ${limit} (현재 ${price})\n"
        f"확신도: {conf}\n사유: {reason}\n"
        f"추세: SMA5>SMA20={trend['sma5_above_sma20']}, 5일 {trend['change_5d_pct']}%\n"
        f"현재 노출: ${pf.total_exposure_usd():.0f}"
    )
    decision = await ask_approval(bot, summary)
    if decision != "approve":
        print(f"  [{sym}] 승인 안 됨({decision}).")
        log_cycle("cycle_skipped", {**base_payload, "qty": qty, "limit": limit,
                                    "reason_skip": f"user_{decision}"})
        return

    # 11) Rank 2(승인-제출 분리): 07:30은 정규장 마감 후라 즉시주문이 거부됨(40580000 '장종료').
    #   정규장 중이면(드묾·수동 실행) 즉시 제출, 아니면 pending 으로 큐잉 → submission_loop 가
    #   다음 미국 개장(~22:35 KST)에 제출. 배경: docs/ORDER_TIMING_ISSUE.md
    order_payload = {**base_payload, "qty": qty, "limit": limit}
    if us_regular_session_open():
        await _place_and_confirm(bot, client, pf, sym, action, qty, limit, exch, order_payload)
    else:
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
    pending = list(load_state().get("pending_orders") or [])
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