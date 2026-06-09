"""signal_strength 라벨링 — 단일 진실 소스.

daily_trader.compute_trend() 와 tools/tune_thresholds.py 가 이 모듈을 공유한다
(임계값이 두 곳에 복제되어 조용히 어긋나는 드리프트를 방지).

⚠️ 이 라벨은 '추세 강도/변동성'이지 '방향(매수/매도)' 신호가 아니다.
   방향은 LLM 이 price·sma5·sma20·change_5d_pct 데이터로만 판단한다
   (근거: docs/SIGNAL_STRENGTH_ANALYSIS.md — 2년 5종목 분석에서 라벨의 방향 예측력 미관측).

임계값은 AAPL 2년 일봉 분포 기준 보정값. Phase 2 다종목 진입 시 종목별/변동성정규화
재보정 필요(종목마다 분포가 3~6배 차이 — AAPL weak ~31% vs AMD ~8%).
"""

# score = spread%(=|SMA5-SMA20|/price*100) + |5일변동%|
WEAK_SCORE_CUT = 3.5       # score < 이 값이면 weak (AAPL ~p33 → weak 약 30%)
STRONG_SPREAD_PCT = 1.0    # strong: spread% >= 이 값 AND
STRONG_CHG_PCT = 3.0       # strong: |chg%| >= 이 값


def classify_strength(spread_pct, chg_pct):
    """spread%, |chg%| 로 weak/moderate/strong 을 결정적으로 산출.

    weak     : score(=spread%+|chg%|) < WEAK_SCORE_CUT  → 횡보/저변동. LLM 에 hold 강제.
    strong   : spread% >= STRONG_SPREAD_PCT AND |chg%| >= STRONG_CHG_PCT  → 변동 큰 날.
    moderate : 그 사이.

    구 AND-gate(spread<0.3 AND chg<1.0)는 weak 이 ~1.7%만 떠 'hold 강제' 브레이크가
    死문자였음. score 기반 weak 으로 교체해 weak ~30% 정상 작동.
    """
    score = spread_pct + chg_pct
    if score < WEAK_SCORE_CUT:
        return "weak"
    if spread_pct >= STRONG_SPREAD_PCT and chg_pct >= STRONG_CHG_PCT:
        return "strong"
    return "moderate"
