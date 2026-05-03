import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = "https://www.joongboo.com"
LIST_URL = "https://www.joongboo.com/news/articleList.html?sc_serial_code=SRN361&view_type=sm"


def get_lucky() -> list:
    """오늘의 운세를 가져옵니다."""
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

    return _filter_first_sentence(lines)


def _fix_missing_years(line: str) -> str:
    """누락된 연도 보정: 05→93, 06→94, 07→95 추가"""
    replacements = [
        (r"\b05,\s*81년생", "05, 93, 81년생"),
        (r"\b06,\s*82년생", "06, 94, 82년생"),
        (r"\b07,\s*83년생", "07, 95, 83년생"),
    ]
    for pattern, repl in replacements:
        line = re.sub(pattern, repl, line)
    return line


def _filter_first_sentence(lines: list) -> list:
    result = []
    for line in lines:
        stripped = line.strip()

        if re.fullmatch(r"〈.+띠〉", stripped):
            result.append(line)
            continue

        if stripped.startswith("금전") and "운세지수" in stripped:
            result.append(line)
            continue

        # 누락된 연도 보정
        line = _fix_missing_years(line)

        # 두 번째 연령 그룹 앞에서 자르기
        matches = list(re.finditer(r"(?:\d{2},\s*)*\d{2}년생", line))
        if len(matches) >= 2:
            result.append(line[:matches[1].start()].strip())
        else:
            result.append(line)

    return result