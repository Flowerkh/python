import feedparser
from datetime import datetime, timedelta
import os
import time
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SENDER_EMAIL = "mbp.prd@macrogen.com"
SENDER_PW = os.getenv("SENDER_PW")  # 앱 비밀번호 사용 권장
RECEIVER_LIST = ["cdffee1@naver.com"]

client = OpenAI(api_key=OPENAI_API_KEY)

RSS_URLS = [
    "http://feeds.bbci.co.uk/news/technology/rss.xml",
    "https://techcrunch.com/feed/",
    "https://www.eetimes.com/feed/",
    "https://semiengineering.com/feed/",
    "https://semiwiki.com/feed/",
    "https://siliconsemiconductor.net/rss",
    "https://www.digitimes.com/rss/it_news.xml",
    "https://www.reutersagency.com/feed/?best-topics=technology&post_type=best"
]


def get_recent_news():
    recent_articles = []
    seven_days_ago = datetime.now() - timedelta(days=7)

    print(f"--- 최근 일주일({seven_days_ago.date()} 이후) 뉴스 수집 중 ---")

    for url in RSS_URLS:
        try:
            feed = feedparser.parse(url)
            source_name = feed.feed.title if hasattr(feed.feed, 'title') else url

            for entry in feed.entries:
                # 날짜 데이터 파싱 (안정성을 위해 속성 확인)
                if hasattr(entry, 'published_parsed'):
                    published_time = datetime.fromtimestamp(time.mktime(entry.published_parsed))

                    if published_time > seven_days_ago:
                        # 딕셔너리 형태로 저장하여 URL 정보를 보존
                        recent_articles.append({
                            "title": entry.title,
                            "summary": entry.summary[:300] if hasattr(entry, 'summary') else "",
                            "link": entry.link,
                            "source": source_name
                        })
        except Exception as e:
            print(f"RSS 수집 에러 ({url}): {e}")

    return recent_articles


def analyze_with_openai(news_data):
    if not news_data:
        return None, ""

    # 분석용 텍스트 생성 (최대 15개 기사)
    analysis_input = ""
    for idx, art in enumerate(news_data[:15]):
        analysis_input += f"[{idx + 1}] Source: {art['source']}\nTitle: {art['title']}\nSummary: {art['summary']}\n\n"

    prompt = f"""
    [수집된 뉴스 데이터]
    {analysis_input}
    
    당신은 골드만삭스와 같은 글로벌 투자은행의 '수석 반도체 전략가'입니다. 
    최근 일주일간의 수집된 뉴스 데이터를 바탕으로 기관 투자자들을 위한 [2026 반도체 전략 투자 리포트]를 작성하세요.

    [작성 가이드라인: 투자 관점]
    1. ★ 거시적 요인 분석: 금리, 지정학적 리스크(대만/미중/전쟁), 보조금 정책이 반도체 공급망에 미치는 영향을 서술하세요.
    2. ★ 기업별 투자 등급 및 방향성: 
       - NVIDIA, 삼성전자, TSMC, ASML, SK하이닉스, 구글, 마이크로소프트, 브로드컴 중 데이터에 언급된 기업을 중심으로 분석하세요.
       - 각 기업의 '경제적 해자(Moat)'가 강화되었는지, 혹은 위협받고 있는지 판단하세요.
    3. ★ 공급망 권력 이동: 설계(Fabless) vs 제조(Foundry) vs 장비(OSAT/Equipment) 중 어느 섹터에 자본이 몰리고 있는지 짚어주세요.
    4. ★ 최종 투자 의견: 
       - 향후 3개월 전망을 '비중확대(Overweight)', '중립(Neutral)', '비중축소(Underweight)' 중 하나로 제시하고 그 이유를 명확히 하세요.

    [작성 형식]
    - 전문적인 금융 리포트 톤앤매너를 유지할 것.
    - 가독성을 위해 불렛포인트와 섹션 구분(###)을 명확히 할 것.
    - 기업명, 투자(긍정,보통,불안), 상세이유 형식으로 작성할 것.
    - 한국어로 작성할 것.
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )

    # 리포트 생성
    ai_report = response.choices[0].message.content

    # 하단에 참고 문헌(URL) 리스트 생성
    references = "\n\n※ 참고 기사 리스트\n"
    for idx, art in enumerate(news_data[:15]):
        references += f"{idx + 1}. {art['title']}\n   - {art['link']}\n"

    return ai_report + references


def send_email(subject, content):
    if not content:
        print("발송할 내용이 없습니다.")
        return False
    try:
        # 1. MIMEText 생성 시 utf-8 명시
        msg = MIMEText(content, 'plain', 'utf-8')

        # 2. 헤더 설정 (한글 깨짐 방지)
        msg['Subject'] = Header(subject, 'utf-8')
        msg['From'] = SENDER_EMAIL
        msg['To'] = ", ".join(RECEIVER_LIST)

        # 3. SMTP 발송 로직
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=20, local_hostname='localhost') as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PW)

            raw_string = msg.as_string()
            server.sendmail(SENDER_EMAIL, RECEIVER_LIST, raw_string)

        return True
    except Exception as e:
        print(f"이메일 발송 에러 발생: {e}")
        # 상세 에러 디버깅을 원하시면 아래 주석을 해제하세요.
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    news_list = get_recent_news()
    print(f"수집된 뉴스 개수: {len(news_list)}건")

    if news_list:
        print("\n--- OpenAI 분석 리포트 생성 중 ---")
        full_content = analyze_with_openai(news_list)

        if full_content:
            print("이메일 발송 중...")
            subject = f"[2026 반도체 전략 리포트] {datetime.now().strftime('%Y-%m-%d')} 투자 가이드"

            if send_email(subject, full_content):
                print(f"보고서 발송 완료")
            else:
                print("이메일 발송 실패")
    else:
        print("최근 일주일간 새로운 뉴스가 없어 리포트를 생성하지 않습니다.")