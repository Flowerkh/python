import os
from dotenv import load_dotenv, find_dotenv
from openai import OpenAI
import google.generativeai as genai


# 공용 환경 변수 로드 함수
def load_ai_keys():
    load_dotenv(find_dotenv(raise_error_if_not_found=True))
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
            model = genai.GenerativeModel('gemini-flash-latest')  # 최신 모델명 권장
            return model, None
        else:
            return None, "Gemini API 키가 없습니다."

    return None, "모델 선택이 잘못되었습니다."


def generate_text(model_choice: str, client, gemini_model, prompt: str) -> str:
    if model_choice == "OpenAI":
        if client is None:
            raise ValueError("OpenAI 클라이언트가 초기화되지 않았습니다.")
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    else:
        if gemini_model is None:
            raise ValueError("Gemini 모델이 초기화되지 않았습니다.")
        return gemini_model.generate_content(prompt).text