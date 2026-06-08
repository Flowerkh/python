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

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from kis import universe
from kis.audit import log_cycle
from kis.client import KISClient
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


def compute_trend(closes: list[float]) -> dict:
    """일봉 종가 리스트로 추세 지표를 계산해 dict로 반환."""
    n = len(closes)
    price = closes[-1]

    def sma(k):
        return round(sum(closes[-k:]) / k, 2) if n >= k else None

    sma5, sma20, sma60 = sma(5), sma(20), sma(60)
    change_5d_pct = round((price / closes[-6] - 1) * 100, 2) if n >= 6 else None

    # 추세 강도 라벨 (코드 기준 결정적 산출 — LLM 의 모호한 자율 판단을 줄임)
    #   weak     : SMA5/20 스프레드 < 0.3% 이고 5일 변동 < 1% → 사실상 횡보
    #   strong   : 스프레드 >= 1.0% 이고 5일 변동 >= 3% → 명확한 추세
    #   moderate : 그 사이
    # 임계값은 출발점일 뿐 운영 데이터 보고 조정 필요.
    if sma5 is None or sma20 is None or change_5d_pct is None:
        signal_strength = "weak"  # 데이터 부족 시 보수적
    else:
        spread_pct = abs(sma5 - sma20) / price * 100
        chg = abs(change_5d_pct)
        if spread_pct < 0.3 and chg < 1.0:
            signal_strength = "weak"
        elif spread_pct >= 1.0 and chg >= 3.0:
            signal_strength = "strong"
        else:
            signal_strength = "moderate"

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

    # 6) hold / low_confidence 조기 종료
    if action == "hold":
        await bot.send_message(chat_id=CHAT_ID, text=f"😴 {sym} 관망(hold). 사유: {reason}")
        log_cycle("cycle_skipped", {**base_payload, "reason_skip": "hold"})
        return
    if conf < CONFIDENCE_THRESHOLD:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=f"{sym} 신호 {action}이나 확신도 {conf} < {CONFIDENCE_THRESHOLD} → 건너뜀.")
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

    # 11) 주문 실행 (텔레그램 ✅/⚠️ 알림은 KISClient.order가 자동 발송)
    res = client.order(sym, action, qty, limit, exch)
    rt = res.get("rt_cd")
    order_payload = {
        **base_payload,
        "qty": qty,
        "limit": limit,
        "rt_cd": rt,
        "msg1": res.get("msg1", ""),
        "odno": (res.get("output") or {}).get("ODNO"),
    }

    # 12) apply_fill (state 갱신 단일 지점) 또는 consecutive_errors 누적
    if rt == "0":
        pf.apply_fill(sym, qty, action, limit)
        await bot.send_message(
            chat_id=CHAT_ID,
            text=f"📊 {sym} {'매수' if action=='buy' else '매도'} 체결 — 보유 {pf.positions.get(sym, {}).get('qty', 0)}주")
        log_cycle("cycle_complete", order_payload)
    else:
        update_state(lambda s: s.update({"consecutive_errors": s.get("consecutive_errors", 0) + 1}))
        log_cycle("cycle_error", order_payload)


def seconds_until_next_run() -> float:
    now = datetime.now()
    target = now.replace(hour=RUN_HOUR, minute=RUN_MINUTE, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def main_loop(app):
    bot = app.bot
    await bot.send_message(
        chat_id=CHAT_ID,
        text=f"🚀 하루1회 자동매매 시작 (모의). 매일 {RUN_HOUR:02d}:{RUN_MINUTE:02d} KST 점검 (미국장 마감 후).")
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
            await main_loop(app)
        finally:
            await app.updater.stop()
            await app.stop()
            await app.shutdown()

    asyncio.run(runner())


if __name__ == "__main__":
    main()