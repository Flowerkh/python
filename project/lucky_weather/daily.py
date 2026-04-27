import pyperclip
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
from collections import defaultdict

# ─────────────────────────────────────────
# 날씨
# ─────────────────────────────────────────

def get_seoul_weather_today():
    """서울의 오늘 오전/오후 날씨 예보를 가져옵니다."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": 37.5665,
        "longitude": 126.9780,
        "hourly": "temperature_2m,relative_humidity_2m,weather_code,precipitation_probability,wind_speed_10m",
        "timezone": "Asia/Seoul",
        "forecast_days": 1,
    }
    try:
        response = requests.get(url, params=params, timeout=(30, 30))
        response.raise_for_status()
        data = response.json()
        return _summarize_am_pm(data["hourly"])
    except requests.RequestException as e:
        return {"error": f"날씨 정보를 가져오는데 실패했습니다: {e}"}


def _summarize_am_pm(hourly: dict) -> dict:
    times = hourly["time"]
    temps = hourly["temperature_2m"]
    humidities = hourly["relative_humidity_2m"]
    codes = hourly["weather_code"]
    rain_probs = hourly["precipitation_probability"]
    winds = hourly["wind_speed_10m"]

    periods = defaultdict(lambda: {
        "temps": [], "humidities": [], "codes": [],
        "rain_probs": [], "winds": []
    })

    for i, t in enumerate(times):
        hour = datetime.fromisoformat(t).hour
        period = "오전" if hour < 12 else "오후"
        periods[period]["temps"].append(temps[i])
        periods[period]["humidities"].append(humidities[i])
        periods[period]["codes"].append(codes[i])
        periods[period]["rain_probs"].append(rain_probs[i])
        periods[period]["winds"].append(winds[i])

    result = {}
    for period in ["오전", "오후"]:
        d = periods[period]
        if not d["temps"]:
            continue
        dominant_code = max(set(d["codes"]), key=d["codes"].count)
        result[period] = {
            "최저기온": f"{min(d['temps'])}°C",
            "최고기온": f"{max(d['temps'])}°C",
            "평균습도": f"{round(sum(d['humidities']) / len(d['humidities']))}%",
            "최대강수확률": f"{max(d['rain_probs'])}%",
            "평균풍속": f"{round(sum(d['winds']) / len(d['winds']), 1)} km/h",
            "날씨": _decode_weather(dominant_code),
        }
    return result


def _decode_weather(code: int) -> str:
    weather_map = {
        0: "맑음",
        1: "대체로 맑음", 2: "부분적으로 흐림", 3: "흐림",
        45: "안개", 48: "짙은 안개",
        51: "약한 이슬비", 53: "이슬비", 55: "강한 이슬비",
        61: "약한 비", 63: "비", 65: "강한 비",
        71: "약한 눈", 73: "눈", 75: "강한 눈",
        77: "싸락눈",
        80: "약한 소나기", 81: "소나기", 82: "강한 소나기",
        85: "약한 눈 소나기", 86: "강한 눈 소나기",
        95: "천둥번개", 96: "천둥번개와 약한 우박", 99: "천둥번개와 강한 우박",
    }
    return weather_map.get(code, f"알 수 없음 (코드: {code})")


# ─────────────────────────────────────────
# 운세
# ─────────────────────────────────────────

BASE_URL = "https://www.joongboo.com"
LIST_URL = "https://www.joongboo.com/news/articleList.html?sc_serial_code=SRN361&view_type=sm"

def get_lucky():
    headers = {"User-Agent": "Mozilla/5.0"}

    res = requests.get(LIST_URL, headers=headers)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")

    ul = soup.find("ul", class_="type2")
    first_li = ul.find("li") if ul else None
    if not first_li:
        raise Exception("첫 번째 기사 없음")

    a_tag = first_li.find("a", class_="thumb")
    href = a_tag.get("href") if a_tag else None
    if not href:
        raise Exception("href 없음")

    article_url = urljoin(BASE_URL, href)
    res = requests.get(article_url, headers=headers)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")

    article = soup.find("article", id="article-view-content-div")
    paragraphs = article.find_all("p")

    lines = []
    for p in paragraphs:
        text = p.get_text(strip=True)
        if "저작권은 지윤철학원에 있습니다" in text:
            continue
        if text:
            lines.append(text)

    return _filter_first_sentence(lines)  # ← 여기만 변경


def _filter_first_sentence(lines: list[str]) -> list[str]:
    import re
    result = []
    for line in lines:
        # 띠 헤더는 그대로
        if re.fullmatch(r"〈.+띠〉", line.strip()):
            result.append(line)

        # 연도생으로 시작하는 본문 줄 → 첫 문장만
        elif re.match(r"[\d,\s]+년생", line.strip()):
            match = re.match(r"([\d,\s]+년생\s+.+?\.)", line.strip())
            if match:
                result.append(match.group(1))
            else:
                result.append(line)

        # 운세지수, 날짜, 기타는 그대로
        elif line.startswith("운세지수"):
            result.append(line)
        else:
            result.append(line)

    return result


# ─────────────────────────────────────────
# 메인
# ─────────────────────────────────────────

if __name__ == "__main__":
    today = datetime.now().strftime("%Y-%m-%d")
    output_parts = []

    # ── 날씨 ──
    weather_header = f"=== 날씨 ({today}) ==="
    print(weather_header)
    print()
    output_parts.append(weather_header)
    output_parts.append("")

    weather = get_seoul_weather_today()
    if "error" in weather:
        print(weather["error"])
        output_parts.append(weather["error"])
    else:
        for period, info in weather.items():
            line = f"[{period}]"
            print(line)
            output_parts.append(line)
            for key, value in info.items():
                line = f"  {key}: {value}"
                print(line)
                output_parts.append(line)
            print()
            output_parts.append("")

    # ── 운세 ──
    lucky_header = "=== 운세 ==="
    print(lucky_header)
    print()
    output_parts.append(lucky_header)
    output_parts.append("")

    lucky_lines = get_lucky()
    for line in lucky_lines:
        print(line)
        print()
        output_parts.append(line)
        output_parts.append("")

    pyperclip.copy("\n".join(output_parts))
    print("📋 클립보드에 자동 복사 완료")
