"""kis.signals 단위 테스트 — vol 정규화(P2) + 회귀(P1까지의 동작 보존).

네트워크/외부의존 0. KIS/Telegram/OpenAI 호출 없음.

실행(프로젝트 루트): python test/test_signals.py
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kis.signals import (BASELINE_VOL, STRONG_CHG_PCT, STRONG_SPREAD_PCT,
                         VOL_WINDOW, WEAK_SCORE_CUT, classify_strength,
                         compute_vol_factor)

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


# ============================================================
# 1) classify_strength 회귀 — vol_factor=1.0 기본값이 P1 까지의 동작과 동일
# ============================================================
print("\n=== 1) classify_strength 회귀(vol_factor 기본=1.0) ===")
# weak 경계: score < 3.5 → weak. score = 3.5 → moderate (strict <).
check(classify_strength(1.0, 1.0) == "weak", "weak: spread=1.0 chg=1.0 (score=2.0<3.5)")
check(classify_strength(1.5, 1.5) == "weak", "weak: score=3.0<3.5")
check(classify_strength(1.5, 2.0) == "moderate", "moderate 경계: score=3.5(=cut) → moderate(strict <)")
check(classify_strength(2.0, 2.0) == "moderate", "moderate: score=4.0≥3.5, chg<3")
# strong 경계: spread>=1.0 AND chg>=3.0
check(classify_strength(1.0, 3.0) == "strong", "strong 경계: spread=1.0 chg=3.0")
check(classify_strength(0.9, 3.0) == "moderate", "strong NOT: spread<1.0")
check(classify_strength(1.0, 2.9) == "moderate", "strong NOT: chg<3.0")
check(classify_strength(2.5, 5.0) == "strong", "strong: spread/chg 큼")
# weak < strong 우선순위 (저-score 인데 strong 조건 만족 시도 weak)
check(classify_strength(0.1, 0.1) == "weak", "weak: 매우 작은 값")


# ============================================================
# 2) classify_strength + vol_factor — score 정규화
# ============================================================
print("\n=== 2) classify_strength vol_factor 정규화 ===")
# 고변동(vol_factor=2.0): score /=2 → 더 많은 weak
# spread=2.0, chg=2.0: score=4.0/2.0 = 2.0 < 3.5 → weak (절대값으로는 moderate)
check(classify_strength(2.0, 2.0, 1.0) == "moderate", "vol=1.0: score=4.0 → moderate")
check(classify_strength(2.0, 2.0, 2.0) == "weak", "vol=2.0: norm score=2.0 → weak (고변동 throttle UP)")
# 저변동(vol_factor=0.5): score *=2 → 더 적은 weak
# spread=1.0, chg=1.0: score=2.0/0.5 = 4.0 ≥ 3.5 → moderate (절대값으로는 weak)
check(classify_strength(1.0, 1.0, 1.0) == "weak", "vol=1.0: score=2.0 → weak")
check(classify_strength(1.0, 1.0, 0.5) == "moderate", "vol=0.5: norm score=4.0 → moderate (저변동 weak 해제)")
# 고변동(vol_factor 큼) + raw strong 만족 → normalized score 가 낮으면 weak 가 우선 (throttle)
# raw score=4.0, vol=2.0 → norm=2.0 < 3.5 → weak. AMD strong 64% 과발동 문제도 같이 해소.
check(classify_strength(1.0, 3.0, 2.0) == "weak",
      "고변동 raw strong → norm score 낮으면 weak 우선(AMD strong-과발동 throttle)")
# 저변동 + raw strong 만족 → strong (norm score 높아져 weak 통과)
check(classify_strength(1.0, 3.0, 0.5) == "strong", "저변동 raw strong → strong 유지")
# 진짜 큰 움직임(고변동에도) → strong: raw 매우 큼 + norm score 도 ≥3.5
# spread=3, chg=8, vol=2 → norm=5.5 ≥3.5, AND raw strong → strong
check(classify_strength(3.0, 8.0, 2.0) == "strong", "고변동에도 큰 breakout(norm 통과) → strong")


# ============================================================
# 3) classify_strength vol_factor 가드 (0/음수/None)
# ============================================================
print("\n=== 3) vol_factor 가드 (잘못된 값 → 1.0 폴백) ===")
check(classify_strength(1.0, 1.0, 0.0) == classify_strength(1.0, 1.0, 1.0),
      "vol=0 → 1.0 폴백 (zero-div 가드)")
check(classify_strength(1.0, 1.0, -1.0) == classify_strength(1.0, 1.0, 1.0),
      "vol=음수 → 1.0 폴백")
check(classify_strength(1.0, 1.0, None) == classify_strength(1.0, 1.0, 1.0),
      "vol=None → 1.0 폴백")


# ============================================================
# 4) compute_vol_factor — 합성 데이터
# ============================================================
print("\n=== 4) compute_vol_factor 합성 데이터 ===")
# 4-1) 빈/짧은 closes → 1.0 폴백
check(compute_vol_factor([]) == 1.0, "empty closes → 1.0")
check(compute_vol_factor([100.0]) == 1.0, "1개 close → 1.0")
check(compute_vol_factor([100.0] * VOL_WINDOW) == 1.0,
      f"{VOL_WINDOW}개(=window) closes → 1.0(window+1 미만)")

# 4-2) 상수 closes → vol=0 → 1.0 폴백
check(compute_vol_factor([100.0] * (VOL_WINDOW + 5)) == 1.0,
      "상수 closes → vol=0 → 1.0 폴백")

# 4-3) ±1% 교차 일변동 → 일수익 stdev 정확히 0.01
#   closes = [100, 101, 100, 101, ...] : 일수익 [+0.01, -0.0099, +0.01, ...]
#   pstdev 가 0.01 근처.
closes = [100.0]
for _ in range(VOL_WINDOW):
    closes.append(closes[-1] * (1.01 if len(closes) % 2 else 1 / 1.01))
vf = compute_vol_factor(closes)
expected = 0.01 / BASELINE_VOL
check(abs(vf - expected) < 0.05,
      f"±1% 교차 → vol_factor≈{expected:.3f}, 실측={vf:.3f}")

# 4-4) BASELINE_VOL 자체에 해당하는 vol 합성 → vol_factor≈1.0
# 일수익 [+BASELINE, -BASELINE, +BASELINE, ...] : pstdev = BASELINE_VOL
closes = [100.0]
for _ in range(VOL_WINDOW):
    closes.append(closes[-1] * (1 + BASELINE_VOL if len(closes) % 2 else 1 / (1 + BASELINE_VOL)))
vf = compute_vol_factor(closes)
check(abs(vf - 1.0) < 0.05,
      f"BASELINE_VOL 일변동 → vol_factor≈1.0, 실측={vf:.3f}")

# 4-5) BASELINE_VOL 의 2배 일변동 → vol_factor≈2.0 (대략, 정확히 2배 stdev → 2.0)
closes = [100.0]
high = BASELINE_VOL * 2
for _ in range(VOL_WINDOW):
    closes.append(closes[-1] * (1 + high if len(closes) % 2 else 1 / (1 + high)))
vf = compute_vol_factor(closes)
check(abs(vf - 2.0) < 0.1,
      f"2×BASELINE_VOL → vol_factor≈2.0, 실측={vf:.3f}")


# ============================================================
# 5) 통합: high-vol 합성 closes + classify_strength → weak 증가
# ============================================================
print("\n=== 5) 통합: 고변동 합성 → vol_factor>1 → 정규화 weak 변화 ===")
# 같은 spread/chg(=raw moderate) 라도 고변동 시점에서는 weak.
spread, chg = 2.0, 2.0  # raw score=4.0 → moderate (절대)
# 저변동 closes (BASELINE 절반)
calm = [100.0]
low = BASELINE_VOL * 0.5
for _ in range(VOL_WINDOW):
    calm.append(calm[-1] * (1 + low if len(calm) % 2 else 1 / (1 + low)))
# 고변동 closes (BASELINE 2배)
wild = [100.0]
hi = BASELINE_VOL * 2
for _ in range(VOL_WINDOW):
    wild.append(wild[-1] * (1 + hi if len(wild) % 2 else 1 / (1 + hi)))

vf_calm = compute_vol_factor(calm)
vf_wild = compute_vol_factor(wild)
label_calm = classify_strength(spread, chg, vf_calm)
label_wild = classify_strength(spread, chg, vf_wild)
check(vf_calm < vf_wild, f"vf_calm={vf_calm:.2f} < vf_wild={vf_wild:.2f}")
check(label_wild == "weak", f"고변동 + raw moderate → weak (실측={label_wild})")
check(label_calm in ("moderate", "strong"),
      f"저변동 + raw moderate → ≥moderate (실측={label_calm})")


# ============================================================
print(f"\n총 {_fails}건 실패")
sys.exit(1 if _fails else 0)
