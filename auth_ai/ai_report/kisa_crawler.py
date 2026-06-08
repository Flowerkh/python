#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KISA 보호나라 보안공지 크롤러
- 주기적으로 실행하여 새 글 감지 시 이메일 알림
- cron 등록 예시: */30 * * * * /usr/bin/python3 /path/to/kisa_crawler.py
"""

import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
import os
import logging
from datetime import datetime

# ──────────────────────────────────────────────
# ✅ 설정값 (환경에 맞게 수정하세요)
# ──────────────────────────────────────────────

# 크롤링 대상
TARGET_URL = "https://www.boho.or.kr/kr/bbs/list.do?menuNo=205020&bbsId=B0000133"

# 이메일 설정
EMAIL_CONFIG = {
    "smtp_host": "smtp.gmail.com",       # SMTP 서버 (Gmail 예시)
    "smtp_port": 587,                    # TLS 포트
    "sender": "your_email@gmail.com",    # 발신자 이메일
    "password": "your_app_password",     # Gmail 앱 비밀번호 (2FA 필요)
    "recipients": [                      # 수신자 목록 (여러 명 가능)
        "recipient@example.com",
    ],
}

# 이전 상태 저장 파일 (새 글 감지용)
STATE_FILE = "/tmp/kisa_crawler_state.json"

# 로그 파일
LOG_FILE = "/tmp/kisa_crawler.log"

# ──────────────────────────────────────────────
# 로깅 설정
# ──────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 크롤링
# ──────────────────────────────────────────────

def fetch_posts():
    """보안공지 목록 크롤링 (공지 제외 일반글만)"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        res = requests.get(TARGET_URL, headers=headers, timeout=10)
        res.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"크롤링 실패: {e}")
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    rows = soup.select("table tbody tr")

    posts = []
    for row in rows:
        cols = row.find_all("td")
        if not cols or len(cols) < 5:
            continue

        num_text = cols[0].get_text(strip=True)

        # 공지(숫자 아닌 것) 제외
        if not num_text.isdigit():
            continue

        title_tag = cols[1].find("a")
        if not title_tag:
            continue

        title = title_tag.get_text(strip=True)
        link = "https://www.boho.or.kr" + title_tag["href"]
        views = cols[2].get_text(strip=True)
        has_attachment = bool(cols[3].find("img") or cols[3].get_text(strip=True))
        date = cols[4].get_text(strip=True)

        posts.append({
            "num": int(num_text),
            "title": title,
            "link": link,
            "views": views,
            "has_attachment": "📎 있음" if has_attachment and cols[3].get_text(strip=True) else "없음",
            "date": date,
        })

    logger.info(f"총 {len(posts)}개 게시글 파싱 완료")
    return posts


# ──────────────────────────────────────────────
# 상태 저장/로드
# ──────────────────────────────────────────────

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"last_num": 0}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ──────────────────────────────────────────────
# 이메일 발송
# ──────────────────────────────────────────────

def send_email(new_posts):
    """새 게시글 목록을 이메일로 발송"""
    cfg = EMAIL_CONFIG

    subject = f"[KISA 보안공지] 새 글 {len(new_posts)}건 등록됨 ({datetime.now().strftime('%Y-%m-%d %H:%M')})"

    # HTML 본문 생성
    rows_html = ""
    for p in new_posts:
        attachment_badge = (
            '<span style="color:#e67e22;">📎 첨부있음</span>'
            if "있음" in p["has_attachment"] else "—"
        )
        rows_html += f"""
        <tr>
            <td style="padding:8px;border:1px solid #ddd;text-align:center;">{p['num']}</td>
            <td style="padding:8px;border:1px solid #ddd;">
                <a href="{p['link']}" style="color:#2c7be5;text-decoration:none;">{p['title']}</a>
            </td>
            <td style="padding:8px;border:1px solid #ddd;text-align:center;">{attachment_badge}</td>
            <td style="padding:8px;border:1px solid #ddd;text-align:center;">{p['date']}</td>
        </tr>
        """

    html_body = f"""
    <html><body style="font-family:Arial,sans-serif;color:#333;">
        <h2 style="color:#c0392b;">🔔 KISA 보호나라 보안공지 새 글 알림</h2>
        <p>새로운 보안공지가 <strong>{len(new_posts)}건</strong> 등록되었습니다.</p>
        <table style="border-collapse:collapse;width:100%;max-width:800px;">
            <thead>
                <tr style="background:#2c3e50;color:#fff;">
                    <th style="padding:10px;border:1px solid #ddd;width:60px;">번호</th>
                    <th style="padding:10px;border:1px solid #ddd;">제목</th>
                    <th style="padding:10px;border:1px solid #ddd;width:90px;">첨부파일</th>
                    <th style="padding:10px;border:1px solid #ddd;width:100px;">게시일</th>
                </tr>
            </thead>
            <tbody>{rows_html}</tbody>
        </table>
        <br>
        <p style="font-size:12px;color:#999;">
            출처: <a href="{TARGET_URL}">KISA 보호나라 보안공지</a><br>
            발송 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </p>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg["sender"]
    msg["To"] = ", ".join(cfg["recipients"])
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"]) as server:
            server.ehlo()
            server.starttls()
            server.login(cfg["sender"], cfg["password"])
            server.sendmail(cfg["sender"], cfg["recipients"], msg.as_string())
        logger.info(f"이메일 발송 완료 → {cfg['recipients']}")
    except Exception as e:
        logger.error(f"이메일 발송 실패: {e}")


# ──────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────

def main():
    logger.info("===== KISA 크롤러 시작 =====")

    posts = fetch_posts()
    if not posts:
        logger.warning("게시글을 가져오지 못했습니다.")
        return

    state = load_state()
    last_num = state.get("last_num", 0)
    latest_num = posts[0]["num"]  # 가장 최신 번호

    logger.info(f"저장된 마지막 번호: {last_num} / 현재 최신 번호: {latest_num}")

    # 새 글 필터링
    new_posts = [p for p in posts if p["num"] > last_num]

    if new_posts:
        logger.info(f"새 글 {len(new_posts)}건 감지!")
        for p in new_posts:
            logger.info(f"  [{p['num']}] {p['title']} ({p['date']}) 첨부:{p['has_attachment']}")
        send_email(new_posts)
        save_state({"last_num": latest_num})
    else:
        logger.info("새 글 없음.")

    logger.info("===== 크롤러 종료 =====\n")


if __name__ == "__main__":
    main()