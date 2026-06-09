"""signal_strength 임계값 튜닝 보조 — 읽기 전용 분석 도구.

daily_trader.compute_trend() 의 weak/moderate/strong 라벨 임계값(spread%, chg%)을
'감'이 아니라 종목 자신의 과거 분포에서 정하기 위한 분석 스크립트.

하는 일 (주문/상태 변경 일절 없음, get_daily_prices 읽기만):
  1) universe 의 각 종목에 대해 최근 일봉을 받아
  2) 매 영업일의 spread%(=|SMA5-SMA20|/price)와 |5일변동%|를 계산
  3) 그 분포(백분위)와 현재 임계값 기준 라벨 분포를 출력
  4) 라벨별 '다음날/5일 후 |수익률|' 을 같이 출력 → 라벨이 유의미한지 검증
     (weak < moderate < strong 순으로 forward 변동폭이 커져야 신호에 정보가치가 있음)

⚠️ 이 스크립트는 분석만 한다. 임계값을 실제로 바꾸려면 daily_trader.compute_trend()
   안의 값을 직접 수정해야 한다(현재 그 로직은 daily_trader 에 인라인되어 있음).
   아래 THRESHOLDS 는 '현재 운영값을 그대로 베껴 둔 것'이며, 여길 고쳐도 운영엔 영향 없음
   — 여러 후보값으로 라벨 분포가 어떻게 바뀌는지 시뮬레이션해 보는 용도.

실행 (KIS IP 화이트리스트에 등록된 환경에서):
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

# daily_trader.compute_trend() 의 현재 운영 임계값을 베껴 둔 것.
# weak    : spread < WEAK_SPREAD  AND |chg| < WEAK_CHG
# strong  : spread >= STRONG_SPREAD AND |chg| >= STRONG_CHG
# moderate: 그 외
THRESHOLDS = {
    "WEAK_SPREAD":   0.3,
    "WEAK_CHG":      1.0,
    "STRONG_SPREAD": 1.0,
    "STRONG_CHG":    3.0,
}

DEFAULT_DAYS = 100  # KIS dailyprice 는 보통 ~100 영업일까지 반환


def label(spread_pct: float, chg: float, t: dict) -> str:
    """compute_trend() 와 동일한 분기 (임계값만 인자로 받아 시뮬레이션 가능)."""
    if spread_pct < t["WEAK_SPREAD"] and chg < t["WEAK_CHG"]:
        return "weak"
    if spread_pct >= t["STRONG_SPREAD"] and chg >= t["STRONG_CHG"]:
        return "strong"
    return "moderate"


def _pct(sorted_arr: list, p: float):
    """정렬된 배열의 백분위값(p: 0~1). 빈 배열이면 None."""
    if not sorted_arr:
        return None
    idx = min(int(len(sorted_arr) * p), len(sorted_arr) - 1)
    return sorted_arr[idx]


def analyze(symbol: str, exchange: str, closes: list) -> None:
    """한 종목의 spread/chg 분포 + 라벨 분포 + forward 검증 출력."""
    if len(closes) < 26:  # SMA20 + 5일변동 + forward 여유
        print(f"\n[{symbol}] 일봉 부족({len(closes)}개) — 건너뜀")
        return

    rows = []  # (spread_pct, chg, fwd1, fwd5)
    for i in range(20, len(closes)):
        w = closes[: i + 1]
        price = w[-1]
        sma5 = sum(w[-5:]) / 5
        sma20 = sum(w[-20:]) / 20
        spread = abs(sma5 - sma20) / price * 100
        chg = abs(w[-1] / w[-6] - 1) * 100
        fwd1 = abs(closes[i + 1] / closes[i] - 1) * 100 if i + 1 < len(closes) else None
        fwd5 = abs(closes[i + 5] / closes[i] - 1) * 100 if i + 5 < len(closes) else None
        rows.append((spread, chg, fwd1, fwd5))

    spreads = sorted(r[0] for r in rows)
    chgs = sorted(r[1] for r in rows)

    print(f"\n===== {symbol} ({exchange}) — 표본 {len(rows)}일 =====")
    qs = (0.3, 0.5, 0.75, 0.9)
    print("  spread% 분포  p30/p50/p75/p90:",
          [round(_pct(spreads, q), 3) for q in qs])
    print("  |chg|%  분포  p30/p50/p75/p90:",
          [round(_pct(chgs, q), 3) for q in qs])
    print(f"  → weak 상한 후보 = spread p30 {_pct(spreads, 0.3):.3f} / chg p30 {_pct(chgs, 0.3):.3f}")
    print(f"  → strong 하한 후보 = spread p75 {_pct(spreads, 0.75):.3f} / chg p75 {_pct(chgs, 0.75):.3f}")

    # 현재 임계값 기준 라벨 분포 + forward 검증
    buckets = defaultdict(lambda: {"n": 0, "fwd1": [], "fwd5": []})
    for spread, chg, fwd1, fwd5 in rows:
        lab = label(spread, chg, THRESHOLDS)
        b = buckets[lab]
        b["n"] += 1
        if fwd1 is not None:
            b["fwd1"].append(fwd1)
        if fwd5 is not None:
            b["fwd5"].append(fwd5)

    print(f"  현재 임계값 {THRESHOLDS} 기준 라벨 분포 / forward |수익률|:")
    total = len(rows)
    for lab in ("weak", "moderate", "strong"):
        b = buckets[lab]
        n = b["n"]
        share = n / total * 100 if total else 0
        f1 = f"{st.mean(b['fwd1']):.2f}%" if b["fwd1"] else "  -  "
        f5 = f"{st.mean(b['fwd5']):.2f}%" if b["fwd5"] else "  -  "
        print(f"    {lab:8} {n:4d}일 ({share:4.1f}%)   다음날 {f1}   5일후 {f5}")
    print("  ※ weak < moderate < strong 순으로 forward 변동폭이 커지면 라벨이 유의미.")
    print("    역전/유사하면 임계값이 아니라 신호 설계를 재검토.")


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
