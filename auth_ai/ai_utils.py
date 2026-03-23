import os
from dotenv import load_dotenv
from openai import OpenAI
import google.generativeai as genai
from pathlib import Path


# 공용 환경 변수 로드 함수
def load_ai_keys():
    # 현재 파일(ai_utils.py) 기준으로 상위 폴더의 .env를 찾음
    current_dir = Path(__file__).resolve().parent
    env_path = current_dir / '.env'  # auth_ai/.env 위치 기준

    # 만약 위 경로에 없다면 프로젝트 루트도 확인 (유연성)
    if not env_path.exists():
        env_path = current_dir.parent / '.env'

    load_dotenv(dotenv_path=env_path)
    return {
        "openai": os.getenv("OPENAI_API_KEY"),
        "gemini": os.getenv("GEMINI_API_KEY")
    }


# 클라이언트 초기화 함수
def get_ai_client(model_choice):
    keys = load_ai_keys()

    if model_choice == "OpenAI":
        if keys["openai"]:
            return OpenAI(api_key=keys["openai"]), None
        else:
            return None, "OpenAI API 키가 없습니다."

    elif model_choice == "Google Gemini":
        if keys["gemini"]:
            genai.configure(api_key=keys["gemini"])
            model = genai.GenerativeModel('gemini-1.5-flash')  # 최신 모델명 권장
            return model, None
        else:
            return None, "Gemini API 키가 없습니다."

    return None, "모델 선택이 잘못되었습니다."