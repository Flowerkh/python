import requests

AIR_API_KEY = "sxbRIn8O3zpisPkZQ2a11s2K3N1yG8a90bDZRV6+b65d/u+oRzWVfwZtcpHwQ1jV6iKu4TvEWSbHT5qCNImVxw=="
def get_seoul_air_quality() -> dict:
    """서울 미세먼지 정보를 가져옵니다."""
    url = "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty"
    params = {
        "serviceKey": AIR_API_KEY,
        "returnType": "json",
        "numOfRows": 100,
        "pageNo": 1,
        "sidoName": "서울",
        "ver": "1.0",
    }
    try:
        response = requests.get(url, params=params, timeout=(30, 30))
        response.raise_for_status()
        data = response.json()

        items = data["response"]["body"]["items"]
        if not items:
            return {"error": "측정 데이터 없음"}

        pm10_list = [int(x["pm10Value"]) for x in items if x.get("pm10Value", "-") != "-"]
        pm25_list = [int(x["pm25Value"]) for x in items if x.get("pm25Value", "-") != "-"]

        avg_pm10 = round(sum(pm10_list) / len(pm10_list)) if pm10_list else None
        avg_pm25 = round(sum(pm25_list) / len(pm25_list)) if pm25_list else None

        return {
            "미세먼지(PM10)":   f"{avg_pm10}㎍/㎥  {_pm10_grade(avg_pm10)}" if avg_pm10 else "데이터 없음",
            "초미세먼지(PM2.5)": f"{avg_pm25}㎍/㎥  {_pm25_grade(avg_pm25)}" if avg_pm25 else "데이터 없음",
        }
    except requests.RequestException as e:
        return {"error": f"미세먼지 정보 조회 실패: {e}"}


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