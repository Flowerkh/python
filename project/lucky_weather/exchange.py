import requests

# Frankfurter: ECB 참조환율 기반, 무료·키 불필요
FRANKFURTER_URL = "https://api.frankfurter.app/latest"

CONNECT_TIMEOUT = 5
READ_TIMEOUT = 10

# (통화코드, 표시 단위) — 엔화는 100엔 기준으로 보는 게 관례다.
TARGETS = [("USD", 1), ("EUR", 1), ("JPY", 100)]

_session = requests.Session()


def get_exchange_rates() -> dict:
    """주요 통화의 원화 환율을 가져옵니다. 요청 1회로 전 통화를 조회합니다."""
    codes = [code for code, _ in TARGETS]

    try:
        response = _session.get(
            FRANKFURTER_URL,
            params={"base": "KRW", "symbols": ",".join(codes)},
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as e:
        return {"error": f"환율 정보 조회 실패: {e}"}

    rates = data.get("rates", {})
    if not rates:
        return {"error": "환율 데이터 없음"}

    # 응답은 'KRW 1당 외화' 값이므로 '외화 1당 KRW'로 역산한다.
    result = {}
    for code, unit in TARGETS:
        rate = rates.get(code)
        if not rate:
            result[f"{unit} {code}" if unit != 1 else f"1 {code}"] = "데이터 없음"
            continue
        krw = (1 / rate) * unit
        label = f"{unit} {code}" if unit != 1 else f"1 {code}"
        result[label] = f"{krw:,.2f}원"

    result["기준일"] = data.get("date", "-")
    return result
