import random
import time

import requests

AIR_API_KEY = "sxbRIn8O3zpisPkZQ2a11s2K3N1yG8a90bDZRV6+b65d/u+oRzWVfwZtcpHwQ1jV6iKu4TvEWSbHT5qCNImVxw=="

AIRKOREA_URL = "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty"
OPENMETEO_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
SEOUL_LATLON = (37.5665, 126.9780)

# 에어코리아는 간헐적으로 504(SERVICETIMEOUT_ERROR)를 뱉거나 아예 응답을 끊는다.
# 게이트웨이가 약 10초에 포기하므로 read 타임아웃을 짧게 잡아 빨리 재시도하고,
# 전체 소요 시간은 예산으로 묶어 스케줄러에서 무한정 매달리지 않게 한다.
CONNECT_TIMEOUT = 5
READ_TIMEOUT = 15
RETRY_BUDGET = 45   # 초, 재시도를 포함한 에어코리아 호출 총 예산
RETRY_BASE = 1.5    # 초, 시도마다 배로 증가 + 지터

_session = requests.Session()


def _sleep_before_retry(attempt: int) -> None:
    """지수 백오프 + 지터. 서버 회복 타이밍과 매번 어긋나는 것을 막는다."""
    time.sleep(RETRY_BASE * (2 ** (attempt - 1)) * (0.5 + random.random()))


def _fetch_airkorea() -> list:
    """대기오염정보 API를 예산 안에서 재시도하며 호출해 측정소 목록을 돌려줍니다."""
    params = {
        "serviceKey": AIR_API_KEY,
        "returnType": "json",
        "numOfRows": 100,
        "pageNo": 1,
        "sidoName": "서울",
        "ver": "1.0",
    }

    deadline = time.monotonic() + RETRY_BUDGET
    last_error = None
    attempt = 0

    while time.monotonic() < deadline:
        if attempt:
            _sleep_before_retry(attempt)
            if time.monotonic() >= deadline:
                break
        attempt += 1

        try:
            response = _session.get(
                AIRKOREA_URL, params=params, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT)
            )
            if response.status_code >= 500:
                last_error = f"{response.status_code} 서버 응답 지연"
                continue
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as e:
            last_error = str(e)
            continue

        # 상태코드 200이어도 에러 봉투를 돌려주는 경우가 있다.
        if "response" not in data:
            header = data.get("OpenAPI_ServiceResponse", {}).get("cmmMsgHeader", {})
            last_error = header.get("errMsg") or "예상치 못한 응답 형식"
            continue

        return data["response"]["body"]["items"] or []

    raise RuntimeError(f"{attempt}회 시도 실패: {last_error or '알 수 없는 오류'}")


def _fetch_openmeteo() -> tuple:
    """에어코리아 장애 시 쓰는 폴백. CAMS 모델 기반 추정치라 실측과 차이가 있다."""
    latitude, longitude = SEOUL_LATLON
    response = _session.get(
        OPENMETEO_URL,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "current": "pm10,pm2_5",
            "timezone": "Asia/Seoul",
        },
        timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
    )
    response.raise_for_status()
    current = response.json()["current"]

    pm10, pm25 = current.get("pm10"), current.get("pm2_5")
    return (
        round(pm10) if pm10 is not None else None,
        round(pm25) if pm25 is not None else None,
    )


def _average(items: list, field: str):
    """측정소별 값 중 결측('-', None)을 빼고 평균을 냅니다."""
    values = [
        int(x[field])
        for x in items
        if str(x.get(field, "-")).strip() not in ("-", "", "None")
    ]
    return round(sum(values) / len(values)) if values else None


def get_seoul_air_quality() -> dict:
    """서울 미세먼지 정보를 가져옵니다. 에어코리아 실측 우선, 장애 시 Open-Meteo 폴백."""
    source = "에어코리아 실측"

    try:
        items = _fetch_airkorea()
        if not items:
            raise RuntimeError("측정 데이터 없음")

        avg_pm10 = _average(items, "pm10Value")
        avg_pm25 = _average(items, "pm25Value")
        if avg_pm10 is None and avg_pm25 is None:
            raise RuntimeError("유효한 측정값 없음")

    except (RuntimeError, KeyError, TypeError, ValueError) as primary_error:
        try:
            avg_pm10, avg_pm25 = _fetch_openmeteo()
            source = "Open-Meteo 추정(에어코리아 장애)"
        except (requests.RequestException, KeyError, TypeError, ValueError) as fallback_error:
            return {
                "error": f"미세먼지 정보 조회 실패: "
                         f"에어코리아({primary_error}) / 폴백({fallback_error})"
            }

    return {
        "미세먼지(PM10)": f"{avg_pm10}㎍/㎥  {_pm10_grade(avg_pm10)}"
                          if avg_pm10 is not None else "데이터 없음",
        "초미세먼지(PM2.5)": f"{avg_pm25}㎍/㎥  {_pm25_grade(avg_pm25)}"
                          if avg_pm25 is not None else "데이터 없음",
        "출처": source,
    }


def _pm10_grade(value: int) -> str:
    if value <= 30:  return "좋음 🟢"
    if value <= 80:  return "보통 🟡"
    if value <= 150: return "나쁨 🟠"
    return "매우나쁨 🔴"


def _pm25_grade(value: int) -> str:
    if value <= 15: return "좋음 🟢"
    if value <= 35: return "보통 🟡"
    if value <= 75: return "나쁨 🟠"
    return "매우나쁨 🔴"
