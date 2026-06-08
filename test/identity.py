"""
유전자 DTC 검사 결과(data.json)를 종합하여
'나의 아이덴티티'를 한 줄로 정의하는 스크립트.
"""

import json
import sys
from pathlib import Path


# ── 프롬프트 설계 ───────────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
당신은 유전자 DTC(소비자 직접 의뢰) 검사 결과를 해석하는 유전체 분석가이자,
복잡한 데이터를 한 문장의 강렬한 카피로 압축하는 카피라이터입니다.

[해석 원칙]
- topHighList: 상대적으로 양호하거나 '강점'으로 작용하는 형질입니다.
- topLowList: 주의가 필요하거나 '약점·리스크'로 작용하는 형질입니다.
- 각 항목의 '등급'(안심/낮음/보통/주의/높음 등)을 형질의 성격에 맞게 해석하세요.
  · 위험도·민감도가 '높음/주의' → 조심해야 할 신호
  · 위험·수치가 '안심/낮음' → 안정적이거나 둔감한 특성
- DTC 검사는 의료 진단이 아닙니다. 질병을 단정하거나 진단하지 마세요.
- 검사 항목명을 그대로 나열하지 말고, 여러 형질의 의미를 '종합'하여
  한 사람의 정체성으로 승화시키세요. 강점은 살리고 약점은 자기인식으로 녹이세요.

[아이덴티티 문장 형식] 아래 구조를 반드시 따르세요.
  "[강점 묘사]를 지녔지만 [관리 포인트]가 필요한 '[페르소나 별명]'"
  · 예: "안정적인 순환과 담대한 미각을 지녔지만 피부와 발목 관리가 필요한 '담담한 미식가'"
  · 전체 문장은 공백 포함 40자 내외(35~45자)로 쓰세요. 너무 짧게 압축하지 마세요.
  · 강점과 약점을 각각 자연스러운 구절로 풀어 묘사하되, 검사 항목을 그대로 나열하진 마세요.
  · 끝의 페르소나 별명은 작은따옴표로 감싸고, 공백 포함 5~9자의 콘셉트 네이밍으로.
  · 별명은 위트와 유머가 살아있게! 말장난·반전·의외의 조합·드립을 적극 활용하세요.
    피식 웃음이 나거나 "오 센스있다" 싶은 별명을 노리세요. 진부하고 점잖은 표현은 금지.
    예: '카페인 청정구역', '겉바속촉 인간', '발목만 조심하면 무적', '미각계의 대식가',
        '노화 거부 위원회', '간 보는 미식가' 처럼 재치있게.
  · 별명은 형질을 비유·드립으로 압축한 창의적 표현(밈·직업·캐릭터·동물·반전 등 자유).

[출력 형식] 아래 JSON 객체 '하나만' 출력하세요. 다른 텍스트는 금지합니다.
{
  "identity": "위 형식을 따른 40자 내외의 한 문장 (페르소나 별명을 작은따옴표로 포함)",
  "persona": "페르소나 별명만 (작은따옴표 없이, 5~9자)",
  "keywords": ["핵심 키워드 3개"],
  "rationale": "그렇게 정의한 근거를 한 줄로"
}"""

USER_TEMPLATE = """\
다음은 나의 유전자 DTC 검사 결과입니다.
강점(topHighList)과 약점(topLowList)을 종합하여,
나의 아이덴티티를 한 줄로 정의해주세요.

```json
{data}
```"""
# ────────────────────────────────────────────────────────────────────────────


def build_messages(data: dict) -> list:
    data_str = json.dumps(data, ensure_ascii=False, indent=2)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_TEMPLATE.format(data=data_str)},
    ]


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "gpt-5.5"
    data_path = sys.argv[2] if len(sys.argv) > 2 else "data6.json"

    p = Path(data_path)
    if not p.exists():
        p = Path(__file__).parent / data_path
    if not p.exists():
        print(f"[실패] 데이터 파일을 찾을 수 없습니다: {data_path}")
        sys.exit(1)

    data = json.loads(p.read_text(encoding="utf-8"))

    #openAI API KEY
    api_key = "openAI API KEY"
    if not api_key:
        print("[실패] 환경변수 OPENAI_API_KEY가 설정되지 않았습니다.")
        print('  PowerShell:  $env:OPENAI_API_KEY = "sk-..."')
        sys.exit(1)

    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    messages = build_messages(data)

    print(f"모델: {model}  |  데이터: {p.name}")
    print("아이덴티티 생성 중...\n")

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            max_completion_tokens=2000,
        )
    except Exception as e:
        print(f"[실패] API 호출 오류: {type(e).__name__}: {e}")
        sys.exit(1)

    raw = resp.choices[0].message.content
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        print("[경고] JSON 파싱 실패. 원문을 출력합니다.\n")
        print(raw)
        return

    print("=" * 50)
    print(f"  나의 아이덴티티")
    print("=" * 50)
    print(f"  ▶ {result.get('identity', '(없음)')}")
    if result.get("persona"):
        print(f"  페르소나: '{result['persona']}'")
    print("-" * 50)
    kws = result.get("keywords", [])
    if kws:
        print(f"  키워드: {' · '.join(kws)}")
    if result.get("rationale"):
        print(f"  근거  : {result['rationale']}")
    print("=" * 50)


if __name__ == "__main__":
    main()
