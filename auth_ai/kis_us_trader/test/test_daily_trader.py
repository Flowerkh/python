"""daily_trader.select_picks 단위 테스트 — 네트워크/LLM 0(순수 함수).

macro_bias N 제한 + confidence 임계 + 정렬/동률 결정성 검증.

실행(프로젝트 루트): python test/test_daily_trader.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from daily_trader import CONFIDENCE_THRESHOLD, select_picks

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


def adv(action, conf):
    return {"action": action, "confidence": conf, "reason": "x", "flagged": []}


print(f"\n=== select_picks (CONFIDENCE_THRESHOLD={CONFIDENCE_THRESHOLD}) ===")

decisions = {
    "AAPL": adv("buy", 90),
    "NVDA": adv("buy", 85),
    "AMD":  adv("buy", 95),
    "MU":   adv("buy", 80),
    "INTC": adv("hold", 99),
    "TSM":  adv("sell", 88),
    "QCOM": adv("buy", 79),   # 임계 미만 → 제외
}

# N=2: conf>=80 BUY 정렬 desc → [AMD95, AAPL90, NVDA85, MU80], 상위 2 = [AMD, AAPL]
buys, sells = select_picks(decisions, max_buys=2, threshold=80)
check(buys == ["AMD", "AAPL"], f"N=2 → 상위 2 매수 [AMD, AAPL] (실측 {buys})")
check(sells == ["TSM"], f"SELL conf>=80 → [TSM] (실측 {sells})")

# N=0(risk_off/unknown) → 매수 전면 컷, 매도는 유지
buys0, sells0 = select_picks(decisions, max_buys=0, threshold=80)
check(buys0 == [], "N=0 → 매수 없음(risk_off 전면 컷)")
check(sells0 == ["TSM"], "N=0 라도 매도(청산)는 허용")

# N 충분히 큼 → conf>=80 BUY 전부, 정렬 desc
buysA, _ = select_picks(decisions, max_buys=10, threshold=80)
check(buysA == ["AMD", "AAPL", "NVDA", "MU"], f"N 큼 → 전체 정렬 (실측 {buysA})")

# 임계 79 종목 제외 확인
check("QCOM" not in buysA, "conf=79 < 80 → 제외")

# 동률 confidence → 알파벳 순(결정성)
tie = {"NVDA": adv("buy", 85), "AMD": adv("buy", 85), "AVGO": adv("buy", 85)}
buyt, _ = select_picks(tie, max_buys=2, threshold=80)
check(buyt == ["AMD", "AVGO"], f"동률 85 → 알파벳 순 상위2 [AMD, AVGO] (실측 {buyt})")

# SELL 도 임계 적용
sell_low = {"TSM": adv("sell", 70)}
_, slo = select_picks(sell_low, max_buys=2, threshold=80)
check(slo == [], "SELL conf=70 < 80 → 제외")

# hold/flagged-hold 는 제외(action!=buy/sell)
holds = {"AAPL": adv("hold", 95), "NVDA": adv("buy", 0)}  # NVDA flagged→hold 강등 시 conf 0
bh, sh = select_picks(holds, max_buys=3, threshold=80)
check(bh == [] and sh == [], "hold + 저신뢰(flagged 강등) → 선정 0")

# 빈 decisions
check(select_picks({}, max_buys=3) == ([], []), "빈 decisions → ([], [])")


print(f"\n총 {_fails}건 실패")
sys.exit(1 if _fails else 0)
