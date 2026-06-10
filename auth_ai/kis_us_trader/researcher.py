"""종목별 LLM 결정을 비동기 병렬로 모으는 모듈 (Phase 2, 설계안 C).

`decide_parallel(market, macro_bias)`:
  - 유니버스 종목들에 대해 종목당 1콜씩 LLM(aget_advice)을 asyncio.gather 로 동시 호출.
  - 종목별로 retry(기본 2회, 지수 백오프). 끝까지 실패한 종목은 **hold 로 폴백**(절대 raise 안 함).
  - 반환: {symbol: {action, confidence, reason, flagged, ...}} — 입력의 모든 종목 키 보존.

설계 의도(DESIGN.md §2): LLM 은 종목당 buy/sell/hold 만 답한다(환각 표면적 최소화).
종목 발굴/순위/배분/한도는 코드(universe/safety_gate/portfolio)가 담당하고, 여기서는
"각 종목 독립 판단을 안전하게 모으기"만 한다. 한 종목 LLM 실패가 다른 종목을 막지 않는다.

advisor 주입(advisor=...)으로 단위 테스트 시 OpenAI 없이 가짜 결정 함수를 넣을 수 있다.
"""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from llm_advisor import aget_advice

# 끝까지 실패한 종목의 보수적 폴백(주문 도달 불가 — action=hold).
_HOLD_FALLBACK = {"action": "hold", "confidence": 0, "reason": "LLM 실패 → 보수적 hold", "flagged": []}

Advisor = Callable[[str, dict, dict | None], Awaitable[dict]]


async def _decide_one(
    symbol: str,
    trend: dict,
    macro_bias: dict | None,
    retries: int,
    backoff_base: float,
    advisor: Advisor,
    per_call_timeout: float,
) -> dict:
    """종목 1개 결정 + retry. 끝까지 실패해도 raise 하지 않고 hold 폴백 dict 반환.

    per_call_timeout>0 이면 advisor 호출을 asyncio.wait_for 로 감싼다 — 한 종목의 hung LLM 호출이
    asyncio.gather 전체(=daily_cycle)를 무한정 막지 못하게(precommit review #11). TimeoutError 는
    아래 except 가 잡아 retry/폴백으로 흐른다. (단, to_thread 스레드는 취소 불가 → SDK timeout 이
    실제 부하 해소; 이 wait_for 는 루프 진행 보장용.)
    """
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            if per_call_timeout and per_call_timeout > 0:
                res = await asyncio.wait_for(advisor(symbol, trend, macro_bias), timeout=per_call_timeout)
            else:
                res = await advisor(symbol, trend, macro_bias)
            if isinstance(res, dict) and res.get("action") in ("buy", "sell", "hold"):
                return res
            # 모양이 깨진 응답 → 폴백(보수)
            return dict(_HOLD_FALLBACK)
        except Exception as e:  # noqa: BLE001 — 종목별 격리
            last_err = e
            if attempt < retries and backoff_base > 0:
                await asyncio.sleep(backoff_base * (2 ** attempt))
    return {**_HOLD_FALLBACK,
            "reason": f"LLM 실패({type(last_err).__name__}) → hold",
            "error": f"{type(last_err).__name__}: {last_err}"}


async def decide_parallel(
    market: dict[str, dict],
    macro_bias: dict | None = None,
    *,
    retries: int = 2,
    backoff_base: float = 0.5,
    advisor: Advisor = aget_advice,
    per_call_timeout: float = 35.0,
) -> dict[str, dict]:
    """market = {symbol: trend_dict}. 종목별 LLM 결정을 동시 수집해 {symbol: advice} 반환.

    - asyncio.gather(return_exceptions=True): 한 코루틴 예외가 전체를 깨지 않게.
    - _decide_one 이 이미 내부에서 폴백하므로 여기 도달하는 예외는 드물지만, 방어적으로 한 번 더 흡수.
    - 입력의 모든 symbol 키가 결과에 존재(누락 종목 = hold).
    """
    symbols = list(market.keys())
    if not symbols:
        return {}
    coros = [
        _decide_one(s, market[s] or {}, macro_bias, retries, backoff_base, advisor, per_call_timeout)
        for s in symbols
    ]
    results = await asyncio.gather(*coros, return_exceptions=True)
    out: dict[str, dict] = {}
    for s, r in zip(symbols, results):
        if isinstance(r, Exception):
            out[s] = {**_HOLD_FALLBACK, "reason": f"내부 예외({type(r).__name__}) → hold"}
        elif isinstance(r, dict):
            out[s] = r
        else:
            out[s] = dict(_HOLD_FALLBACK)
    return out
