import requests

# Open-Meteo: 무료·키 불필요. 요청 1회로 여러 좌표를 동시에 받을 수 있다.
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

CONNECT_TIMEOUT = 5
READ_TIMEOUT = 15

# (표시명, 위도, 경도)
CITIES = [
    ("서울", 37.5665, 126.9780),  # 서울시청
    ("수원", 37.2636, 127.0286),  # 수원시청
    ("화성", 37.1996, 126.8314),  # 경기 화성시청
    ("송도", 37.3826, 126.6435),  # 인천 연수구 송도동
]

# 낮 시간대만 본다. 새벽은 출근 전 리포트에 의미가 적다.
DAY_HOURS = range(6, 19)  # 06~18시

# WMO weather code -> (한글, 이모지)
# 계열이 다르면 이모지도 반드시 다르게 둔다. 이슬비와 비가 같은 그림이면
# 한눈에 구분이 안 된다. 세기(약/보통/강)는 계열 안에서 합쳤다.
_WMO = {
    # 맑음 ~ 흐림
    0: ("맑음", "☀"), 1: ("대체로 맑음", "🌤"), 2: ("구름 조금", "⛅"), 3: ("흐림", "☁"),
    # 안개
    45: ("안개", "🌫"), 48: ("상고대 안개", "🌫"),
    # 이슬비
    51: ("약한 이슬비", "💧"), 53: ("이슬비", "💧"), 55: ("강한 이슬비", "💧"),
    # 비
    61: ("약한 비", "🌧"), 63: ("비", "🌧"), 65: ("강한 비", "🌧"),
    # 소나기
    80: ("약한 소나기", "🌦"), 81: ("소나기", "🌦"), 82: ("강한 소나기", "🌦"),
    # 눈
    71: ("약한 눈", "🌨"), 73: ("눈", "🌨"), 75: ("강한 눈", "🌨"), 77: ("싸락눈", "🌨"),
    # 눈 소나기
    85: ("약한 눈소나기", "❄"), 86: ("강한 눈소나기", "❄"),
    # 뇌우
    95: ("뇌우", "⛈"), 96: ("뇌우/우박", "⛈"), 99: ("강한 뇌우/우박", "⛈"),
    # 어는 비 계열 (국내에서는 드물다)
    56: ("어는 이슬비", "🥶"), 57: ("강한 어는 이슬비", "🥶"),
    66: ("어는 비", "🥶"), 67: ("강한 어는 비", "🥶"),
}

_session = requests.Session()


def _summarize(hourly: dict) -> dict:
    """한 지점의 낮 시간대를 하루 한 줄 분량으로 압축합니다."""
    idx = [h for h in DAY_HOURS if h < len(hourly["time"])]
    if not idx:
        raise ValueError("예보 시간대 없음")

    temps = [hourly["temperature_2m"][i] for i in idx]
    rains = [hourly["precipitation_probability"][i] or 0 for i in idx]
    winds = [hourly["wind_speed_10m"][i] for i in idx]
    codes = [hourly["weather_code"][i] for i in idx]

    # 하루 대표 날씨는 가장 궂은 쪽으로 잡는다. WMO 코드는 대체로 값이
    # 클수록 궂은 날씨라, 잠깐이라도 비가 오면 그걸 알려주는 편이 낫다.
    icon = _WMO.get(max(codes), ("알 수 없음", "❔"))[1]

    return {
        "low": round(min(temps)),
        "high": round(max(temps)),
        "rain": max(rains),
        "wind": round(sum(winds) / len(winds), 1),
        "icon": icon,
    }


def get_today_weather() -> dict:
    """서울·수원·화성·송도의 오늘 날씨를 요청 1회로 가져와 한 줄씩 요약합니다."""
    try:
        response = _session.get(
            FORECAST_URL,
            params={
                "latitude": ",".join(str(lat) for _, lat, _ in CITIES),
                "longitude": ",".join(str(lon) for _, _, lon in CITIES),
                "hourly": "temperature_2m,precipitation_probability,"
                          "weather_code,wind_speed_10m",
                "timezone": "Asia/Seoul",
                "forecast_days": 1,
            },
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        )
        response.raise_for_status()
        blocks = response.json()
    except (requests.RequestException, ValueError) as e:
        return {"error": f"날씨 정보 조회 실패: {e}"}

    # 좌표를 하나만 넘기면 리스트가 아닌 단일 객체로 온다.
    if isinstance(blocks, dict):
        blocks = [blocks]
    if len(blocks) != len(CITIES):
        return {"error": f"날씨 응답 지점 수 불일치({len(blocks)}/{len(CITIES)})"}

    lines = []
    for (name, _, _), block in zip(CITIES, blocks):
        try:
            s = _summarize(block["hourly"])
        except (KeyError, TypeError, ValueError, IndexError) as e:
            lines.append(f"{name} 조회 실패({e})")
            continue

        lines.append(
            f"{s['icon']}{name} {s['low']}/{s['high']}도 "
            f"☔{s['rain']}% 💨{s['wind']}km/h"
        )

    return {"lines": lines}
