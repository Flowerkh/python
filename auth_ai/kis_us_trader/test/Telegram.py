"""텔레그램 승인 단독 테스트 (v2 - 표준 폴링 방식).

이전 버전은 콜백 수신이 라이브러리 버전을 타서, 버튼을 눌러도
스크립트가 못 받는 문제가 있었습니다. 이 버전은 표준 run_polling을
사용해 버튼 클릭을 확실히 수신합니다.

준비:
  - .env 에 TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID 입력
  - 봇과 대화창에서 메시지 한 번 보내둘 것

실행:
  python Telegram.py
  → 폰으로 승인 요청이 오면 버튼을 누르세요.
  → 결과가 콘솔에 찍히고 자동 종료됩니다.
"""
import os
import sys

from dotenv import load_dotenv

load_dotenv()

try:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
    from telegram.ext import Application, CallbackQueryHandler, ContextTypes
except ImportError:
    print("python-telegram-bot 이 필요합니다:  pip install python-telegram-bot")
    sys.exit(1)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """승인/거절 버튼 클릭 콜백."""
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass  # 만료된(오래된) 쿼리면 무시
    choice = query.data  # "approve" | "reject"
    label = "✅ 승인됨" if choice == "approve" else "❌ 거절됨"
    await query.edit_message_text(f"{query.message.text}\n\n— {label}")

    print(f"\n===== 결과: {choice} =====")
    if choice == "approve":
        print("→ (실제 시스템이라면 여기서 주문을 실행)")
    else:
        print("→ 주문하지 않고 건너뜀")

    # 응답을 받았으니 폴링 종료 → 프로그램 끝
    context.application.stop_running()


async def post_init(app: Application):
    """봇이 폴링을 시작한 직후, 승인 요청 메시지를 보낸다."""
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ 승인", callback_data="approve"),
        InlineKeyboardButton("❌ 거절", callback_data="reject"),
    ]])
    text = (
        "🤖 [테스트] 매매 승인 요청\n\n"
        "종목: NVDA (예시)\n"
        "동작: 매수 1주\n"
        "예상가: $180.00 (가상)\n"
        "확신도: 70%\n\n"
        "이건 실제 주문이 아닌 텔레그램 연동 테스트입니다.\n"
        "버튼을 눌러주세요. (스크립트가 떠 있는 동안 유효)"
    )
    await app.bot.send_message(chat_id=CHAT_ID, text=text, reply_markup=keyboard)
    print("[정보] 폰으로 승인 요청을 보냈습니다. 텔레그램에서 버튼을 눌러주세요...")


def main():
    if not TOKEN:
        print("[오류] .env 에 TELEGRAM_BOT_TOKEN 이 없습니다.")
        return
    if not CHAT_ID:
        print("[오류] .env 에 TELEGRAM_CHAT_ID 가 없습니다. (예: 8348817158)")
        return

    app = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )
    app.add_handler(CallbackQueryHandler(on_button))

    print("[정보] 봇 시작. 버튼 응답을 기다립니다... (Ctrl+C로 중단)")
    # 표준 폴링: 버튼 클릭을 확실히 수신한다
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    print("[정보] 종료되었습니다.")


if __name__ == "__main__":
    main()