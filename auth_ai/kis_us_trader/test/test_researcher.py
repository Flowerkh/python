"""researcher.decide_parallel 단위 테스트 — OpenAI 호출 0(가짜 advisor 주입).

실행(프로젝트 루트): python test/test_researcher.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from researcher import decide_parallel

PASS = "[OK ]"
FAIL = "[FAIL]"
_fails = 0


def check(cond: bool, label: str) -> None:
    global _fails
    if cond:
        print(f"  {PASS} {label}")
    else:
        print(f"  {FAIL} {label}")
        _fails += 1


# ===== 가짜 advisor 들 =====
def make_canned_advisor(table):
    """{symbol: advice} 표대로 응답. 표에 'RAISE' 면 예외."""
    async def _adv(symbol, trend, macro_bias):
        v = table.get(symbol)
        if v == "RAISE":
            raise RuntimeError(f"boom {symbol}")
        return v
    return _adv


def make_flaky_advisor(fail_times):
    """첫 fail_times 번 호출은 예외, 이후 성공. 종목별 카운터."""
    counters = {}

    async def _adv(symbol, trend, macro_bias):
        n = counters.get(symbol, 0)
        counters[symbol] = n + 1
        if n < fail_times:
            raise RuntimeError(f"flaky {symbol} attempt {n}")
        return {"action": "buy", "confidence": 70, "reason": f"{symbol} ok", "flagged": []}
    return _adv


market = {
    "AAPL": {"price": 180, "signal_strength": "strong"},
    "NVDA": {"price": 120, "signal_strength": "moderate"},
    "AMD":  {"price": 90, "signal_strength": "weak"},
}
macro = {"bias": "risk_on"}


print("\n=== 1) 정상 + 일부 실패 → 실패 종목 hold 폴백 ===")
table = {
    "AAPL": {"action": "buy", "confidence": 85, "reason": "추세 양호", "flagged": []},
    "NVDA": "RAISE",
    "AMD":  {"action": "hold", "confidence": 40, "reason": "약세", "flagged": []},
}
res = asyncio.run(decide_parallel(market, macro, retries=2, backoff_base=0,
                                  advisor=make_canned_advisor(table)))
check(set(res.keys()) == {"AAPL", "NVDA", "AMD"}, "모든 종목 키 보존")
check(res["AAPL"]["action"] == "buy" and res["AAPL"]["confidence"] == 85, "AAPL buy 85 보존")
check(res["NVDA"]["action"] == "hold" and res["NVDA"]["confidence"] == 0,
      "실패 종목 NVDA → hold 0 폴백")
check("error" in res["NVDA"], "NVDA 폴백에 error 기록")
check(res["AMD"]["action"] == "hold", "AMD hold 보존")


print("\n=== 2) retry — 첫 1회 실패 후 성공 ===")
res2 = asyncio.run(decide_parallel(market, macro, retries=2, backoff_base=0,
                                   advisor=make_flaky_advisor(fail_times=1)))
check(all(res2[s]["action"] == "buy" for s in market), "1회 실패→재시도 성공 → 전부 buy")


print("\n=== 3) retry 초과 → hold 폴백 ===")
res3 = asyncio.run(decide_parallel(market, macro, retries=1, backoff_base=0,
                                   advisor=make_flaky_advisor(fail_times=5)))
check(all(res3[s]["action"] == "hold" and res3[s]["confidence"] == 0 for s in market),
      "retries=1 < 필요 → 전부 hold 폴백")


print("\n=== 4) 모양 깨진 응답 → hold 폴백 ===")
bad = make_canned_advisor({
    "AAPL": {"action": "buy", "confidence": 80, "reason": "ok", "flagged": []},
    "NVDA": {"oops": "no action"},      # action 없음
    "AMD":  {"action": "long", "confidence": 99, "reason": "?"},  # 잘못된 action
})
res4 = asyncio.run(decide_parallel(market, macro, retries=0, backoff_base=0, advisor=bad))
check(res4["AAPL"]["action"] == "buy", "정상 AAPL 유지")
check(res4["NVDA"]["action"] == "hold", "action 누락 → hold 폴백")
check(res4["AMD"]["action"] == "hold", "잘못된 action → hold 폴백")


print("\n=== 5) 빈 market → 빈 dict ===")
check(asyncio.run(decide_parallel({}, macro, advisor=make_canned_advisor({}))) == {},
      "빈 market → {}")


print("\n=== 6) per_call_timeout — hung advisor → 폴백(review #11) ===")
async def _slow_advisor(symbol, trend, macro_bias):
    await asyncio.sleep(0.3)  # per_call_timeout 보다 길게
    return {"action": "buy", "confidence": 90, "reason": "late", "flagged": []}

res6 = asyncio.run(decide_parallel(market, macro, retries=1, backoff_base=0,
                                   per_call_timeout=0.01, advisor=_slow_advisor))
check(all(res6[s]["action"] == "hold" and res6[s]["confidence"] == 0 for s in market),
      "타임아웃(0.01s < 0.3s) → 전부 hold 폴백")
check(all("error" in res6[s] for s in market), "타임아웃 폴백에 error 기록")


print(f"\n총 {_fails}건 실패")
sys.exit(1 if _fails else 0)
