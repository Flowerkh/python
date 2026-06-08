import requests
import urllib3
from collections import defaultdict

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_WEATHER_KO = {
    "Sunny": "맑음",
    "Clear": "맑음",
    "Partly Cloudy": "구름 조금",
    "Partly cloudy": "구름 조금",
    "Cloudy": "흐림",
    "Overcast": "흐림",
    "Mist": "안개",
    "Fog": "안개",
    "Freezing fog": "결빙 안개",
    "Patchy rain nearby": "근처 간헐적 비",
    "Patchy rain possible": "비 가능성",
    "Patchy light rain": "간헐적 가랑비",
    "Light rain": "가벼운 비",
    "Light drizzle": "이슬비",
    "Patchy light drizzle": "간헐적 이슬비",
    "Light rain shower": "가벼운 소나기",
    "Moderate rain": "비",
    "Moderate rain at times": "간헐적 비",
    "Heavy rain": "폭우",
    "Heavy rain at times": "간헐적 폭우",
    "Torrential rain shower": "집중 호우",
    "Moderate or heavy rain shower": "강한 소나기",
    "Light freezing rain": "가벼운 결빙 비",
    "Moderate or heavy freezing rain": "강한 결빙 비",
    "Patchy snow possible": "눈 가능성",
    "Patchy light snow": "간헐적 가벼운 눈",
    "Light snow": "가벼운 눈",
    "Light snow showers": "가벼운 눈 소나기",
    "Moderate snow": "눈",
    "Heavy snow": "폭설",
    "Moderate or heavy snow showers": "강한 눈 소나기",
    "Blowing snow": "눈보라",
    "Blizzard": "폭풍설",
    "Ice pellets": "우박",
    "Light sleet": "가벼운 진눈깨비",
    "Light sleet showers": "가벼운 진눈깨비 소나기",
    "Moderate or heavy sleet": "강한 진눈깨비",
    "Moderate or heavy sleet showers": "강한 진눈깨비 소나기",
    "Thundery outbreaks possible": "천둥 가능성",
    "Patchy light rain with thunder": "천둥 동반 가벼운 비",
    "Moderate or heavy rain with thunder": "천둥 동반 강한 비",
    "Patchy light snow with thunder": "천둥 동반 가벼운 눈",
    "Moderate or heavy snow with thunder": "천둥 동반 폭설",
}


def _translate_weather(desc: str) -> str:
    return _WEATHER_KO.get(desc.strip(), desc)


def get_seoul_weather_today() -> dict:
    """서울의 오늘 오전/오후 날씨 예보를 가져옵니다. (wttr.in)"""
    try:
        response = requests.get(
            "https://wttr.in/Seoul?format=j1&lang=ko",
            timeout=(30, 30),
            headers={"User-Agent": "curl/7.0"},
            verify=False
        )
        response.raise_for_status()
        data = response.json()
        return _summarize_am_pm(data)
    except requests.RequestException as e:
        return {"error": f"날씨 정보를 가져오는데 실패했습니다: {e}"}


def _summarize_am_pm(data: dict) -> dict:
    """wttr.in 데이터를 오전/오후로 요약합니다."""
    today = data["weather"][0]

    # hourly: 0=자정, 1=오전3시, 2=오전6시, 3=오전9시,
    #         4=정오,  5=오후3시, 6=오후6시, 7=오후9시
    hourly = today["hourly"]
    am_slots = hourly[0:4]  # 0~9시
    pm_slots = hourly[4:8]  # 12~21시

    def summarize(slots):
        temps      = [int(s["tempC"]) for s in slots]
        humidity   = [int(s["humidity"]) for s in slots]
        rain_prob  = [int(s["chanceofrain"]) for s in slots]
        wind       = [int(s["windspeedKmph"]) for s in slots]
        descs      = [_translate_weather(s["weatherDesc"][0]["value"]) for s in slots]
        return {
            "최저기온":    f"{min(temps)}°C",
            "최고기온":    f"{max(temps)}°C",
            "평균습도":    f"{round(sum(humidity) / len(humidity))}%",
            "최대강수확률": f"{max(rain_prob)}%",
            "평균풍속":    f"{round(sum(wind) / len(wind), 1)} km/h",
            "날씨":       descs[2],  # 대표 시간대 설명
        }

    return {
        "오전": summarize(am_slots),
        "오후": summarize(pm_slots),
    }