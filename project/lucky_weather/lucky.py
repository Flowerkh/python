import pyperclip
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = "https://www.joongboo.com"
LIST_URL = "https://www.joongboo.com/news/articleList.html?sc_serial_code=SRN361&view_type=sm"  # 목록 페이지 URL (실제 URL로 교체)

headers = {
    "User-Agent": "Mozilla/5.0"
}

res = requests.get(LIST_URL, headers=headers)
res.raise_for_status()

soup = BeautifulSoup(res.text, "html.parser")

# ul.type2 안의 첫 번째 li
ul = soup.find("ul", class_="type2")
first_li = ul.find("li") if ul else None

if not first_li:
    raise Exception("첫 번째 기사 없음")

# a.thumb 추출
a_tag = first_li.find("a", class_="thumb")
href = a_tag.get("href") if a_tag else None

if not href:
    raise Exception("href 없음")

# 절대경로로 변환
article_url = urljoin(BASE_URL, href)

res = requests.get(article_url, headers=headers)
res.raise_for_status()

soup = BeautifulSoup(res.text, "html.parser")

article = soup.find("article", id="article-view-content-div")
paragraphs = article.find_all("p")

result = []

for p in paragraphs:
    text = p.get_text(strip=True)

    # 저작권 문구 제거
    if "저작권은 지윤철학원에 있습니다" in text:
        continue

    if text:
        result.append(text)

output = []

for line in result:
    print(line)
    print()
    output.append(line)

pyperclip.copy("\n\n".join(output))
print("📋 클립보드에 자동 복사 완료")