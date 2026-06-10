"""
OpenAI API 연결 및 동작 확인용 스크립트.

사용법:
    1) 환경변수에 API 키 설정
         PowerShell:  $env:OPENAI_API_KEY = "sk-..."
         CMD:         set OPENAI_API_KEY=sk-...
    2) 실행
         python test.py

    또는 모델 지정:
         python test.py gpt-4o-mini
"""
import os
import sys


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "gpt-5.5"

    api_key = "sk-xxxxxxxxxxxxxxxx"
    if not api_key:
        print("[실패] 환경변수 OPENAI_API_KEY가 설정되지 않았습니다.")
        print('  PowerShell:  $env:OPENAI_API_KEY = "sk-..."')
        sys.exit(1)

    try:
        from openai import OpenAI
    except ImportError:
        print("[실패] openai 패키지가 설치되지 않았습니다.  pip install openai")
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    print(f"모델: {model}")
    print("OpenAI API 호출 중...\n")

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "너는 간결하게 답하는 테스트 도우미야."},
                {"role": "user", "content": "연결 테스트입니다. 'OK'라고만 답해줘."},
            ],
            # GPT-5 계열(reasoning 모델)은 max_tokens 대신 max_completion_tokens 사용.
            # reasoning 토큰을 함께 소비하므로 한도를 충분히 줘야 응답이 비지 않음.
            max_completion_tokens=2000,
        )
    except Exception as e:
        print(f"[실패] API 호출 중 오류 발생: {type(e).__name__}: {e}")
        sys.exit(1)

    answer = resp.choices[0].message.content
    usage = resp.usage

    print("[성공] OpenAI API 연결 정상")
    print(f"  응답: {answer.strip()!r}")
    if usage:
        print(
            f"  토큰: prompt={usage.prompt_tokens}, "
            f"completion={usage.completion_tokens}, total={usage.total_tokens}"
        )


if __name__ == "__main__":
    main()
