"""접근토큰(access token) 발급 및 캐시.

KIS 토큰은 발급 후 약 24시간 유효합니다. 매 실행마다 새로 발급하면
'토큰 발급 횟수 제한'에 걸릴 수 있으므로 파일에 캐시하여 재사용합니다.
"""
import json
import time
from pathlib import Path

import requests

from .config import Settings

# 환경별로 캐시 파일을 분리 (모의/실전 토큰 혼용 방지)
_CACHE_DIR = Path.home() / ".kis_us_trader"
_CACHE_DIR.mkdir(exist_ok=True)


def _cache_path(settings: Settings) -> Path:
    return _CACHE_DIR / f"token_{settings.env}.json"


def get_access_token(settings: Settings) -> str:
    cache = _cache_path(settings)

    # 1) 캐시 확인: 만료 10분 전까지는 재사용
    if cache.exists():
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            if data.get("expires_at", 0) - 600 > time.time():
                return data["access_token"]
        except (json.JSONDecodeError, KeyError):
            pass  # 캐시 손상 시 재발급

    # 2) 신규 발급
    url = f"{settings.base_url}/oauth2/tokenP"
    payload = {
        "grant_type": "client_credentials",
        "appkey": settings.app_key,
        "appsecret": settings.app_secret,
    }
    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()
    body = resp.json()

    token = body["access_token"]
    # expires_in(초) 또는 access_token_token_expired(문자열)가 올 수 있음
    expires_in = int(body.get("expires_in", 86400))

    cache.write_text(
        json.dumps({
            "access_token": token,
            "expires_at": time.time() + expires_in,
        }),
        encoding="utf-8",
    )
    return token
