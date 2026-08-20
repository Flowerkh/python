import os
import sys
from datetime import datetime

import requests
from dotenv import load_dotenv

# 콘솔(cp949)에서 이모지·한글 출력 시 UnicodeEncodeError 방지
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from weather import get_today_weather
from kbo import get_kbo_games
from exchange import get_exchange_rates
from lucky import get_lucky

# 같은 폴더의 .env에서 텔레그램 토큰/챗ID 로드
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


def _print_and_collect(text: str, parts: list) -> None:
    print(text)
    parts.append(text)


def send_telegram(text: str) -> None:
    """.env의 봇 토큰/챗ID로 텔레그램 메시지를 전송합니다."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("❌ TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 가 .env에 없습니다.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }

    try:
        res = requests.post(url, data=payload, timeout=10)
        if res.status_code == 200:
            print("📨 텔레그램 전송 완료")
        else:
            print(f"❌ 텔레그램 전송 실패: {res.text}")
    except requests.RequestException as e:
        print(f"❌ 텔레그램 전송 예외: {e}")


if __name__ == "__main__":
    today = datetime.now().strftime("%Y-%m-%d")
    output_parts = []
    p = lambda text: _print_and_collect(text, output_parts)

    p(f"=== {today} ===")
    # ── KBO ──
    p(f"=== 오늘 KBO ===")
    kbo = get_kbo_games()
    if "error" in kbo:
        p(kbo["error"])
    else:
        for line in kbo["lines"]:
            p(line)
    p("")

    # ── 날씨 ──
    p(f"=== 날씨 ===")
    weather = get_today_weather()
    if "error" in weather:
        p(weather["error"])
    else:
        for line in weather["lines"]:
            p(line)
    p("")

    # ── 환율 ──
    p("=== 환율 ===")
    rates = get_exchange_rates()
    if "error" in rates:
        p(rates["error"])
    else:
        for key, value in rates.items():
            p(f"  {key}: {value}")
    p("")

    # ── 운세 ──
    p("=== 운세 ===")
    for line in get_lucky():
        p(line)

    send_telegram("\n".join(output_parts))
