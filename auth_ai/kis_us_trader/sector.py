"""섹터 매크로 편향(macro_bias) — 코드가 산출하는 결정적 라벨.

Phase 2: 반도체 섹터의 '위험선호(risk_on)/중립(neutral)/위험회피(risk_off)' 국면을
SMH ETF(반도체 대표 ETF) 추세 + 유니버스 breadth(SMA20 상회 비율)로 결정적으로 라벨링한다.

설계 철학(CLAUDE.md): **추세/국면 계산은 코드가, 해석/판단은 LLM이.**
  - macro_bias 는 코드가 만든 '사실 블록'이며, LLM 프롬프트에 그대로 주입된다(LLM 이 자유롭게
    국면을 추정하지 않음 — 환각 표면적 최소화).
  - daily_trader 는 이 라벨로 그날 매수 종목 수 N 의 상한을 정한다(risk_on=3 / neutral=2 / risk_off=0).
  - SMH 조회 실패 시 bias='unknown' → 보수적으로 risk_off 와 동일하게 N=0(BUY 전면 보류).

⚠️ 방향 알파 주장 아님. signal_strength 와 마찬가지로 이 라벨은 '국면/보수성 throttle'이지
   수익 보장 신호가 아니다(docs/SIGNAL_STRENGTH_ANALYSIS.md 의 "throttle 이지 알파 아님" 기조 동일).

단독 점검(서버, KIS IP 등록 환경): python sector.py
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from kis.client import KISClient

# ===== 임계값(결정적 라벨 단일 진실 소스) =====
SMH_SYMBOL = "SMH"          # VanEck 반도체 ETF. NASDAQ 상장.
SMH_EXCHANGE = "NASD"       # 주문/시세 변환은 client 내부에서 NAS 로 매핑.
SMH_LOOKBACK_DAYS = 70      # SMA50 계산에 50+ 필요 → 여유 70.

BREADTH_RISK_ON_PCT = 60.0  # 유니버스의 이 비율 이상이 SMA20 상회 → 위험선호 확인
BREADTH_RISK_OFF_PCT = 40.0 # 이 비율 이하 → 위험회피

# bias → 그날 신규 매수 종목 수 상한(daily_trader 가 사용). risk_off/unknown 은 0(BUY 보류).
MAX_BUYS_BY_BIAS: dict[str, int] = {
    "risk_on": 3,
    "neutral": 2,
    "risk_off": 0,
    "unknown": 0,
}


def _sma(closes: list[float], k: int) -> Optional[float]:
    if len(closes) < k:
        return None
    return round(sum(closes[-k:]) / k, 4)


def classify_bias(
    smh_price: Optional[float],
    smh_sma20: Optional[float],
    smh_sma50: Optional[float],
    breadth_pct: Optional[float],
) -> str:
    """SMH 추세 구조 + breadth 로 risk_on/neutral/risk_off/unknown 을 결정적으로 산출.

    판정(보수 우선 = risk_off 를 먼저 확정):
      unknown  : SMH 가격/이평 중 하나라도 None(데이터 부족/조회 실패).
      up_struct   = price > sma20 AND sma20 >= sma50  (상승 정렬)
      down_struct = price < sma20 AND sma20 <  sma50  (하락 정렬)
      risk_off : down_struct  OR  (breadth_pct 제공되고 <= BREADTH_RISK_OFF_PCT)
      risk_on  : up_struct   AND (breadth_pct 미제공  OR  >= BREADTH_RISK_ON_PCT)
      neutral  : 그 외(혼조/약한 정렬).

    breadth 가 추세와 어긋나면(예: 상승 정렬인데 breadth 낮음) 보수적으로 risk_off/neutral 로
    내려간다 — 분산(divergence)일 때 매수를 늘리지 않음.
    """
    if smh_price is None or smh_sma20 is None or smh_sma50 is None:
        return "unknown"

    up_struct = smh_price > smh_sma20 and smh_sma20 >= smh_sma50
    down_struct = smh_price < smh_sma20 and smh_sma20 < smh_sma50

    # 1) risk_off 우선(보수)
    if down_struct:
        return "risk_off"
    if breadth_pct is not None and breadth_pct <= BREADTH_RISK_OFF_PCT:
        return "risk_off"

    # 2) risk_on (상승 정렬 + breadth 확인 또는 breadth 미제공)
    if up_struct and (breadth_pct is None or breadth_pct >= BREADTH_RISK_ON_PCT):
        return "risk_on"

    # 3) 그 외 중립
    return "neutral"


def max_buys_for_bias(bias: str) -> int:
    """bias 라벨 → 그날 신규 매수 종목 수 상한. 미지의 라벨은 0(보수)."""
    return MAX_BUYS_BY_BIAS.get(bias, 0)


def compute_breadth_pct(member_above_sma20: list[bool] | None) -> Optional[float]:
    """유니버스 멤버의 'SMA20 상회' 플래그 리스트 → 상회 비율(0~100). 빈/None 이면 None."""
    if not member_above_sma20:
        return None
    n = len(member_above_sma20)
    return round(sum(1 for x in member_above_sma20 if x) / n * 100, 2)


def compute_macro_bias(
    client: "KISClient",
    *,
    member_above_sma20: list[bool] | None = None,
    exchange: str = SMH_EXCHANGE,
) -> dict:
    """SMH 일봉(1콜) + (선택)유니버스 breadth 로 매크로 편향 dict 를 만든다.

    member_above_sma20: daily_trader 가 종목별 compute_trend 에서 이미 산출한 above_sma20
      플래그 리스트. 주면 breadth_pct 계산에 쓰고, 안 주면 SMH 추세만으로 판정한다
      (추가 KIS 호출 0 — 종목 일봉을 sector 가 중복 조회하지 않음).

    반환: {smh_price, smh_sma20, smh_sma50, breadth_pct, bias, samples}
      조회 실패/데이터 부족 시 bias='unknown', 수치 필드 None.
    """
    breadth_pct = compute_breadth_pct(member_above_sma20)
    try:
        closes = client.get_daily_prices(SMH_SYMBOL, exchange, days=SMH_LOOKBACK_DAYS)
    except Exception as e:  # noqa: BLE001 — 조회 실패는 unknown 으로 흡수(fail-conservative)
        return {
            "smh_price": None, "smh_sma20": None, "smh_sma50": None,
            "breadth_pct": breadth_pct, "bias": "unknown", "samples": 0,
            "error": f"{type(e).__name__}: {e}",
        }

    # classify_bias 가 sma50(=50 캔들 필요)이 None 이면 무조건 unknown 을 돌려준다.
    # 따라서 20~49 캔들이면 price/sma20 은 멀쩡한데 bias 만 unknown(=N=0 전면 BUY 정지)이 되어
    # '진짜 조회 실패'와 구분 불가해진다(precommit review #10). 임계를 50 으로 올려 모호함 제거
    # (SMH_LOOKBACK_DAYS=70 이라 정상 시 ~100 캔들 → steady-state 동작 불변).
    if not closes or len(closes) < 50:
        return {
            "smh_price": None, "smh_sma20": None, "smh_sma50": None,
            "breadth_pct": breadth_pct, "bias": "unknown", "samples": len(closes or []),
        }

    price = round(closes[-1], 4)
    sma20 = _sma(closes, 20)
    sma50 = _sma(closes, 50)
    bias = classify_bias(price, sma20, sma50, breadth_pct)
    return {
        "smh_price": price,
        "smh_sma20": sma20,
        "smh_sma50": sma50,
        "breadth_pct": breadth_pct,
        "bias": bias,
        "samples": len(closes),
    }


# 단독 점검(서버에서만 — 로컬은 KIS IP 미등록일 수 있음)
if __name__ == "__main__":
    from kis.client import KISClient

    c = KISClient()
    mb = compute_macro_bias(c)
    print(f"[macro_bias] env={c.settings.env}")
    for k, v in mb.items():
        print(f"  {k}: {v}")
    print(f"  → 그날 매수 상한 N = {max_buys_for_bias(mb['bias'])}")
