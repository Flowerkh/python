import requests
import urllib3
from collections import defaultdict

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_seoul_weather_today() -> dict:
    """서울의 오늘 오전/오후 날씨 예보를 가져옵니다. (wttr.in)"""
    try:
        response = requests.get(
            "https://wttr.in/Seoul?format=j1",
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
        descs      = [s["lang_ko"][0]["value"] if s.get("lang_ko") else s["weatherDesc"][0]["value"] for s in slots]
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