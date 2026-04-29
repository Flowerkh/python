import pyperclip
from datetime import datetime

from weather import get_seoul_weather_today
from air_quality import get_seoul_air_quality
from lucky import get_lucky


def _print_and_collect(text: str, parts: list) -> None:
    print(text)
    parts.append(text)


if __name__ == "__main__":
    today = datetime.now().strftime("%Y-%m-%d")
    output_parts = []
    p = lambda text: _print_and_collect(text, output_parts)

    # ── 미세먼지 ──
    p(f"=== 미세먼지 ===")
    air = get_seoul_air_quality()
    if "error" in air:
        p(air["error"])
    else:
        for key, value in air.items():
            p(f"  {key}: {value}")
    p("")

    # ── 날씨 ──
    p(f"=== 날씨 ({today}) ===")
    weather = get_seoul_weather_today()
    if "error" in weather:
        p(weather["error"])
    else:
        am = weather.get("오전", {})
        pm = weather.get("오후", {})
        p("[오전/오후]")
        for key in am:
            p(f"  {key}: {am[key]} / {pm.get(key, '-')}")
        p("")

    # ── 운세 ──
    p("=== 운세 ===")
    for line in get_lucky():
        p(line)

    pyperclip.copy("\n".join(output_parts))
    print("📋 클립보드에 자동 복사 완료")