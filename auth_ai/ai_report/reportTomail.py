import os
import re
import time
import requests
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SENDER_PW = os.getenv("SENDER_PW")
SENDER_EMAIL = "mbp.prd@macrogen.com"
RECEIVER_LIST = [
    "sj99146@macrogen.com"
    , "hoban@macrogen.com"
    , "kimjihan@macrogen.com"
]
#LOG_FILE = "/var/log/httpd/error_log"  # 실서버 경로
LOG_FILE = "C:/Users/김경하/Desktop/기타/error_log"
POS_FILE = "tmp/log_last_pos.txt"

# 1. AI 분석 함수 (Gemini API - requests 방식)
def get_ai_analysis(logs, is_security=False):
    if not logs: return ""
    role = "보안 전문가" if is_security else "PHP 개발 전문가"
    prompt = f"당신은 {role}입니다. 로그를 분석하여 원인과 해결책을 번호 순서대로 한국어로 요약하세요.\n\n{logs}"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={GEMINI_API_KEY}"

    max_retry = 3
    for attempt in range(max_retry):
        try:
            res = requests.post(url,
                headers={"Content-Type": "application/json"},
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=30
            )
            return res.json()['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            print(f"AI 분석 실패 ({attempt+1}/{max_retry}): {e}")
            if attempt < max_retry - 1:
                wait = (attempt + 1) * 10
                print(f"{wait}초 후 재시도...")
                time.sleep(wait)

    return "AI 분석 실패"

# 2. 로그 증분 분석 함수
def get_new_logs(file_path):
    exclude_k = ["php notice", "php warning", "undefined variable", "missing argument", '"result_cd":"s"',
                 "### send_data", "### url"]
    security_k = ["not found", "denied", "script not found"]

    normal_errors = []
    security_threats = []

    if not os.path.exists(file_path): return "", "", 0
    current_size = os.path.getsize(file_path)

    last_pos = 0
    if os.path.exists(POS_FILE):
        with open(POS_FILE, 'r') as f:
            content = f.read().strip()
            last_pos = int(content) if content else 0

    print(f"-- 디버깅: 이전 위치={last_pos}, 현재 파일크기={current_size}")

    if current_size < last_pos:
        print("-- 디버깅: 로그 로테이션 감지! 처음부터 읽습니다.")
        last_pos = 0
    elif current_size == last_pos:
        print("-- 디버깅: 추가된 로그가 용량상 전혀 없습니다.")
        return "", "", last_pos

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        f.seek(last_pos)

        for line in f:
            line_lower = line.lower()
            if any(ex in line_lower for ex in exclude_k): continue

            time_match = re.search(r'(\d{2}):\d{2}:\d{2}', line)
            if time_match:
                hour = int(time_match.group(1))
                if 0 <= hour < 6 and any(sk in line_lower for sk in security_k):
                    security_threats.append(line.strip())
                elif "[:error]" in line_lower and "script" not in line_lower:
                    normal_errors.append(line.strip())

        new_pos = f.tell()
        with open(POS_FILE, 'w') as f_pos:
            f_pos.write(str(new_pos))

    return "\n".join(normal_errors), "\n".join(security_threats), new_pos

def send_email(subject, content):
    try:
        msg = MIMEText(content, 'plain', 'utf-8')
        msg['Subject'] = Header(subject, 'utf-8')
        msg['From'] = SENDER_EMAIL
        msg['To'] = ", ".join(RECEIVER_LIST)

        with smtplib.SMTP("smtp.gmail.com", 587, timeout=20, local_hostname='localhost') as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PW)
            server.sendmail(SENDER_EMAIL, RECEIVER_LIST, msg.as_string())
        return True
    except Exception as e:
        print(f"이메일 발송 에러: {e}")
        return False

# 3. 메인 실행
if __name__ == "__main__":
    errors, threats, new_pos = get_new_logs(LOG_FILE)
    report = ""

    if errors:
        print("일반 에러 분석 중...")
        report += "### [시스템 에러 분석 보고]\n"
        report += get_ai_analysis(errors) + "\n\n"
        report += "--- [일반 에러 원본 로그] ---\n"
        report += errors + "\n\n"
        report += "=" * 50 + "\n\n"

    if threats:
        print("보안 위협 분석 중...")
        report += "### [보안 위협 분석 보고]\n"
        report += get_ai_analysis(threats, True) + "\n\n"
        report += "--- [보안 위협 원본 로그] ---\n"
        report += threats + "\n\n"
        report += "=" * 50 + "\n\n"

    if report:
        print("이메일 발송 중...")
        error_count = len(errors.split('\n')) if errors else 0
        threat_count = len(threats.split('\n')) if threats else 0
        subject = f"[서버 알림] 에러({error_count}건) 및 보안({threat_count}건) 통합 분석 보고서"

        if send_email(subject, report):
            print(f"보고서 발송 완료 (에러: {error_count}, 보안: {threat_count})")
        else:
            print("이메일 발송 실패")
    else:
        print("새로 발생한 특이 로그가 없습니다.")