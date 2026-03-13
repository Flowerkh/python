# 🚀 Gemini Pro 블로그 & 인스타 자동화 프로그램 매뉴얼

이 매뉴얼은 Python 3.7 환경에서 Google Gemini API를 사용하여 블로그 포스팅을 자동 생성하는 프로그램의 설정 및 실행 방법을 담고 있습니다.

## 1. 환경 준비 (Environment Setup)

### 필수 라이브러리 설치
```bash
python -m pip install -U streamlit google-generativeai python-dotenv Pillow
python -m streamlit run blog_app.py
```

### 실행용 진입점 파일
run_app.py

### 제미나이 API 사용 버전 확인
https://generativelanguage.googleapis.com/v1/models?key={API_KEY}
