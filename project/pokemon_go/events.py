# -*- coding: utf-8 -*-
"""포켓몬 GO 이벤트 정보를 ScrapedDuck(leekduck.com 비공식 미러) 피드에서 가져온다.
https://github.com/bigfoott/ScrapedDuck
"""
import json
import os
import re
from datetime import datetime, timedelta, timezone

import requests

EVENTS_URL = "https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/events.json"

HEADERS = {"User-Agent": "Mozilla/5.0"}
CONNECT_TIMEOUT = 5
READ_TIMEOUT = 15

KST = timezone(timedelta(hours=9))
WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]

# heading(이벤트 대분류)별 표시 이모지
HEADING_EMOJI = {
    "Community Day": "🟢",
    "Event": "✨",
    "Raid Battles": "⚔️",
    "Raid Day": "⚔️",
    "Raid Hour": "⏰",
    "GO Battle League": "🥊",
    "Max Battles": "💥",
    "Max Mondays": "💥",
    "Pokémon Spotlight Hour": "🔎",
    "Wild Area": "🌍",
    "Pokémon GO Tour": "🧭",
    "Season": "🗓",
    "Research": "🔬",
    "GO Pass": "🎫",
    "Twitch Drops": "🎮",
}
DEFAULT_EMOJI = "📌"

_session = requests.Session()

# ── 레이드 보스 한글 번역 ──
# 영→한 종 이름은 PokeAPI에서 미리 받아 캐시해 둔 파일을 쓴다. (build_names.py 참고)
_NAMES_KO_PATH = os.path.join(os.path.dirname(__file__), "data", "pokemon_names_ko.json")
try:
    with open(_NAMES_KO_PATH, encoding="utf-8") as _f:
        SPECIES_KO = json.load(_f)
except (OSError, ValueError):
    SPECIES_KO = {}

# 메가/섀도우 등 접두사
PREFIX_KO = {
    "Mega": "메가",
    "Primal": "프라이멀",
    "Shadow": "섀도우",
    "Partner": "파트너",
    "Alolan": "알로라",
    "Galarian": "가라르",
    "Hisuian": "히스이",
    "Paldean": "팔데아",
}

# 괄호로 붙는 폼(forme) 이름
FORME_KO = {
    "Incarnate": "화신폼",
    "Therian": "영수폼",
    "Origin": "오리진폼",
    "Altered": "어나더폼",
    "Sky": "스카이폼",
    "Attack": "어택폼",
    "Defense": "디펜스폼",
    "Speed": "스피드폼",
    "Normal": "노멀폼",
    "Plant": "플랜트폼",
    "Sandy": "샌드폼",
    "Trash": "트래쉬폼",
    "Sunny": "선샤인폼",
    "Rainy": "레이니폼",
    "Snowy": "스노위폼",
    "Heat": "히트로터폼",
    "Wash": "워시로터폼",
    "Frost": "프로스트로터폼",
    "Fan": "팬로터폼",
    "Mow": "커트로터폼",
}

# 레이드 등급 문구
TIER_KO = {
    "Mega Raids": "메가 레이드",
    "5-star Raid Battles": "5성 레이드",
    "Shadow Raids": "섀도우 레이드",
}

# 스팟라이트 아워 보너스 문구
SPOTLIGHT_BONUS_KO = {
    "2× Catch XP": "2배 캐치 XP",
    "2× Catch Candy": "2배 캐치 사탕",
    "2× Transfer Candy": "2배 교환 사탕",
    "2× Catch Stardust": "2배 캐치 별의모래",
    "2× Evolution XP": "2배 진화 XP",
}

# "event" 타입처럼 패턴화하기 어려운 제목에서, 알아볼 수 있는 단어만 한글로 바꾼다.
# 고유 브랜드명(이벤트 시리즈 이름 등)은 번역 데이터가 없어 원문을 그대로 둔다.
# 긴 구문을 먼저 매칭해야 하므로 길이 내림차순으로 적용한다.
EVENT_PHRASE_KO = [
    ("Community Day Classic", "커뮤니티 데이 클래식"),
    ("Special Research", "스페셜 리서치"),
    ("Timed Research", "기간한정 리서치"),
    ("Field Research", "필드 리서치"),
    ("Community Day", "커뮤니티 데이"),
    ("GO Battle League", "GO 배틀 리그"),
    ("Pokémon GO Tour", "포켓몬 GO 투어"),
    ("Max Battle Day", "다이맥스 배틀 데이"),
    ("Max Monday", "맥스 먼데이"),
    ("Max Battles", "맥스 배틀"),
    ("Raid Battles", "레이드 배틀"),
    ("Hatch Day", "해치 데이"),
    ("Raid Day", "레이드 데이"),
    ("Raid Hour", "레이드 아워"),
    ("Spotlight Hour", "스팟라이트 아워"),
    ("Wild Area", "와일드 에리어"),
    ("GO Pass", "GO 패스"),
    ("Halloween", "할로윈"),
    ("Marathon", "마라톤"),
    ("Celebration", "기념"),
    ("Holiday", "홀리데이"),
    ("Anniversary", "기념일"),
    ("Debut", "데뷔"),
]


def _translate_pokemon_name(name: str) -> str:
    """영문 레이드 보스 이름(메가/섀도우/폼 포함)을 최대한 한글로 바꾼다.
    매핑에 없는 이름은 원문을 그대로 돌려준다(틀린 번역보다 원문이 낫다)."""
    if not name:
        return name

    s = name.strip()

    # 괄호 폼 분리: "Landorus (Incarnate)" / "Giratina (Origin Forme)"
    forme_ko = None
    m = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", s)
    if m:
        s = m.group(1).strip()
        forme_word = re.sub(r"\s+Forme?$", "", m.group(2).strip(), flags=re.IGNORECASE)
        forme_ko = FORME_KO.get(forme_word, m.group(2).strip())

    # 접두사 분리: Mega / Shadow / Primal / Alolan / Galarian / Hisuian / Paldean / Partner
    tokens = s.split(" ")
    prefix_ko = ""
    while tokens and tokens[0] in PREFIX_KO:
        prefix_ko += PREFIX_KO[tokens[0]] + " "
        tokens = tokens[1:]

    # 말미 X/Y 분리: "Charizard X" -> "리자몽 X"
    suffix_xy = ""
    if tokens and tokens[-1] in ("X", "Y"):
        suffix_xy = " " + tokens[-1]
        tokens = tokens[:-1]

    base_en = " ".join(tokens).strip()
    base_ko = SPECIES_KO.get(base_en.lower())
    if base_ko is None:
        return name  # 모르는 이름은 원문 유지

    result = f"{prefix_ko}{base_ko}{suffix_xy}"
    if forme_ko:
        result += f" ({forme_ko})"
    return result


def _parse_dt(value: str):
    """ScrapedDuck의 시각 두 형식을 모두 처리한다.
    - 'Z' 없음: 플레이어 로컬 시각(그대로 사용)
    - 'Z' 있음: UTC 고정 시각 -> KST로 변환
    """
    if not value:
        return None
    if value.endswith("Z"):
        dt = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
        dt = dt.replace(tzinfo=timezone.utc).astimezone(KST)
        return dt.replace(tzinfo=None)
    return datetime.fromisoformat(value)


def _fmt_date(dt: datetime) -> str:
    return "%s(%s)" % (dt.strftime("%m/%d"), WEEKDAY_KR[dt.weekday()])


def _fmt_range(start: datetime, end: datetime) -> str:
    if start.date() == end.date():
        return "%s %s~%s" % (_fmt_date(start), start.strftime("%H:%M"), end.strftime("%H:%M"))
    return "%s %s ~ %s %s" % (
        _fmt_date(start), start.strftime("%H:%M"),
        _fmt_date(end), end.strftime("%H:%M"),
    )


def _translate_raid_title(event: dict) -> str:
    """레이드 관련 이벤트(raid-battles/raid-hour/raid-day)의 제목을 한글로 재구성한다.
    패턴을 인식 못 하면 원문 제목을 그대로 돌려준다."""
    name = event.get("name", "")
    event_type = event.get("eventType")
    bosses = [
        b.get("name") for b in
        ((event.get("extraData") or {}).get("raidbattles") or {}).get("bosses") or []
        if b.get("name")
    ]

    if event_type == "raid-hour":
        m = re.match(r"^(.*)\s+Raid Hour$", name)
        if m:
            # extraData에 보스 목록이 없는 경우 제목에서 직접 뽑아낸다
            raw_bosses = bosses or re.split(r"\s+and\s+", m.group(1))
            boss_ko = ", ".join(_translate_pokemon_name(b) for b in raw_bosses)
            return f"{boss_ko} 레이드 아워"

    elif event_type == "raid-battles":
        m = re.match(r"^(.*)\s+in\s+(Mega Raids|5-star Raid Battles|Shadow Raids)$", name)
        if m:
            tier_ko = TIER_KO.get(m.group(2), m.group(2))
            raw_bosses = bosses or re.split(r"\s+and\s+", m.group(1))
            boss_ko = ", ".join(_translate_pokemon_name(b) for b in raw_bosses)
            return f"{boss_ko} {tier_ko}"

    elif event_type == "raid-day":
        return f"{name} (레이드 데이)"

    return name


def _translate_dynamax_title(event: dict) -> str:
    """Max Mondays / Max Battles(다이맥스) 제목을 한글로 재구성한다."""
    name = event.get("name", "")
    event_type = event.get("eventType")

    if event_type == "max-mondays":
        m = re.match(r"^Dynamax\s+(.*)\s+during Max Monday$", name)
        if m:
            boss_ko = _translate_pokemon_name(m.group(1))
            return f"{boss_ko} 다이맥스 (맥스 먼데이)"

    elif event_type == "max-battles":
        m = re.match(r"^Dynamax\s+(.*)\s+Max Battle Day$", name)
        if m:
            raw_bosses = re.split(r",\s*|\s+and\s+", m.group(1))
            boss_ko = ", ".join(_translate_pokemon_name(b) for b in raw_bosses if b)
            return f"{boss_ko} 다이맥스 배틀 데이"

    return name


def _translate_spotlight_title(event: dict) -> str:
    """Pokémon Spotlight Hour 제목을 한글로 재구성한다."""
    name = event.get("name", "")
    spotlight = (event.get("extraData") or {}).get("spotlight") or {}
    boss = spotlight.get("name")

    if boss:
        return f"{_translate_pokemon_name(boss)} 스팟라이트 아워"

    m = re.match(r"^(.*)\s+Spotlight Hour$", name)
    if m:
        return f"{_translate_pokemon_name(m.group(1))} 스팟라이트 아워"

    return name


def _translate_event_title(event: dict) -> str:
    """패턴이 정해져 있지 않은 'event' 타입 제목을 최대한 한글로 바꾼다.
    - '<포켓몬> Hatch Day' 처럼 알아볼 수 있는 패턴은 통째로 재구성한다.
    - 그 외에는 알려진 단어/구문만 한글로 바꾸고, 고유 브랜드명은 원문을 유지한다
      (매핑에 없는 이름을 억지로 번역하면 오역이 되므로 원문 유지가 더 안전하다)."""
    name = event.get("name", "")

    m = re.match(r"^(.*)\s+Hatch Day$", name)
    if m and m.group(1).strip().lower() in SPECIES_KO:
        return f"{_translate_pokemon_name(m.group(1).strip())} 해치 데이"

    result = name
    for phrase_en, phrase_ko in EVENT_PHRASE_KO:
        result = result.replace(phrase_en, phrase_ko)
    return result


def _extra_detail(event: dict):
    """커뮤니티 데이, 레이드, 스팟라이트 등 부가 정보를 한 줄 덧붙인다."""
    extra = event.get("extraData") or {}

    cd = extra.get("communityday")
    if cd:
        names = ", ".join(s.get("name", "") for s in cd.get("spawns") or [] if s.get("name"))
        if names:
            return f"    ㄴ 등장: {names}"

    raid = extra.get("raidbattles")
    if raid:
        names = ", ".join(
            _translate_pokemon_name(b.get("name", ""))
            for b in raid.get("bosses") or [] if b.get("name")
        )
        if names:
            return f"    ㄴ 보스: {names}"

    spotlight = extra.get("spotlight")
    if spotlight:
        name = spotlight.get("name", "")
        bonus = spotlight.get("bonus", "")
        if name:
            detail = f"    ㄴ 대상: {_translate_pokemon_name(name)}"
            if bonus:
                bonus_ko = SPOTLIGHT_BONUS_KO.get(bonus, bonus)
                detail += f" (보너스: {bonus_ko})"
            return detail

    return None


def _fetch_events() -> list:
    response = _session.get(
        EVENTS_URL,
        headers=HEADERS,
        timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
    )
    response.raise_for_status()
    return response.json()


def get_pokemon_events(days: int = 7) -> dict:
    """오늘부터 `days`일 안에 진행 중이거나 시작하는 포켓몬 GO 이벤트를 요약합니다."""
    try:
        events = _fetch_events()
    except (requests.RequestException, ValueError) as e:
        return {"error": f"포켓몬 GO 이벤트 조회 실패: {e}"}

    now = datetime.now()
    window_end = now + timedelta(days=days)

    rows = []
    for e in events:
        start = _parse_dt(e.get("start"))
        end = _parse_dt(e.get("end"))
        if start is None or end is None:
            continue
        # 이번 주 안에 걸쳐 있는 이벤트만: 아직 끝나지 않았고 이번 주 안에 시작한다
        if end >= now and start <= window_end:
            rows.append((start, end, e))

    if not rows:
        return {"lines": [f"앞으로 {days}일간 예정된 이벤트가 없습니다"]}

    rows.sort(key=lambda t: t[0])

    lines = []
    for start, end, e in rows:
        heading = e.get("heading", "")
        emoji = HEADING_EMOJI.get(heading, DEFAULT_EMOJI)
        status = "🔵" if start <= now else "🆕"
        event_type = e.get("eventType")
        if event_type in ("raid-battles", "raid-hour", "raid-day"):
            name = _translate_raid_title(e)
        elif event_type in ("max-mondays", "max-battles"):
            name = _translate_dynamax_title(e)
        elif event_type == "pokemon-spotlight-hour":
            name = _translate_spotlight_title(e)
        elif event_type == "event":
            name = _translate_event_title(e)
        else:
            name = e.get("name", "(이름 없음)")
        line = f"{status}{emoji} [{heading}] {name}\n    {_fmt_range(start, end)}"
        lines.append(line)

        detail = _extra_detail(e)
        if detail:
            lines.append(detail)

        link = e.get("link")
        if link:
            lines.append(f"    {link}")

    return {"lines": lines}
