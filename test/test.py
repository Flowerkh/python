import requests

def get_exchange_rate(base: str, target: str = "KRW") -> float | None:
    """
    단일 통화 환율 조회 (Frankfurter API - ECB 기준, 무료, 키 불필요)
    :param base: 기준 통화 (예: 'USD', 'EUR')
    :param target: 대상 통화 (예: 'KRW')
    :return: 환율 값 (1 base = ? target), 실패 시 None
    """
    url = "https://api.frankfurter.app/latest"
    params = {"from": base, "to": target}

    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()

        rate = data.get("rates", {}).get(target)
        if rate is None:
            print(f"환율 데이터 파싱 실패: {data}")
            return None

        return float(rate)

    except requests.exceptions.RequestException as e:
        print(f"환율 API 호출 실패: {e}")
        return None


def get_multiple_rates(targets: list[str], base: str = "KRW") -> dict:
    """
    여러 통화 환율을 한 번에 조회 (요청 1회로 처리)
    :param targets: 대상 통화 리스트 (예: ['USD', 'EUR'])
    :param base: 기준 통화 (기본 KRW)
    :return: {"USD": 1350.5, "EUR": 1580.2, "date": "2026-08-18"}
    """
    url = "https://api.frankfurter.app/latest"
    params = {"from": base, "to": ",".join(targets)}

    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()

        rates = data.get("rates", {})
        if not rates:
            return {}

        # KRW 기준 1당 외화 값이므로, "외화 1당 KRW" 형태로 역산
        result = {
            currency: round(1 / rate, 2)
            for currency, rate in rates.items()
            if rate > 0
        }
        result["date"] = data.get("date")

        return result

    except requests.exceptions.RequestException as e:
        print(f"환율 API 호출 실패: {e}")
        return {}


# ===== 사용 예시 =====
if __name__ == "__main__":
    # 방법 1: 개별 조회
    usd_to_krw = get_exchange_rate("USD", "KRW")
    eur_to_krw = get_exchange_rate("EUR", "KRW")

    print("---")

    # 방법 2: 한 번의 요청으로 여러 통화 조회 (추천, 효율적)
    rates = get_multiple_rates(["USD", "EUR", "JPY"])
    jpy_rate = rates.get("JPY", 0)

    if rates:
        print(f"기준일: {rates.get('date')}")
        print(f"1 USD = {rates.get('USD', 0):,.2f}원")
        print(f"1 EUR = {rates.get('EUR', 0):,.2f}원")
        print(f"100 JPY = {jpy_rate * 100:,.2f}원")
    else:
        print("환율 조회 실패")