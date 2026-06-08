"""영속화된 봇 상태 (`.state/state.json`).

다종목 매매 확장의 토대. 다음 필드를 한 파일에 모아 관리한다:
  - paused_until            : ISO datetime 또는 None. 이후이면 사이클 skip
  - consecutive_errors      : 누적 오류(LLM JSON 오류, KIS 주문 거부 등)
  - last_buy_at             : {symbol: 'YYYY-MM-DD'} 쿨다운 추적
  - daily_buy_count         : 당일 신규 매수 종목 수
  - daily_buy_amount_usd    : 당일 매수 금액 합계
  - daily_loss_realized_usd : 당일 실현 손실 (음수로 누적)
  - daily_reset_date_et     : 당일 카운터의 ET 날짜. 다르면 daily_* 리셋
  - open_orders             : 미체결 주문 추적 리스트

동시성:
  - 같은 프로세스: asyncio.Lock(`_async_lock`) — 코루틴 race 방지
  - 다른 프로세스: portalocker 파일 잠금 — 동시 R/M/W 직렬화

리셋 기준은 **ET 자정**. 한국시간 자정(KST 24:00)을 기준으로 잡으면 사이클 발화 시각
(07:30 KST = ET 17:30 또는 18:30)이 같은 ET 날짜에 묶이지 못해 race가 생긴다.
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

try:
    import portalocker
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "portalocker가 필요합니다. `pip install portalocker` 후 다시 실행하세요."
    ) from exc

_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = Path(os.getenv("STATE_DIR") or (_ROOT / ".state"))
STATE_FILE = STATE_DIR / "state.json"

ET = ZoneInfo("America/New_York")

DEFAULT_STATE: dict = {
    "paused_until": None,
    "consecutive_errors": 0,
    "last_buy_at": {},
    "daily_buy_count": 0,
    "daily_buy_amount_usd": 0.0,
    "daily_loss_realized_usd": 0.0,
    "daily_reset_date_et": None,
    "open_orders": [],
}

_async_lock = asyncio.Lock()


def _current_et_date_iso() -> str:
    return datetime.now(ET).date().isoformat()


def _ensure_state_file() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not STATE_FILE.exists():
        STATE_FILE.write_text(
            json.dumps(DEFAULT_STATE, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _reset_daily_if_new_et_day(data: dict) -> bool:
    """ET 날짜가 바뀌었으면 daily_* 리셋. 리셋 발생 시 True."""
    current = _current_et_date_iso()
    if data.get("daily_reset_date_et") != current:
        data["daily_buy_count"] = 0
        data["daily_buy_amount_usd"] = 0.0
        data["daily_loss_realized_usd"] = 0.0
        data["daily_reset_date_et"] = current
        return True
    return False


def _merge_defaults(data: dict) -> dict:
    """기존 state.json에 누락 필드가 있으면 DEFAULT_STATE 값으로 채운다(스키마 진화 대응)."""
    for k, v in DEFAULT_STATE.items():
        data.setdefault(k, v if not isinstance(v, (dict, list)) else type(v)(v))
    return data


def load_state() -> dict:
    """현재 상태 읽기(공유잠금). ET 리셋도 같은 호출에서 처리하지 않음 —
    상태를 보기만 할 때 부작용이 없도록. 리셋은 update_state에서만."""
    _ensure_state_file()
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        portalocker.lock(f, portalocker.LOCK_SH)
        try:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = dict(DEFAULT_STATE)
        finally:
            portalocker.unlock(f)
    return _merge_defaults(data)


def update_state(mutator: Callable[[dict], None]) -> dict:
    """원자적 read-modify-write (배타잠금). mutator(data)가 data를 in-place 수정.
    리턴값은 저장된 최종 상태."""
    _ensure_state_file()
    with open(STATE_FILE, "r+", encoding="utf-8") as f:
        portalocker.lock(f, portalocker.LOCK_EX)
        try:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = dict(DEFAULT_STATE)
            data = _merge_defaults(data)
            _reset_daily_if_new_et_day(data)
            mutator(data)
            f.seek(0)
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.truncate()
        finally:
            portalocker.unlock(f)
    return data


async def aupdate_state(mutator: Callable[[dict], None]) -> dict:
    """async 컨텍스트용 래퍼. asyncio.Lock + 스레드풀에서 sync 함수 실행."""
    async with _async_lock:
        return await asyncio.to_thread(update_state, mutator)


def is_paused(state: dict | None = None) -> bool:
    """paused_until > now면 True. None/과거이면 False."""
    if state is None:
        state = load_state()
    iso = state.get("paused_until")
    if not iso:
        return False
    try:
        until = datetime.fromisoformat(iso)
    except (ValueError, TypeError):
        return False
    # naive datetime은 로컬 시간으로 간주
    return datetime.now(until.tzinfo) < until if until.tzinfo else datetime.now() < until


# CLI 점검: python -m kis.state
if __name__ == "__main__":
    s = load_state()
    print(f"state file: {STATE_FILE}")
    print(json.dumps(s, ensure_ascii=False, indent=2))
