"""감사 로그 (`logs/cycles-YYYYMM.jsonl`).

매 사이클 한 줄씩 append. 각 줄은 SHA-256 hash chain으로 직전 줄과 연결되어
사후 변조 탐지에 활용. Phase 0 검증 기준 "audit log에 7줄이 hash chain으로 연결".

엔트리 형식:
  {
    "ts": "2026-06-04T07:30:12",
    "prev_hash": "0000...",        # 직전 줄의 hash. 첫 줄은 64자 0.
    "event": "cycle_complete",     # 'cycle_complete' | 'cycle_skipped' | 'error'
    ... 페이로드 ...,
    "hash": "abcd...",             # 이 줄의 hash (prev_hash 포함 모든 필드의 SHA-256)
  }

체인 검증: prev_hash가 직전 줄의 hash와 일치하는지 순회 점검.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = _ROOT / "logs"

_GENESIS_HASH = "0" * 64


def _current_log_file(now: datetime | None = None) -> Path:
    now = now or datetime.now()
    return LOGS_DIR / f"cycles-{now:%Y%m}.jsonl"


def _read_last_hash(log_file: Path) -> str:
    """파일 끝 줄의 hash를 반환. 파일이 없거나 마지막 줄 파싱 실패 시 GENESIS."""
    if not log_file.exists():
        return _GENESIS_HASH
    try:
        lines = [
            ln for ln in log_file.read_text(encoding="utf-8").splitlines() if ln.strip()
        ]
    except OSError:
        return _GENESIS_HASH
    if not lines:
        return _GENESIS_HASH
    try:
        last = json.loads(lines[-1])
        return last.get("hash") or _GENESIS_HASH
    except json.JSONDecodeError:
        return _GENESIS_HASH


def _hash_body(entry_without_hash: dict) -> str:
    body = json.dumps(entry_without_hash, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def log_cycle(event: str, payload: dict | None = None) -> dict:
    """한 줄을 추가하고 저장된 엔트리(hash 포함)를 반환.

    event: 'cycle_complete' | 'cycle_skipped' | 'error' 등 식별자
    payload: 임의의 추가 필드 (symbol, action, confidence, rt_cd, ...)
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = _current_log_file()
    prev_hash = _read_last_hash(log_file)
    entry: dict = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "prev_hash": prev_hash,
        "event": event,
    }
    if payload:
        for k, v in payload.items():
            if k in ("ts", "prev_hash", "event", "hash"):
                continue  # 예약 필드 보호
            entry[k] = v
    entry["hash"] = _hash_body(entry)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def verify_chain(log_file: Path | None = None) -> tuple[bool, int, str | None]:
    """체인 검증. (ok, checked_lines, error_msg) 반환.

    각 줄의 prev_hash가 직전 줄의 hash와 일치하고, 줄 자체의 hash가
    재계산값과 일치하는지 확인.
    """
    log_file = log_file or _current_log_file()
    if not log_file.exists():
        return True, 0, None
    expected_prev = _GENESIS_HASH
    n = 0
    for i, line in enumerate(log_file.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as e:
            return False, n, f"line {i}: JSON 파싱 실패 ({e})"
        if entry.get("prev_hash") != expected_prev:
            return False, n, f"line {i}: prev_hash 불일치 (expected {expected_prev[:8]}…)"
        stored_hash = entry.pop("hash", None)
        recomputed = _hash_body(entry)
        if stored_hash != recomputed:
            return False, n, f"line {i}: hash 재계산 불일치"
        expected_prev = stored_hash
        n += 1
    return True, n, None


# CLI 점검: python -m kis.audit verify
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        ok, n, err = verify_chain()
        print(f"체인 검증: {'OK' if ok else 'FAIL'} ({n}줄)")
        if err:
            print(f"  사유: {err}")
        sys.exit(0 if ok else 1)
    else:
        print(f"log dir: {LOGS_DIR}")
        print("사용법: python -m kis.audit verify")
