"""하루 1회 추세 기반 자동매매 (비동기).

Phase 0 운영: 단일 종목(AAPL), 일봉 확정 후 한 번 점검.

한 사이클:
  0) state 로드 → paused 검사 (paused면 즉시 skip + audit 기록)
  1) KIS 일봉 조회 → 코드로 추세 지표 계산
  2) 계산된 '사실'을 LLM에 주고 buy/sell/hold + 확신도 수신
  3) 안전장치(확신도 임계값, 금액 한도) 통과 시 텔레그램 승인 요청
  4) 승인되면 금액 기준($BUDGET)으로 수량 계산 후 모의주문
  5) audit.log_cycle()로 한 줄 append (hash chain)

트리거 시각: 한국시간 07:30 (= 미국 EDT 18:30 / EST 17:30).
이유: 미국 정규장이 끝나고 그날 일봉이 확정된 직후 발화해야 안정된 추세로 의사결정.

설계 의도: 추세는 코드가 정확히 계산, 해석/판단은 LLM이.
⚠️ 모의투자 기본. LLM 제안은 투자 추천이 아니며 사람 승인을 거칩니다.

실행: python daily_trader.py
"""
import asyncio
import os
from datetime import datetime, timedelta

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from kis.audit import log_cycle
from kis.client import KISClient
from kis.state import is_paused, load_state, update_state
from llm_advisor import get_advice

load_dotenv()

# ===== 운영 파라미터 =====
SYMBOL = "AAPL"
EXCHANGE = "NASD"
DAILY_BUDGET_USD = 200.0       # 하루 매수 예산(금액 기준)
CONFIDENCE_THRESHOLD = 80      # 이 이상일 때만 승인 요청
MAX_POSITION_USD = 2000.0      # 최대 보유 평가금액 한도(안전장치)
APPROVAL_TIMEOUT = 1800        # 승인 대기(초). 무응답 시 자동 거절(30분)
RUN_HOUR = 7                   # 매일 실행 시각(한국시간 24h). 미국 정규장 마감 직후.
RUN_MINUTE = 30

CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

_position_qty = 0  # 보유 수량 추적(실제론 잔고조회로 동기화 권장)


def compute_trend(closes: list[float]) -> dict:
    """일봉 종가 리스트로 추세 지표를 계산해 dict로 반환."""
    n = len(closes)
    price = closes[-1]

    def sma(k):
        return round(sum(closes[-k:]) / k, 2) if n >= k else None

    sma5, sma20, sma60 = sma(5), sma(20), sma(60)
    return {
        "price": round(price, 2),
        "sma5": sma5,
        "sma20": sma20,
        "sma60": sma60,
        "above_sma20": (price > sma20) if sma20 else None,
        "sma5_above_sma20": (sma5 > sma20) if (sma5 and sma20) else None,
        "change_5d_pct": round((price / closes[-6] - 1) * 100, 2) if n >= 6 else None,
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
    """한 사이클 실행. 종료 시점에서 무조건 audit.log_cycle 한 줄 남긴다."""
    global _position_qty

    # 0) state 로드 + paused 검사
    state = load_state()
    if is_paused(state):
        msg = f"BOT PAUSED (paused_until={state.get('paused_until')}) → 사이클 skip"
        print("  " + msg)
        await bot.send_message(chat_id=CHAT_ID, text=f"⏸️ {msg}")
        log_cycle("cycle_skipped", {"reason": "paused", "symbol": SYMBOL})
        return

    client = KISClient()

    closes = client.get_daily_prices(SYMBOL, EXCHANGE, days=60)
    if len(closes) < 20:
        msg = f"일봉 데이터 부족({len(closes)}개). 휴장/운영시간 외일 수 있음. 건너뜀."
        print("  " + msg)
        await bot.send_message(chat_id=CHAT_ID, text=f"ℹ️ {msg}")
        log_cycle("cycle_skipped", {"reason": "insufficient_candles", "symbol": SYMBOL, "samples": len(closes)})
        return

    trend = compute_trend(closes)
    print(f"  추세: price={trend['price']} sma20={trend['sma20']} "
          f"sma5>sma20={trend['sma5_above_sma20']}")

    advice = get_advice(SYMBOL, trend)
    action, conf, reason = advice["action"], advice["confidence"], advice["reason"]
    print(f"  LLM: {action} (확신도 {conf}) - {reason}")

    base_payload = {
        "symbol": SYMBOL,
        "price": trend["price"],
        "sma20": trend["sma20"],
        "action": action,
        "confidence": conf,
        "reason": reason,
    }

    if action == "hold":
        await bot.send_message(chat_id=CHAT_ID, text=f"😴 오늘은 관망(hold). 사유: {reason}")
        log_cycle("cycle_skipped", {**base_payload, "reason_skip": "hold"})
        return
    if conf < CONFIDENCE_THRESHOLD:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=f"오늘 신호 {action}이나 확신도 {conf} < {CONFIDENCE_THRESHOLD} → 건너뜀.")
        log_cycle("cycle_skipped", {**base_payload, "reason_skip": "low_confidence"})
        return

    price = trend["price"]
    if action == "buy":
        qty = int(DAILY_BUDGET_USD // price)
        if qty < 1:
            await bot.send_message(chat_id=CHAT_ID, text=f"예산 ${DAILY_BUDGET_USD}로 1주도 못 삼(주가 ${price}). 건너뜀.")
            log_cycle("cycle_skipped", {**base_payload, "reason_skip": "budget_too_small"})
            return
        # 최대 보유금액 한도 체크
        if (_position_qty + qty) * price > MAX_POSITION_USD:
            await bot.send_message(chat_id=CHAT_ID, text=f"최대 보유금액 한도(${MAX_POSITION_USD}) 초과 → 건너뜀.")
            log_cycle("cycle_skipped", {**base_payload, "reason_skip": "position_cap"})
            return
        limit = round(price * 1.005, 2)
    else:  # sell
        if _position_qty <= 0:
            await bot.send_message(chat_id=CHAT_ID, text="보유 수량 없음 → 매도 건너뜀.")
            log_cycle("cycle_skipped", {**base_payload, "reason_skip": "no_position"})
            return
        qty = _position_qty
        limit = round(price * 0.995, 2)

    summary = (
        f"🤖 오늘의 매매 승인 요청 ({client.settings.env})\n\n"
        f"종목: {SYMBOL}\n동작: {'매수' if action=='buy' else '매도'} {qty}주\n"
        f"지정가: ${limit} (현재 ${price})\n"
        f"예산: ${DAILY_BUDGET_USD}\n확신도: {conf}\n사유: {reason}\n"
        f"추세: SMA5>SMA20={trend['sma5_above_sma20']}, 5일 {trend['change_5d_pct']}%\n\n"
        f"현재 보유(추적): {_position_qty}주"
    )
    decision = await ask_approval(bot, summary)
    if decision != "approve":
        print(f"  승인 안 됨({decision}).")
        log_cycle("cycle_skipped", {**base_payload, "qty": qty, "limit": limit, "reason_skip": f"user_{decision}"})
        return

    # 주문 결과 알림(✅/⚠️)은 KISClient.order가 자동 발송
    res = client.order(SYMBOL, action, qty, limit, EXCHANGE)
    rt = res.get("rt_cd")
    order_payload = {
        **base_payload,
        "qty": qty,
        "limit": limit,
        "rt_cd": rt,
        "msg1": res.get("msg1", ""),
        "odno": (res.get("output") or {}).get("ODNO"),
    }
    if rt == "0":
        _position_qty += qty if action == "buy" else -qty
        # state 갱신: 매수 성공 시 last_buy_at, daily_* 누적
        if action == "buy":
            today_iso = datetime.now().date().isoformat()
            def _mut(s: dict) -> None:
                s["last_buy_at"][SYMBOL] = today_iso
                s["daily_buy_count"] += 1
                s["daily_buy_amount_usd"] += qty * limit
                s["consecutive_errors"] = 0
            update_state(_mut)
        await bot.send_message(chat_id=CHAT_ID, text=f"📊 보유 갱신: {_position_qty}주")
        log_cycle("cycle_complete", order_payload)
    else:
        # 주문 거부 — consecutive_errors 누적
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
            err = f"{type(e).__name__}: {e}"
            print(f"  [오류] {err}")
            try:
                update_state(lambda s: s.update({"consecutive_errors": s.get("consecutive_errors", 0) + 1}))
            except Exception:
                pass
            try:
                log_cycle("error", {"symbol": SYMBOL, "error": err})
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