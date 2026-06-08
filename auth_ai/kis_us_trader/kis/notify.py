"""텔레그램 알림 헬퍼 (동기, 의존성 최소).

매수/매도/취소 등 매매 이벤트에서 자동 호출되어 텔레그램 메시지를 보냅니다.
python-telegram-bot의 비동기 흐름을 거치지 않고 raw HTTP로 보내므로
비동기 컨텍스트가 아닌 곳(test_order.py 등)에서도 그대로 호출 가능합니다.

환경변수(TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID) 누락이나 네트워크 오류는
silent fail — 알림 실패가 매매 흐름을 절대 막지 않도록 합니다.

모듈 로드 시 load_dotenv()를 한 번 호출 — `python -c` 같은 짧은 진입점에서도
.env가 자동 적재되어 동작. 이미 호출된 적 있다면 idempotent(중복 호출 무해).
"""
import os

import requests
from dotenv import load_dotenv

load_dotenv()


def send_telegram(text: str) -> bool:
    """텔레그램 메시지 전송. 성공 시 True, 실패 시 False(예외 발생 안 함)."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=5,
        )
        return resp.ok
    except requests.RequestException:
        return False
