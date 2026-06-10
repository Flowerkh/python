"""signal_strength 라벨링 — 단일 진실 소스.

daily_trader.compute_trend() 와 tools/tune_thresholds.py 가 이 모듈을 공유한다
(임계값이 두 곳에 복제되어 조용히 어긋나는 드리프트를 방지).

⚠️ 이 라벨은 '추세 강도/변동성'이지 '방향(매수/매도)' 신호가 아니다.
   방향은 LLM 이 price·sma5·sma20·change_5d_pct 데이터로만 판단한다
   (근거: docs/SIGNAL_STRENGTH_ANALYSIS.md — 2년 5종목 분석에서 라벨의 방향 예측력 미관측).

P2 정규화 (2026-06-10):
   WEAK_SCORE_CUT 은 절대값이 아니라 종목 자체 변동성 기준으로 적용한다.
   normalized_score = (spread% + |chg5%|) / vol_factor
   vol_factor = trailing_20d_daily_return_stdev / BASELINE_VOL
   → AAPL(저변동) vol_factor≈1.0 = 현행 동작 거의 보존, 고변동 종목(AMD/INTC 등) vol_factor≈2~3
     → score 분모 커져 weak 발동률이 ~30% 균일 수렴(측정: docs/SIGNAL_STRENGTH_ANALYSIS.md P2 절).
   Strong AND-gate 는 raw 유지 — 별도 측정 알파 없음, Phase 2 진입 시 재검토.
"""
import statistics as _st

# score = spread%(=|SMA5-SMA20|/price*100) + |5일변동%|
WEAK_SCORE_CUT = 3.5       # normalized score < 이 값이면 weak (AAPL ~p33 → weak ~30%)
STRONG_SPREAD_PCT = 1.0    # strong: spread% >= 이 값 AND
STRONG_CHG_PCT = 3.0       # strong: |chg%| >= 이 값

# P2: 종목별 vol 정규화 기준점. AAPL 2년 trailing 20d daily-return stdev p50≈0.0144 → round 0.015.
# 측정: tools/vol_calibration.py 의 BASELINE_VOL=0.015 케이스 — 종목 가로 weak 26~39% 수렴
# (정규화 전 7.9~31.2%, ~2배 균일화). 근거: docs/SIGNAL_STRENGTH_ANALYSIS.md P2 절.
BASELINE_VOL = 0.015
VOL_WINDOW = 20  # 트레일링 일수익 stdev 윈도 (영업일)


def compute_vol_factor(closes, window=VOL_WINDOW):
    """트레일링 window일 daily-return stdev / BASELINE_VOL.

    AAPL 평균 vol_factor ≈ 1.0(BASELINE_VOL=AAPL p50 vol). 고변동 종목은 >1.
    데이터 부족(window+1 미만) 시 1.0 으로 폴백 — 정규화 미적용(보수, 현행 동작).
    zero-vol 가드 포함(드물지만 결정성 보장).
    """
    if not closes or len(closes) < window + 1:
        return 1.0
    tail = closes[-(window + 1):]
    rets = [tail[i] / tail[i - 1] - 1 for i in range(1, len(tail))]
    vol = _st.pstdev(rets)
    if vol < 1e-9:
        return 1.0
    return vol / BASELINE_VOL


def classify_strength(spread_pct, chg_pct, vol_factor=1.0):
    """spread%, |chg%|, vol_factor 로 weak/moderate/strong 을 결정적으로 산출.

    판정 순서(weak 가 우선):
      weak     : normalized_score(=(spread%+|chg%|)/vol_factor) < WEAK_SCORE_CUT
                 → 종목 자체 변동성 대비 작은 움직임. LLM 에 hold 강제.
      strong   : spread% >= STRONG_SPREAD_PCT AND |chg%| >= STRONG_CHG_PCT
                 (그리고 위 weak 가 아님 — norm score ≥ WEAK_SCORE_CUT).
                 raw spread/chg 가 절대 임계를 넘고 *동시에* norm score 가 정규화 통과해야 strong.
      moderate : 그 사이.

    설계 의도: 고변동 종목(예: AMD vol_factor≈2)에서 raw strong 조건(spread≥1 & chg≥3) 만족이라도
    norm score 가 낮으면 weak — "큰 종목 기준 평범한 움직임" 으로 판단해 throttle. AMD strong 과발동
    (이전 ~64%) 도 weak normalization 이 함께 해소.

    vol_factor=1.0 (기본) 이면 P1 까지의 동작과 동일 — 호출처 미수정 시 회귀 0.
    """
    if vol_factor is None or vol_factor <= 0:
        vol_factor = 1.0
    score = (spread_pct + chg_pct) / vol_factor
    if score < WEAK_SCORE_CUT:
        return "weak"
    if spread_pct >= STRONG_SPREAD_PCT and chg_pct >= STRONG_CHG_PCT:
        return "strong"
    return "moderate"
