import google.generativeai as genai

# 1. API 키 설정 (보내주신 키 적용)
API_KEY = ""
genai.configure(api_key=API_KEY)

# 2. 모델 설정 (Gemini 1.5 Flash 사용)
model = genai.GenerativeModel('gemini-1.5-flash')


# 3. 테스트 질문 전송
def test_gemini():
    try:
        prompt = "안녕 제미나이! 너와 내가 파이썬으로 연결된 게 맞아? 짧게 답변해줘."
        response = model.generate_content(prompt)

        print("--- 테스트 결과 ---")
        print(response.text)
        print("-------------------")

    except Exception as e:
        print(f"에러가 발생했습니다: {e}")


if __name__ == "__main__":
    test_gemini()