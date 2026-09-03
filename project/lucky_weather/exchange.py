from typing import Optional

import requests

# 1순위: 네이버 금융(하나은행 매매기준율). 당일 값이라 네이버 환율 화면과 일치한다.
NAVER_URL = "https://m.stock.naver.com/front-api/marketIndex/prices"
# 폴백: Frankfurter(ECB 참조환율). 무료·키 불필요하지만 전 영업일 고시라 하루 늦고,
# EUR 크로스레이트라 서울 매매기준율과 2원 안팎 벌어진다.
FRANKFURTER_URL = "https://api.frankfurter.app/latest"

NAVER_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://m.stock.naver.com/",
}

CONNECT_TIMEOUT = 5
READ_TIMEOUT = 10

# (통화코드, 표시 단위) — 엔화는 100엔 기준으로 보는 게 관례다.
TARGETS = [("USD", 1), ("EUR", 1), ("JPY", 100)]

# 네이버가 호가하는 단위. 엔화만 100엔 기준으로 준다.
NAVER_QUOTE_UNIT = {"JPY": 100}

# ECB 원본 기준 통화. base=KRW로 받으면 응답이 소수점 5자리로 반올림되면서
# 유효숫자가 2자리(예: USD 0.00073)밖에 안 남아 역산 시 최대 ±9원까지 틀어진다.
# EUR 기준으로 받아 교차 계산하면 요청 1회를 유지하면서 정밀도를 지킬 수 있다.
BASE = "EUR"

_session = requests.Session()


def _label(code: str, unit: int) -> str:
    return f"{unit} {code}" if unit != 1 else f"1 {code}"


def _fetch_naver() -> Optional[dict]:
    """네이버 금융에서 통화별로 조회합니다. 하나라도 실패하면 통째로 포기합니다.

    통화마다 소스가 섞이면 기준일이 달라져 출력이 뒤죽박죽이 되므로,
    부분 실패 시 전체를 ECB 폴백에 넘긴다.
    """
    result = {}
    for code, unit in TARGETS:
        try:
            response = _session.get(
                NAVER_URL,
                params={
                    "category": "exchange",
                    "reutersCode": f"FX_{code}KRW",
                    "page": 1,
                    "pageSize": 10,  # 10 미만은 API가 거부한다.
                },
                headers=NAVER_HEADERS,
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )
            response.raise_for_status()
            rows = response.json().get("result") or []
            # 최신 영업일이 첫 행. "1,358.40" 형태라 콤마를 걷어낸다.
            krw = float(rows[0]["closePrice"].replace(",", ""))
        except (requests.RequestException, ValueError, KeyError, TypeError, IndexError):
            return None
        # 네이버 호가 단위를 우리 표시 단위로 환산한다.
        result[_label(code, unit)] = f"{krw / NAVER_QUOTE_UNIT.get(code, 1) * unit:,.2f}원"

    return result


def _fetch_ecb() -> Optional[dict]:
    """Frankfurter에서 요청 1회로 전 통화를 조회합니다."""
    # base와 같은 통화는 응답 rates에서 빠지므로 symbols에서도 제외한다.
    symbols = [code for code, _ in TARGETS if code != BASE] + ["KRW"]

    try:
        response = _session.get(
            FRANKFURTER_URL,
            params={"base": BASE, "symbols": ",".join(symbols)},
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        )
        response.raise_for_status()
        rates = response.json().get("rates", {})
    except (requests.RequestException, ValueError) as e:
        print(f"⚠️ ECB 폴백 실패: {e}")
        return None

    krw_per_base = rates.get("KRW")
    if not krw_per_base:
        return None

    result = {}
    for code, unit in TARGETS:
        label = _label(code, unit)
        # 응답은 'base 1당 외화' 값이다. base 자신은 정의상 1.
        per_base = 1.0 if code == BASE else rates.get(code)
        if not per_base:
            result[label] = "데이터 없음"
            continue
        # (base 1당 KRW) / (base 1당 외화) = 외화 1당 KRW
        result[label] = f"{(krw_per_base / per_base) * unit:,.2f}원"

    return result


def get_exchange_rates() -> dict:
    """주요 통화의 원화 환율을 가져옵니다. 네이버 실패 시 ECB로 폴백합니다."""
    rates = _fetch_naver()
    if rates is None:
        print("⚠️ 네이버 환율 조회 실패 — ECB 폴백으로 전환합니다.")
        rates = _fetch_ecb()

    return rates if rates else {"error": "환율 정보 조회 실패"}
