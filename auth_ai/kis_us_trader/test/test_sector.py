"""sector.py(macro_bias) 단위 테스트 — 네트워크/외부의존 0.

순수 함수(classify_bias / max_buys_for_bias / compute_breadth_pct) + FakeClient 로
compute_macro_bias 통합까지. KIS/Telegram/OpenAI 호출 없음.

실행(프로젝트 루트): python test/test_sector.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sector import (BREADTH_RISK_OFF_PCT, BREADTH_RISK_ON_PCT,
                    classify_bias, compute_breadth_pct, compute_macro_bias,
                    max_buys_for_bias)

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


class FakeClient:
    """get_daily_prices 만 모사. closes=None 이면 예외(조회 실패) 시뮬."""

    def __init__(self, closes=None, raise_exc=False):
        self._closes = closes
        self._raise = raise_exc
        self.calls = []

    def get_daily_prices(self, symbol, exchange="NASD", days=30):
        self.calls.append((symbol, exchange, days))
        if self._raise:
            raise RuntimeError("KIS down")
        return list(self._closes or [])


# ============================================================
print("\n=== 1) classify_bias — 추세 구조 ===")
# up_struct: price>sma20>=sma50, breadth None → risk_on
check(classify_bias(110, 105, 100, None) == "risk_on", "up_struct + breadth None → risk_on")
check(classify_bias(110, 100, 100, None) == "risk_on", "sma20==sma50 경계도 up_struct → risk_on")
# up_struct + breadth 확인
check(classify_bias(110, 105, 100, 60.0) == "risk_on", "up_struct + breadth=60(경계) → risk_on")
check(classify_bias(110, 105, 100, 75.0) == "risk_on", "up_struct + breadth 높음 → risk_on")
# up_struct + 낮은 breadth → divergence → risk_off
check(classify_bias(110, 105, 100, 30.0) == "risk_off", "up_struct지만 breadth 낮음 → risk_off(분산)")
check(classify_bias(110, 105, 100, 40.0) == "risk_off", "breadth=40(경계) → risk_off(<=)")
# up_struct + 중간 breadth → neutral
check(classify_bias(110, 105, 100, 50.0) == "neutral", "up_struct + breadth 중간(50) → neutral")

print("\n=== 2) classify_bias — 하락/혼조/unknown ===")
# down_struct: price<sma20<sma50 → risk_off (breadth 무관, risk_off 우선)
check(classify_bias(90, 95, 100, None) == "risk_off", "down_struct → risk_off")
check(classify_bias(90, 95, 100, 80.0) == "risk_off", "down_struct + breadth 높아도 risk_off 우선(보수)")
# 혼조(상승도 하락도 아님) → neutral
check(classify_bias(110, 105, 108, None) == "neutral", "혼조(sma20<sma50) → neutral")
check(classify_bias(102, 105, 100, None) == "neutral", "혼조(price<sma20지만 sma20>sma50) → neutral")
# unknown: 하나라도 None
check(classify_bias(None, 105, 100, 70.0) == "unknown", "price None → unknown")
check(classify_bias(110, None, 100, 70.0) == "unknown", "sma20 None → unknown")
check(classify_bias(110, 105, None, 70.0) == "unknown", "sma50 None → unknown")

print("\n=== 3) max_buys_for_bias ===")
check(max_buys_for_bias("risk_on") == 3, "risk_on → 3")
check(max_buys_for_bias("neutral") == 2, "neutral → 2")
check(max_buys_for_bias("risk_off") == 0, "risk_off → 0")
check(max_buys_for_bias("unknown") == 0, "unknown → 0(보수)")
check(max_buys_for_bias("garbage") == 0, "미지 라벨 → 0(보수)")

print("\n=== 4) compute_breadth_pct ===")
check(compute_breadth_pct(None) is None, "None → None")
check(compute_breadth_pct([]) is None, "빈 리스트 → None")
check(compute_breadth_pct([True, True, False, False]) == 50.0, "[T,T,F,F] → 50.0")
check(compute_breadth_pct([True] * 10) == 100.0, "all True → 100.0")
check(compute_breadth_pct([False] * 7) == 0.0, "all False → 0.0")

print("\n=== 5) compute_macro_bias 통합(FakeClient) ===")
# 5-1) 상승 60일 → up_struct → risk_on, SMH 1콜만
up_closes = [100.0 + i for i in range(60)]
c = FakeClient(closes=up_closes)
mb = compute_macro_bias(c)
check(mb["bias"] == "risk_on", f"상승 시계열 → risk_on (실측={mb['bias']})")
check(mb["smh_price"] == 159.0, f"smh_price=마지막 종가 159 (실측={mb['smh_price']})")
check(mb["samples"] == 60, "samples=60")
check(len(c.calls) == 1 and c.calls[0][0] == "SMH", "SMH 일봉 정확히 1콜")

# 5-2) 하락 시계열 → risk_off
down_closes = [160.0 - i for i in range(60)]
mb2 = compute_macro_bias(FakeClient(closes=down_closes))
check(mb2["bias"] == "risk_off", f"하락 시계열 → risk_off (실측={mb2['bias']})")

# 5-3) breadth 주입 → up_struct + 낮은 breadth → risk_off(분산)
mb3 = compute_macro_bias(FakeClient(closes=up_closes), member_above_sma20=[False] * 10)
check(mb3["breadth_pct"] == 0.0, "breadth_pct=0.0 반영")
check(mb3["bias"] == "risk_off", f"상승+breadth 0% → risk_off (실측={mb3['bias']})")

# 5-4) 조회 실패 → unknown + error
mb4 = compute_macro_bias(FakeClient(raise_exc=True))
check(mb4["bias"] == "unknown", "조회 예외 → unknown")
check("error" in mb4, "error 키 포함")
check(max_buys_for_bias(mb4["bias"]) == 0, "unknown → 매수 상한 0")

# 5-5) 데이터 부족(<50 → sma50 불가) → unknown (review #10: 20~49 도 unknown, 깨끗한 None dict)
mb5 = compute_macro_bias(FakeClient(closes=[100.0] * 10))
check(mb5["bias"] == "unknown", "<50 캔들(10개) → unknown")
check(mb5["samples"] == 10, "samples=10 보존")
mb5b = compute_macro_bias(FakeClient(closes=[100.0 + i for i in range(30)]))
check(mb5b["bias"] == "unknown", "30 캔들(<50, sma50 None) → unknown")
check(mb5b["smh_price"] is None, "불충분 fetch 는 깨끗한 unknown(수치 None) → 실패와 동일 표현")

# 5-6) 임계 상수 sanity
check(BREADTH_RISK_ON_PCT > BREADTH_RISK_OFF_PCT, "RISK_ON 임계 > RISK_OFF 임계")


# ============================================================
print(f"\n총 {_fails}건 실패")
sys.exit(1 if _fails else 0)
