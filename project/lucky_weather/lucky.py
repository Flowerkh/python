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


def _filter_first_sentence(lines: list) -> list:
    result = []
    for line in lines:
        if re.fullmatch(r"〈.+띠〉", line.strip()):
            result.append(line)
        elif re.match(r"[\d,\s]+년생", line.strip()):
            match = re.match(r"([\d,\s]+년생\s+.+?\.)", line.strip())
            result.append(match.group(1) if match else line)
        elif line.startswith("운세지수"):
            result.append(line)
        else:
            result.append(line)
    return result