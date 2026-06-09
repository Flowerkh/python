"""signal_strength 임계값 튜닝 보조 — 읽기 전용 분석 도구.

daily_trader.compute_trend() 의 weak/moderate/strong 라벨 임계값을 '감'이 아니라
종목 자신의 과거 분포에서 정하고, 그 라벨이 '방향 예측력'을 갖는지 검증한다.

하는 일 (주문/상태 변경 일절 없음, get_daily_prices 읽기만):
  1) universe 각 종목의 최근 일봉을 받아 매 영업일의
     spread%(=|SMA5-SMA20|/price), |5일변동%|, 추세방향(SMA5≷SMA20), forward 수익률 계산
  2) spread/chg/score 분포(백분위) 출력 → 임계값 재스케일 근거
  3) 두 가지 라벨링 방식을 나란히 비교:
       (A) AND-gate (현행): spread/chg 두 값을 각각 문턱으로 자름
       (B) score 모드: score = spread + W·chg 한 값의 백분위로 자름 (AND 경계 문제 없음)
  4) 각 방식에 대해 'directional 검증' 출력:
       - 방향일치 수익률 = 추세방향 × forward 수익률(부호 유지).
         추세가 그 방향으로 이어졌으면 +, 되돌렸으면 −.
       - 적중률 = 방향일치 수익률 > 0 인 날 비율.
     강한 라벨일수록 방향일치 평균↑ 이고 적중률>50% 면 추세지속 신호로 유효.
     적중률이 ~50% 면 방향 예측력 없음 → 임계값이 아니라 신호 설계를 재검토.

  ⚠️ |수익률|(변동 크기)이 아니라 부호 있는 방향일치 수익률을 본다. signal_strength 는
     '추세 방향 확신'을 위한 라벨이므로, 변동성이 아니라 방향이 맞았는지가 진짜 검증이다.

⚠️ 이 스크립트는 분석/시뮬레이션만 한다. 실제 운영 라벨은 daily_trader.compute_trend()
   안에 인라인된 AND-gate 로직이다. 아래 상수는 그 값을 베껴 둔 것 + score 모드 파라미터이며,
   여길 고쳐도 운영엔 영향 없음 — 후보값으로 분포/검증이 어떻게 바뀌는지 보는 용도.

실행 (KIS IP 화이트리스트 등록 환경 = 서버 권장):
  .venv/bin/python tools/tune_thresholds.py
  .venv/bin/python tools/tune_thresholds.py AAPL          # 특정 종목만
  .venv/bin/python tools/tune_thresholds.py AAPL 120      # 일봉 일수 지정
"""
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

# tools/ 하위에서 실행되어도 kis 패키지를 찾을 수 있도록 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kis import universe
from kis.client import KISClient

# ── (A) AND-gate: daily_trader.compute_trend() 현재 운영값을 베껴 둔 것 ──
#   weak    : spread < WEAK_SPREAD  AND |chg| < WEAK_CHG
#   strong  : spread >= STRONG_SPREAD AND |chg| >= STRONG_CHG
#   moderate: 그 외
THRESHOLDS = {
    "WEAK_SPREAD":   0.3,
    "WEAK_CHG":      1.0,
    "STRONG_SPREAD": 1.0,
    "STRONG_CHG":    3.0,
}

# ── (B) score 모드 파라미터 ──
#   score = spread% + SCORE_CHG_WEIGHT · |chg%|
#   weak   = score < p[SCORE_WEAK_PCTL],  strong = score >= p[SCORE_STRONG_PCTL]
#   경계가 1차원이라 백분위 2개만 잡으면 됨 (AND/OR 경계 문제 없음).
SCORE_CHG_WEIGHT = 1.0
SCORE_WEAK_PCTL = 0.33    # 하위 33% → weak
SCORE_STRONG_PCTL = 0.66  # 상위 34% → strong

DEFAULT_DAYS = 100  # KIS dailyprice 는 보통 ~100 영업일까지 반환
_LABELS = ("weak", "moderate", "strong")


def _pct(sorted_arr: list, p: float):
    """정렬된 배열의 백분위값(p: 0~1). 빈 배열이면 None."""
    if not sorted_arr:
        return None
    idx = min(int(len(sorted_arr) * p), len(sorted_arr) - 1)
    return sorted_arr[idx]


def build_rows(closes: list) -> list:
    """매 영업일의 지표 + forward(부호) 수익률을 dict 리스트로."""
    rows = []
    for i in range(20, len(closes)):
        w = closes[: i + 1]
        price = w[-1]
        sma5 = sum(w[-5:]) / 5
        sma20 = sum(w[-20:]) / 20
        spread = abs(sma5 - sma20) / price * 100
        chg = abs(w[-1] / w[-6] - 1) * 100
        direction = 1.0 if sma5 >= sma20 else -1.0  # 추세 방향
        score = spread + SCORE_CHG_WEIGHT * chg
        # forward 수익률(부호 유지)
        sf1 = (closes[i + 1] / closes[i] - 1) * 100 if i + 1 < len(closes) else None
        sf5 = (closes[i + 5] / closes[i] - 1) * 100 if i + 5 < len(closes) else None
        rows.append({"spread": spread, "chg": chg, "direction": direction,
                     "score": score, "sf1": sf1, "sf5": sf5})
    return rows


def label_andgate(r: dict, t: dict) -> str:
    """(A) compute_trend() 와 동일한 AND-gate 분기."""
    if r["spread"] < t["WEAK_SPREAD"] and r["chg"] < t["WEAK_CHG"]:
        return "weak"
    if r["spread"] >= t["STRONG_SPREAD"] and r["chg"] >= t["STRONG_CHG"]:
        return "strong"
    return "moderate"


def make_label_score(rows: list):
    """(B) score 백분위 컷으로 라벨링하는 함수 + 컷값 반환."""
    scores = sorted(r["score"] for r in rows)
    lo = _pct(scores, SCORE_WEAK_PCTL)
    hi = _pct(scores, SCORE_STRONG_PCTL)

    def fn(r: dict) -> str:
        if r["score"] < lo:
            return "weak"
        if r["score"] >= hi:
            return "strong"
        return "moderate"

    return fn, lo, hi


def directional_report(title: str, rows: list, label_fn) -> None:
    """라벨별 분포 + 방향일치 수익률(부호) + 적중률 출력."""
    buckets = defaultdict(lambda: {"n": 0, "ta1": [], "ta5": [], "hit5": []})
    for r in rows:
        b = buckets[label_fn(r)]
        b["n"] += 1
        if r["sf1"] is not None:
            b["ta1"].append(r["direction"] * r["sf1"])
        if r["sf5"] is not None:
            ta5 = r["direction"] * r["sf5"]
            b["ta5"].append(ta5)
            b["hit5"].append(1 if ta5 > 0 else 0)

    total = len(rows)
    print(f"  [{title}]")
    print(f"    {'라벨':8} {'일수':>10}   {'1d방향일치':>10}   {'5d방향일치':>10}   {'5d적중률':>8}")
    for lab in _LABELS:
        b = buckets[lab]
        n = b["n"]
        share = n / total * 100 if total else 0
        ta1 = f"{st.mean(b['ta1']):+.2f}%" if b["ta1"] else "  -  "
        ta5 = f"{st.mean(b['ta5']):+.2f}%" if b["ta5"] else "  -  "
        hit5 = f"{st.mean(b['hit5']) * 100:.0f}%" if b["hit5"] else " - "
        print(f"    {lab:8} {n:4d}일({share:4.1f}%)   {ta1:>10}   {ta5:>10}   {hit5:>8}")


def analyze(symbol: str, exchange: str, closes: list) -> None:
    """한 종목: 분포 + (A)AND-gate / (B)score 두 방식의 directional 검증."""
    if len(closes) < 26:  # SMA20 + 5일변동 + forward 여유
        print(f"\n[{symbol}] 일봉 부족({len(closes)}개) — 건너뜀")
        return

    rows = build_rows(closes)
    spreads = sorted(r["spread"] for r in rows)
    chgs = sorted(r["chg"] for r in rows)
    scores = sorted(r["score"] for r in rows)
    qs = (0.3, 0.5, 0.75, 0.9)

    print(f"\n===== {symbol} ({exchange}) — 표본 {len(rows)}일 =====")
    print("  분포(p30/p50/p75/p90):")
    print("    spread%:", [round(_pct(spreads, q), 3) for q in qs])
    print("    |chg|% :", [round(_pct(chgs, q), 3) for q in qs])
    print("    score  :", [round(_pct(scores, q), 3) for q in qs],
          f"(=spread+{SCORE_CHG_WEIGHT}·chg)")

    # (A) 현행 AND-gate
    sf, lo, hi = make_label_score(rows)
    print()
    directional_report(f"A. AND-gate 현행 {THRESHOLDS}",
                       rows, lambda r: label_andgate(r, THRESHOLDS))
    print()
    directional_report(f"B. score 모드  weak<{lo:.2f} / strong>={hi:.2f} "
                       f"(p{int(SCORE_WEAK_PCTL*100)}/p{int(SCORE_STRONG_PCTL*100)})",
                       rows, sf)

    print("  ※ 해석: 강한 라벨일수록 방향일치 평균↑ 이고 적중률>50% 면 추세지속 신호로 유효.")
    print("    strong 적중률이 ~50%(동전던지기)거나 weak보다 낮으면 방향 예측력 없음")
    print("    → 임계값이 아니라 신호 설계(다른 지표/LLM 비중)를 재검토.")


def main():
    argv = sys.argv[1:]
    only_symbol = None
    days = DEFAULT_DAYS
    for a in argv:
        if a.isdigit():
            days = int(a)
        else:
            only_symbol = a.upper()

    syms = universe.list_all()
    if only_symbol:
        syms = [s for s in syms if s.symbol == only_symbol]
        if not syms:
            raise SystemExit(f"'{only_symbol}' 은 universe 화이트리스트에 없음. "
                             f"가능: {[s.symbol for s in universe.list_all()]}")

    print(f"signal_strength 임계값 튜닝 분석 — 종목 {len(syms)}개, 일봉 {days}일")
    client = KISClient()
    for s in syms:
        try:
            closes = client.get_daily_prices(s.symbol, s.exchange, days=days)
            analyze(s.symbol, s.exchange, closes)
        except Exception as e:
            print(f"\n[{s.symbol}] 조회 실패: {type(e).__name__}: {e}")
            print("  (KIS IP 화이트리스트 미등록 환경이면 여기서 막힐 수 있음 — 서버에서 실행 권장)")


if __name__ == "__main__":
    main()
