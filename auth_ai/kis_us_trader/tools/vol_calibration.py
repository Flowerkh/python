"""vol_calibration.py — P2 사전: BASELINE_VOL 후보 측정 + 종목별 weak 균일화 시뮬.

배경:
  현행 `WEAK_SCORE_CUT=3.5` 는 AAPL 일봉 분포 기준으로 정한 값.
  P1-후속 측정으로 종목별 NEW weak 발동률이 AAPL 31% vs AMD 8% 로 6배 차이남이 확인됨.
  → score 를 종목 자체 변동성으로 정규화하면 단일 cut 으로 종목 가로질러 ~균일 발동.

수식 후보:
  vol_proxy(s) = stdev(daily_return) — 트레일링 20영업일
  vol_factor(s) = vol_proxy(s) / BASELINE_VOL
  normalized_score = (spread% + |chg5%|) / vol_factor(s)
  weak = normalized_score < WEAK_SCORE_CUT

  BASELINE_VOL 선택 기준:
    (a) AAPL vol_factor ≈ 1.0 이도록 → 현행 AAPL 동작 보존
    (b) 비-AAPL 종목들의 normalized weak 발동률이 AAPL(~30%) 근처로 균일

이 도구는 BASELINE_VOL ∈ {여러 후보} 에 대해 per-symbol weak 발동률을 계산해
적정값을 데이터 기반으로 추천한다. 코드 변경/주문 없음.

실행: python tools/vol_calibration.py
"""
import json
import statistics as st
import sys
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure") and (sys.stdout.encoding or "").lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kis.signals import STRONG_CHG_PCT, STRONG_SPREAD_PCT, WEAK_SCORE_CUT

SYMBOLS = ("AAPL", "NVDA", "AMD", "TSM", "INTC")
VOL_WINDOW = 20  # trailing 20 영업일 daily-return stdev
BASELINE_CANDIDATES = (0.012, 0.015, 0.018, 0.020, 0.025)


def fetch_closes(symbol: str) -> list[float]:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=2y&interval=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.load(r)
    closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
    return [c for c in closes if c is not None]


def daily_returns(closes: list[float]) -> list[float]:
    return [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]


def build_rows(closes: list[float]) -> list[dict]:
    """매일 spread%, |chg5%|, trailing20d 일수익 stdev."""
    rows = []
    rets = daily_returns(closes)
    # rets[i] = closes[i+1]/closes[i] - 1  → 즉 closes index i+1 의 일수익
    # rows i 는 closes[i] 시점 — vol_window 만큼의 과거 rets 가 필요
    for i in range(max(20, VOL_WINDOW + 1), len(closes)):
        w = closes[: i + 1]
        price = w[-1]
        sma5 = sum(w[-5:]) / 5
        sma20 = sum(w[-20:]) / 20
        spread = abs(sma5 - sma20) / price * 100
        chg = abs(w[-1] / w[-6] - 1) * 100
        # 과거 20개 일수익 (closes[i-19]..closes[i] 사이 변화 = rets[i-20]..rets[i-1])
        vol_rets = rets[i - VOL_WINDOW: i]
        vol = st.pstdev(vol_rets) if len(vol_rets) > 1 else 0.0
        rows.append({"spread": spread, "chg": chg, "vol": vol})
    return rows


def weak_rate(rows: list[dict], baseline: float) -> tuple[int, int]:
    """주어진 BASELINE_VOL 로 normalized_score 적용 시 weak 발동 카운트."""
    weak = 0
    for r in rows:
        vol_factor = r["vol"] / baseline if baseline > 0 else 1.0
        if vol_factor < 1e-9:
            vol_factor = 1.0  # 0 vol 가드(드물지만 결정성 보장)
        normalized = (r["spread"] + r["chg"]) / vol_factor
        if normalized < WEAK_SCORE_CUT:
            weak += 1
    return weak, len(rows)


def weak_rate_current(rows: list[dict]) -> tuple[int, int]:
    """현행(절대 score) weak 발동률 — 비교용."""
    weak = sum(1 for r in rows if r["spread"] + r["chg"] < WEAK_SCORE_CUT)
    return weak, len(rows)


def main():
    print(f"[vol_calibration] BASELINE_VOL 후보 sweep — VOL_WINDOW={VOL_WINDOW}일")
    print(f"  종목 {SYMBOLS}, 현행 WEAK_SCORE_CUT={WEAK_SCORE_CUT}")
    print(f"  목표: AAPL vol_factor≈1.0(AAPL 동작 보존) + 종목별 weak 발동률 ~30% 균일\n")

    per_symbol: dict[str, list[dict]] = {}
    for sym in SYMBOLS:
        try:
            closes = fetch_closes(sym)
        except Exception as e:
            print(f"[{sym}] fetch 실패: {type(e).__name__}: {e}")
            continue
        if len(closes) < 30:
            print(f"[{sym}] 데이터 부족")
            continue
        per_symbol[sym] = build_rows(closes)

    if not per_symbol:
        print("표본 없음")
        return

    # 1) 종목별 트레일링 vol 분포
    print("=" * 64)
    print("1) 종목별 trailing 20d vol(daily return stdev) 분포")
    print("=" * 64)
    print(f"  {'종목':6} {'n':>5} {'mean':>8} {'p25':>8} {'p50':>8} {'p75':>8} {'p90':>8}")
    vol_means = {}
    for sym, rows in per_symbol.items():
        vols = sorted(r["vol"] for r in rows)
        n = len(vols)
        m = st.mean(vols)
        vol_means[sym] = m
        p = lambda q: vols[min(int(n * q), n - 1)] if vols else 0.0
        print(f"  {sym:6} {n:>5d} {m:>7.4f} {p(0.25):>7.4f} {p(0.50):>7.4f} {p(0.75):>7.4f} {p(0.90):>7.4f}")

    # 2) 현행 절대 score 의 종목별 weak 발동률 (재확인)
    print()
    print("=" * 64)
    print("2) 현행(절대 score) weak 발동률 — 정규화 전 베이스라인")
    print("=" * 64)
    for sym, rows in per_symbol.items():
        w, n = weak_rate_current(rows)
        print(f"  {sym:6} weak {w:>4d}/{n} ({w/n*100:>5.1f}%)")

    # 3) BASELINE_VOL 후보별 normalized weak 발동률
    print()
    print("=" * 64)
    print("3) BASELINE_VOL 후보 sweep — normalized weak 발동률(%)")
    print("=" * 64)
    header = "  종목      " + "".join(f" BASELINE={b:.3f}" for b in BASELINE_CANDIDATES)
    print(header)
    for sym, rows in per_symbol.items():
        line = f"  {sym:6}    "
        for b in BASELINE_CANDIDATES:
            w, n = weak_rate(rows, b)
            line += f"      {w/n*100:>5.1f}%   "
        print(line)

    # 4) 추천: AAPL vol_factor 평균이 ~1.0 이도록 — AAPL 평균 vol
    aapl_vol = vol_means.get("AAPL")
    if aapl_vol:
        print()
        print("=" * 64)
        print(f"4) 추천 BASELINE_VOL = AAPL 평균 trailing vol = {aapl_vol:.4f}")
        print("=" * 64)
        print(f"  (AAPL vol_factor 평균 = 1.0 → AAPL 현행 weak 발동률 동일하게 보존)")
        print(f"  이 값으로 normalized 시:")
        for sym, rows in per_symbol.items():
            w, n = weak_rate(rows, aapl_vol)
            current_w, _ = weak_rate_current(rows)
            sym_vol = vol_means[sym]
            vol_factor = sym_vol / aapl_vol
            print(f"    {sym:6} 평균 vol_factor={vol_factor:>4.2f}  "
                  f"현행 {current_w/n*100:>5.1f}% → normalized {w/n*100:>5.1f}%")


if __name__ == "__main__":
    main()
