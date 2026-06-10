"""매매 가능 종목 화이트리스트(단일 진실 소스) + paper_tradable 24h 캐시.

Phase 1: AAPL 1개로 코드 경로 통과 확인.
Phase 2: 반도체 10종목 추가(NVDA·AMD·AVGO·MU·INTC·QCOM·TXN·AMAT·LRCX·TSM).

화이트리스트 외 ticker는 universe.is_whitelisted/is_paper_tradable 둘 다 False를
돌려준다. 즉 LLM이 환각으로 던진 ticker가 주문 호출에 도달할 수 없다.
캐시 디스크 위치: `.state/universe_cache.json` (state.json과 같은 디렉터리).
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import KISClient  # 런타임 import 사이클 회피용

_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = Path(os.getenv("STATE_DIR") or (_ROOT / ".state"))
UNIVERSE_CACHE_FILE = STATE_DIR / "universe_cache.json"
TRADABLE_CACHE_TTL_SEC = 24 * 3600
_VALID_EXCHANGES = {"NASD", "NYSE", "AMEX"}
_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Symbol:
    """화이트리스트 한 종목 메타. immutable, hashable."""
    symbol: str
    exchange: str
    sector: str
    paper_tradable: bool = True


SEMI_UNIVERSE_CORE: tuple[Symbol, ...] = (
    Symbol("AAPL", "NASD", "megacap_tech", True),
    # Phase 2 — 반도체 10종목 (TSM 만 NYSE, 나머지 NASDAQ).
    #   paper_tradable 시드값은 True 지만, 첫 가동 시 test/test_universe_health.py 로
    #   10종목 get_price 실측 후 캐시(.state/universe_cache.json)에 반영할 것.
    #   모의계좌에서 일부 종목이 거래 불가일 수 있다(CLAUDE.md KIS 함정 #4).
    Symbol("NVDA", "NASD", "semiconductor", True),
    Symbol("AMD",  "NASD", "semiconductor", True),
    Symbol("AVGO", "NASD", "semiconductor", True),
    Symbol("MU",   "NASD", "semiconductor", True),
    Symbol("INTC", "NASD", "semiconductor", True),
    Symbol("QCOM", "NASD", "semiconductor", True),
    Symbol("TXN",  "NASD", "semiconductor", True),
    Symbol("AMAT", "NASD", "semiconductor", True),
    Symbol("LRCX", "NASD", "semiconductor", True),
    Symbol("TSM",  "NYSE", "semiconductor", True),
)

# import 시점 검증
for _s in SEMI_UNIVERSE_CORE:
    if _s.exchange not in _VALID_EXCHANGES:
        raise ValueError(f"Invalid exchange {_s.exchange!r} for {_s.symbol}")

_BY_SYMBOL: dict[str, Symbol] = {s.symbol: s for s in SEMI_UNIVERSE_CORE}
_WHITELIST: frozenset[str] = frozenset(_BY_SYMBOL)
_CACHE: dict[str, dict] = {}  # {symbol: {paper_tradable, checked_at, last_error}}


def _norm(symbol: str | None) -> str:
    return (symbol or "").strip().upper()


def load_tradable_cache() -> dict[str, dict]:
    """디스크 캐시를 메모리에 적재. 손상/없음은 빈 dict로 폴백(시드값 사용)."""
    global _CACHE
    _CACHE = {}
    if not UNIVERSE_CACHE_FILE.exists():
        return _CACHE
    try:
        raw = json.loads(UNIVERSE_CACHE_FILE.read_text(encoding="utf-8"))
        for sym, entry in (raw.get("entries") or {}).items():
            if sym in _WHITELIST and isinstance(entry, dict):
                _CACHE[sym] = entry
    except (json.JSONDecodeError, OSError):
        _CACHE = {}
    return _CACHE


def _flush_cache() -> None:
    """원자적 캐시 저장(tmp 후 rename)."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": _SCHEMA_VERSION, "entries": _CACHE}
    tmp = UNIVERSE_CACHE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, UNIVERSE_CACHE_FILE)


def list_all(tradable_only: bool = False) -> list[Symbol]:
    """전체 또는 거래 가능 종목만. 결과는 tuple의 얕은 복사 list."""
    if not tradable_only:
        return list(SEMI_UNIVERSE_CORE)
    return [s for s in SEMI_UNIVERSE_CORE if is_paper_tradable(s.symbol)]


def list_by_sector(sector: str, tradable_only: bool = False) -> list[Symbol]:
    """섹터 필터링. 매치 없으면 빈 리스트."""
    return [s for s in list_all(tradable_only) if s.sector == sector]


def get(symbol: str) -> Symbol | None:
    """O(1) 룩업. 대소문자/공백 정규화. 미존재 시 None."""
    return _BY_SYMBOL.get(_norm(symbol))


def is_whitelisted(symbol: str) -> bool:
    """화이트리스트 멤버십(paper_tradable 무관). 빈/None 입력은 False."""
    return _norm(symbol) in _WHITELIST


def get_sector(symbol: str) -> str | None:
    """safety_gate의 섹터 캡 계산용. 미존재 시 None."""
    s = get(symbol)
    return s.sector if s else None


def is_paper_tradable(symbol: str) -> bool:
    """화이트리스트 + 캐시값 기준. 캐시 없으면 시드값 폴백.

    캐시 만료 여부는 보지 않는다(stale도 그냥 마지막 알려진 값). safety_gate가
    이걸 그대로 신뢰 → 보수적 동작(시드 True인 한 통과).
    """
    sym = _norm(symbol)
    if sym not in _WHITELIST:
        return False
    entry = _CACHE.get(sym)
    if entry is not None:
        return bool(entry.get("paper_tradable"))
    return _BY_SYMBOL[sym].paper_tradable


def is_tradable(symbol, client=None, force_refresh: bool = False) -> bool:
    """whitelist AND paper_tradable, TTL 만료 시 헬스체크로 갱신.

    client=None이면 캐시값 또는 시드값 폴백(네트워크 호출 없음).
    """
    sym = _norm(symbol)
    if sym not in _WHITELIST:
        return False
    entry = _CACHE.get(sym)
    fresh = False
    if entry and not force_refresh:
        try:
            age = time.time() - datetime.fromisoformat(entry["checked_at"]).timestamp()
            fresh = age < TRADABLE_CACHE_TTL_SEC
        except (KeyError, TypeError, ValueError):
            fresh = False
    if fresh:
        return bool(entry.get("paper_tradable"))
    if client is None:
        return bool(entry["paper_tradable"]) if entry else _BY_SYMBOL[sym].paper_tradable
    return _healthcheck_and_record(sym, client)


def _healthcheck_and_record(sym: str, client) -> bool:
    """get_last_price로 헬스체크 후 캐시 갱신. 실패 시 기존값 유지."""
    prior = _CACHE.get(sym, {})
    try:
        meta = get(sym)
        price = client.get_last_price(sym, meta.exchange if meta else "NASD")
        tradable = price > 0
        _CACHE[sym] = {
            "paper_tradable": tradable,
            "checked_at": datetime.now().isoformat(timespec="seconds"),
            "last_error": None,
        }
    except Exception as e:
        # transient: 기존값 유지, last_error만 기록(checked_at은 갱신 안 함)
        _CACHE[sym] = {
            "paper_tradable": prior.get("paper_tradable", _BY_SYMBOL[sym].paper_tradable),
            "checked_at": prior.get("checked_at"),
            "last_error": f"{type(e).__name__}: {e}",
        }
        _flush_cache()
        return bool(_CACHE[sym]["paper_tradable"])
    _flush_cache()
    return tradable


def refresh_tradable_cache(client, symbols: list[str] | None = None) -> dict[str, bool]:
    """강제 헬스체크. symbols=None이면 화이트리스트 전체. 종목별 격리(try/except)."""
    targets = [_norm(s) for s in (symbols or [s.symbol for s in SEMI_UNIVERSE_CORE])]
    out: dict[str, bool] = {}
    for sym in targets:
        if sym not in _WHITELIST:
            continue
        try:
            out[sym] = _healthcheck_and_record(sym, client)
        except Exception:
            out[sym] = False
    return out


# 모듈 import 시 1회 자동 적재
load_tradable_cache()
