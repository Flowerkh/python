"""flipped_day_pnl.py — P1-후속: weak 라벨 개편이 forward P&L 에 미친 영향 측정.

배경:
  `kis/signals.py` 의 weak 판정이 구 AND-gate(spread<0.3 AND chg<1.0) →
  신 score-gate(score=spread%+|chg5%| < 3.5) 로 바뀌었다(2026-06-09 커밋 809967e).
  P1 백테스트(2026-06-10) 의 0/480 항등식 한계 — 진입 트리거가 두 룰에서 동일(strong&up)
  이라 '실제 라벨이 바뀐 날의 P&L' 을 직접 측정 못 했다.
  → 본 스크립트는 라벨이 OLD≠NEW 인 flipped 일자만 떼서 forward P&L 을 잰다.
  부가: '보유 롱을 strong-하락에 청산(구 프롬프트 넛지) vs 유지(신)' 누적 P&L 시뮬.

수학:
  OLD weak ⊂ NEW weak (spread<0.3 AND chg<1 → score<1.3<3.5). strong 정의 불변.
  따라서 flip 방향은 OLD=moderate → NEW=weak 단일(코드 assert).

판정:
  direction = +1 if sma5>=sma20 else -1.  uptrend 가 long-only 매수 후보.
  forward 수익률은 '부호 유지'(signed). long-only 가정.

⚠️ proxy 한계: 실제 LLM 판단을 재현 안 함 — 'label≠weak AND direction=up' 을
   BUY 후보로 근사. 라벨 변경의 LLM-confidence 영향은 별도 백테스트가 필요.
⚠️ 상승장 편향: 2년창 5종목 모두 양전. 검정력 부족. 5bps 슬리피지/세금 미반영.
⚠️ 교차종목 상관(P1 측정 ρ̄≈0.42, VIF≈2.67) 비보정 → 집계 SE 과소평가.

실행: python tools/flipped_day_pnl.py
"""
import json
import statistics as st
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

# Windows cp949 콘솔에서 em-dash 등 깨지는 거 방지 (PowerShell 한글 환경 대응)
if hasattr(sys.stdout, "reconfigure") and (sys.stdout.encoding or "").lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kis.signals import classify_strength  # NEW (score-gate)

SYMBOLS = ("AAPL", "NVDA", "AMD", "TSM", "INTC")
RANGE = "2y"


def classify_old(spread_pct: float, chg_pct: float) -> str:
    """구 AND-gate weak — kis/signals.py 도입 전 daily_trader.compute_trend 산식."""
    if spread_pct < 0.3 and chg_pct < 1.0:
        return "weak"
    if spread_pct >= 1.0 and chg_pct >= 3.0:
        return "strong"
    return "moderate"


def fetch_yahoo_closes(symbol: str, rng: str = RANGE) -> list[float]:
    """Yahoo chart API → 시간순 종가 리스트(None 제거)."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={rng}&interval=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.load(r)
    result = data["chart"]["result"][0]
    closes = result["indicators"]["quote"][0]["close"]
    return [c for c in closes if c is not None]


def build_rows(closes: list[float]) -> list[dict]:
    """매 영업일 라벨(OLD/NEW) + direction + forward 1d/5d 수익률."""
    rows = []
    n = len(closes)
    for i in range(20, n):
        w = closes[: i + 1]
        price = w[-1]
        sma5 = sum(w[-5:]) / 5
        sma20 = sum(w[-20:]) / 20
        spread = abs(sma5 - sma20) / price * 100
        chg = abs(w[-1] / w[-6] - 1) * 100
        direction = 1 if sma5 >= sma20 else -1
        old = classify_old(spread, chg)
        new = classify_strength(spread, chg)
        ret1 = (closes[i + 1] / price - 1) * 100 if i + 1 < n else None
        ret5 = (closes[i + 5] / price - 1) * 100 if i + 5 < n else None
        rows.append({"i": i, "spread": spread, "chg": chg, "direction": direction,
                     "old": old, "new": new, "ret1": ret1, "ret5": ret5})
    return rows


def stats(samples: list[float]) -> dict | None:
    if not samples:
        return None
    n = len(samples)
    m = st.mean(samples)
    sd = st.pstdev(samples) if n > 1 else 0.0
    se = sd / (n ** 0.5) if n > 1 else 0.0
    t = m / se if se > 0 else 0.0
    hit = sum(1 for x in samples if x > 0) / n * 100
    return {"n": n, "mean": m, "std": sd, "t": t, "hit": hit}


def fmt_stats(s: dict | None, key: str = "5d") -> str:
    if not s:
        return "    데이터 부족"
    return (f"n={s['n']:4d}  {key}: mean={s['mean']:+.3f}%  std={s['std']:.2f}  "
            f"t={s['t']:+.2f}  hit>0={s['hit']:.0f}%")


def report_per_symbol(sym: str, rows: list[dict]) -> None:
    n = len(rows)
    old_w = sum(1 for r in rows if r["old"] == "weak")
    new_w = sum(1 for r in rows if r["new"] == "weak")
    flipped = [r for r in rows if r["old"] != r["new"]]
    # 수학적 보증: 모든 flip 은 OLD=moderate → NEW=weak.
    bad = [r for r in flipped if not (r["old"] == "moderate" and r["new"] == "weak")]
    assert not bad, f"예상치 못한 flip 방향: {bad[:3]}"

    print(f"\n--- {sym} ({n}일) ---")
    print(f"  OLD weak 발동: {old_w:3d}/{n} ({old_w/n*100:.1f}%)  "
          f"NEW weak 발동: {new_w:3d}/{n} ({new_w/n*100:.1f}%)  "
          f"flipped: {len(flipped):3d} ({len(flipped)/n*100:.1f}%)")

    up = [r for r in flipped if r["direction"] == 1]
    dn = [r for r in flipped if r["direction"] == -1]
    for label, group in (("flipped ALL    ", flipped),
                          ("flipped uptrend", up),
                          ("flipped dntrend", dn)):
        s5 = stats([r["ret5"] for r in group if r["ret5"] is not None])
        print(f"    {label}  {fmt_stats(s5)}")

    # strong-down sim
    if rows:
        start, end = rows[0]["i"], rows[-1]["i"]
        # buy&hold (시작~끝 종가 수익률)
        hold_ret = None  # 계산은 main 에서 closes 들고 함; 여긴 카운트만
    sd_count = sum(1 for r in rows if r["new"] == "strong" and r["direction"] == -1)
    print(f"  strong-down 일수: {sd_count}/{n} ({sd_count/n*100:.1f}%)")


def simulate_strong_down_exit(closes: list[float], rows: list[dict]) -> dict:
    """HOLD(buy&hold) vs EXIT-on-strong-down 누적 수익률.

    EXIT 전략: 오늘 close 라벨이 strong-down(spread≥1.0 & chg≥3.0 & sma5<sma20)이면
    다음 1영업일 flat (close-to-close 수익률 미캡처). 그 외엔 보유. 마찰비용 0(보수).
    재진입: 다음날 라벨이 strong-down 아니면 자동 보유 → close-to-close 캡처.
    look-ahead 없음(오늘 close 정보로 다음 close 까지 의사결정).
    """
    if len(rows) < 2:
        return {}
    start_idx = rows[0]["i"]
    end_idx = rows[-1]["i"]
    initial = closes[start_idx]
    final = closes[end_idx]
    hold_ret = (final / initial - 1) * 100

    pnl_cum = 1.0
    flat_days = 0
    for k in range(len(rows) - 1):
        r = rows[k]
        next_i = rows[k + 1]["i"]
        ret_mul = closes[next_i] / closes[r["i"]]
        is_strong_down = (r["new"] == "strong" and r["direction"] == -1)
        if is_strong_down:
            flat_days += 1
        else:
            pnl_cum *= ret_mul
    exit_ret = (pnl_cum - 1) * 100
    return {"hold": hold_ret, "exit": exit_ret, "flat_days": flat_days,
            "total_days": len(rows) - 1}


def aggregate(per_symbol_rows: dict[str, list[dict]],
              per_symbol_closes: dict[str, list[float]]) -> None:
    print("\n" + "=" * 60)
    print("전체 5종목 집계")
    print("=" * 60)
    all_rows = []
    for rs in per_symbol_rows.values():
        all_rows.extend(rs)

    n = len(all_rows)
    old_w = sum(1 for r in all_rows if r["old"] == "weak")
    new_w = sum(1 for r in all_rows if r["new"] == "weak")
    flipped = [r for r in all_rows if r["old"] != r["new"]]
    print(f"\n표본: {n}일 (5종목 합산)")
    print(f"OLD weak 발동률: {old_w}/{n} ({old_w/n*100:.1f}%)")
    print(f"NEW weak 발동률: {new_w}/{n} ({new_w/n*100:.1f}%)")
    print(f"Flipped(OLD=moderate→NEW=weak): {len(flipped)}/{n} ({len(flipped)/n*100:.1f}%)")

    print("\n[Flipped 일 forward 5d 수익률 — signed long-only]")
    up = [r for r in flipped if r["direction"] == 1]
    dn = [r for r in flipped if r["direction"] == -1]
    for label, group in (("ALL              ", flipped),
                          ("uptrend(BUY후보) ", up),
                          ("downtrend         ", dn)):
        s5 = stats([r["ret5"] for r in group if r["ret5"] is not None])
        print(f"  {label}  {fmt_stats(s5)}")

    # 비교: non-flipped 일 (= OLD/NEW 라벨 같음) 의 동일 지표
    non_flipped = [r for r in all_rows if r["old"] == r["new"]]
    non_up = [r for r in non_flipped if r["direction"] == 1]
    print("\n[비교: Non-flipped 일 forward 5d 수익률]")
    for label, group in (("ALL              ", non_flipped),
                          ("uptrend          ", non_up)):
        s5 = stats([r["ret5"] for r in group if r["ret5"] is not None])
        print(f"  {label}  {fmt_stats(s5)}")

    # 부분군: flipped uptrend 의 ret1 도(짧은 forward)
    print("\n[Flipped uptrend forward 1d 수익률 — 즉시 다음날]")
    s1 = stats([r["ret1"] for r in up if r["ret1"] is not None])
    print(f"  uptrend 1d  {fmt_stats(s1, '1d')}")

    # Strong-down 시뮬 종목별 + 합산
    print("\n[Strong-down 청산 시뮬 — OLD 프롬프트(매도 넛지) 흉내 vs NEW(보유)]")
    print(f"  {'종목':6} {'기간일수':>8} {'flat일':>7} {'HOLD':>9} {'EXIT':>9} {'Δ(EXIT-HOLD)':>14}")
    diffs = []
    for sym in per_symbol_rows:
        r = simulate_strong_down_exit(per_symbol_closes[sym], per_symbol_rows[sym])
        if not r:
            continue
        diffs.append(r["exit"] - r["hold"])
        print(f"  {sym:6} {r['total_days']:>8d} {r['flat_days']:>7d}  "
              f"{r['hold']:+8.2f}% {r['exit']:+8.2f}%  {r['exit']-r['hold']:+12.2f}%p")
    if diffs:
        print(f"  {'평균Δ':6} {'':>8} {'':>7} {'':>9} {'':>9}  {st.mean(diffs):+12.2f}%p")

    print("\n[해석 가이드]")
    print("  - Flipped uptrend 5d mean ≈ 0 + |t|<2  → 신 weak 룰이 trade 차단해도 P&L 영향 미미(throttle)")
    print("  - mean > 0, t > 2 → 신 룰이 winning BUY 막아 손해(알파 손실 = 룰 후퇴)")
    print("  - mean < 0, t < −2 → 신 룰이 losing BUY 막아 보호(실제 방어 알파)")
    print("  - Strong-down EXIT 평균Δ > 0 → 구 프롬프트 넛지(매도) 가 보호적 → 넛지 제거는 후퇴")
    print("  - 평균Δ < 0 → 넛지 제거(NEW) 가 더 나음. ≈0 이면 무관(=종전 P1c 결론과 일관).")
    print("  - long-only 가정, 마찰비용 0, 2년 상승장 편향. P1e 한계 그대로 적용.")


def main():
    print(f"[flipped_day_pnl] signal_strength 개편 라벨 flipped-day P&L 분석")
    print(f"  종목 {len(SYMBOLS)}개 ({', '.join(SYMBOLS)}), range={RANGE}, "
          f"fetch={datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("  (Yahoo 일봉 fetch, KIS API 미사용. 분석/시뮬만, 주문/상태 변경 0)")

    per_symbol_rows: dict[str, list[dict]] = {}
    per_symbol_closes: dict[str, list[float]] = {}
    for sym in SYMBOLS:
        try:
            closes = fetch_yahoo_closes(sym)
        except Exception as e:
            print(f"\n[{sym}] fetch 실패: {type(e).__name__}: {e}")
            continue
        if len(closes) < 30:
            print(f"\n[{sym}] 데이터 부족 ({len(closes)}일)")
            continue
        rows = build_rows(closes)
        if not rows:
            continue
        per_symbol_rows[sym] = rows
        per_symbol_closes[sym] = closes
        report_per_symbol(sym, rows)

    if per_symbol_rows:
        aggregate(per_symbol_rows, per_symbol_closes)
    else:
        print("\n표본 없음 — 모든 종목 fetch 실패. 네트워크/Yahoo 접근 확인.")


if __name__ == "__main__":
    main()
