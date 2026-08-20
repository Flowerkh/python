from datetime import datetime

import requests

from weather import WMO

# 네이버 스포츠 스케줄 API. 키 불필요, 하루치 전 경기를 요청 1회로 받는다.
# 주의: superCategoryId=kbaseball 로는 0건이 온다. categoryId=kbo 여야 한다.
SCHEDULE_URL = "https://api-gw.sports.naver.com/schedule/games"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://m.sports.naver.com/",
}

CONNECT_TIMEOUT = 5
READ_TIMEOUT = 15

# 구장 좌표. 경기 시각 날씨를 붙이는 데 쓴다.
STADIUM_LATLON = {
    "잠실": (37.5121, 127.0719),
    "고척": (37.4982, 126.8671),
    "문학": (37.4370, 126.6932),
    "수원": (37.2997, 127.0097),
    "대전": (36.3170, 127.4290),
    "대구": (35.8410, 128.6817),
    "창원": (35.2225, 128.5823),
    "사직": (35.1940, 129.0615),
    "광주": (35.1682, 126.8890),
    "울산": (35.5320, 129.2656),
    "포항": (36.0080, 129.3597),
    "청주": (36.6390, 127.4700),
}

# 돔구장은 비가 와도 상관없다.
DOME = {"고척"}

# 경기는 3시간 남짓 이어지므로 시작 시각부터 그만큼을 본다.
GAME_HOURS = 4

_session = requests.Session()


def _fetch_games(date: str) -> list:
    response = _session.get(
        SCHEDULE_URL,
        params={
            "fields": "basic,statusNum,statusInfo,cancel,stadium,"
                      "homeStarterName,awayStarterName",
            "categoryId": "kbo",
            "fromDate": date,
            "toDate": date,
            "size": 100,
        },
        headers=HEADERS,
        timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
    )
    response.raise_for_status()
    return response.json()["result"]["games"]


def _fetch_stadium_hourly(stadiums: list) -> dict:
    """경기가 열리는 구장의 시간별 예보를 요청 1회로 받아온다."""
    known = [s for s in stadiums if s in STADIUM_LATLON]
    if not known:
        return {}

    try:
        response = _session.get(
            FORECAST_URL,
            params={
                "latitude": ",".join(str(STADIUM_LATLON[s][0]) for s in known),
                "longitude": ",".join(str(STADIUM_LATLON[s][1]) for s in known),
                "hourly": "temperature_2m,weather_code",
                "timezone": "Asia/Seoul",
                "forecast_days": 1,
            },
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        )
        response.raise_for_status()
        blocks = response.json()
    except (requests.RequestException, ValueError):
        return {}  # 날씨는 부가 정보다. 실패해도 경기 정보는 그대로 보여준다.

    if isinstance(blocks, dict):
        blocks = [blocks]
    if len(blocks) != len(known):
        return {}

    return {s: b.get("hourly", {}) for s, b in zip(known, blocks)}


def _weather_prefix(stadium: str, hourly: dict, hour: int) -> str:
    """경기 시간대의 날씨를 접두사로 만든다. 낮 평균이 아니라 경기 시각이 핵심이다."""
    if stadium in DOME:
        return "🏟돔 "
    if not hourly:
        return ""

    try:
        idx = [h for h in range(hour, min(hour + GAME_HOURS, 24))
               if h < len(hourly["time"])]
        if not idx:
            return ""
        temp = round(hourly["temperature_2m"][hour])
        code = max(hourly["weather_code"][i] for i in idx)
    except (KeyError, IndexError, TypeError, ValueError):
        return ""

    return f"{WMO.get(code, ('알 수 없음', '❔'))[1]}{temp}도 "


def _format(game: dict, sky: str) -> str:
    time = game.get("gameDateTime", "")[11:16]  # "2026-08-20T19:00:00" -> "19:00"
    stadium = game.get("stadium", "-")
    away = game.get("awayTeamName", "?")
    home = game.get("homeTeamName", "?")

    if game.get("cancel"):
        return f"{sky}🚫{time} {stadium} {away} vs {home} ({game.get('statusInfo', '취소')})"

    if game.get("statusCode") == "BEFORE":
        away_pitcher = game.get("awayStarterName") or "미정"
        home_pitcher = game.get("homeStarterName") or "미정"
        return f"{sky}{time} {stadium} {away} {away_pitcher} vs {home} {home_pitcher}"

    # 경기중·종료는 선발보다 점수가 궁금하다.
    # statusInfo에는 상태가 아니라 이닝("9회말")이 들어오므로,
    # 종료 여부는 statusCode == RESULT 로 판단한다.
    score = f"{away} {game.get('awayTeamScore', 0)} vs {game.get('homeTeamScore', 0)} {home}"
    state = "종료" if game.get("statusCode") == "RESULT" else game.get("statusInfo", "진행중")
    return f"{sky}{time} {stadium} {score} ({state})"


def get_kbo_games(date: str = None) -> dict:
    """오늘 KBO 경기를 선발투수·구장 날씨와 함께 한 줄씩 요약합니다."""
    today = datetime.now().strftime("%Y-%m-%d")
    if date is None:
        date = today

    try:
        games = _fetch_games(date)
    except (requests.RequestException, ValueError, KeyError, TypeError) as e:
        return {"error": f"KBO 일정 조회 실패: {e}"}

    if not games:
        return {"lines": ["오늘은 경기가 없습니다"]}

    # 예보는 오늘치만 받으므로 다른 날짜를 조회하면 날씨는 붙이지 않는다.
    hourly = _fetch_stadium_hourly([g.get("stadium") for g in games]) if date == today else {}

    lines = []
    for g in games:
        time = g.get("gameDateTime", "")[11:16]
        hour = int(time[:2]) if time[:2].isdigit() else 18
        sky = _weather_prefix(g.get("stadium", "-"), hourly.get(g.get("stadium"), {}), hour)
        lines.append(_format(g, sky))

    return {"lines": lines}
