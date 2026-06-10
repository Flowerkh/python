"""LLM 판단 모듈.

시세/지표 데이터를 OpenAI에 넣어 매매 '제안'을 구조화(JSON)로 받습니다.
반환 형식: {"action": "buy|sell|hold", "confidence": 0~100, "reason": "..."}

⚠️ 매우 중요한 한계:
  - LLM은 실시간 시장을 모릅니다. 반드시 우리가 데이터를 넣어줘야 합니다.
  - LLM은 환각/비결정성이 있어 틀리거나 답이 바뀔 수 있습니다.
  - 따라서 이 출력은 '제안'일 뿐이며, 실제 주문은 사람 승인(텔레그램)과
    코드 안전장치를 반드시 거칩니다. 투자 추천이 아닙니다.

단독 테스트:
  python llm_advisor.py
"""
import json
import os

from dotenv import load_dotenv

load_dotenv()

try:
    from openai import OpenAI
except ImportError:
    raise SystemExit("openai 가 필요합니다:  pip install openai")

_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # 저렴한 기본값

# 시스템 프롬프트: 역할과 출력 형식을 엄격히 지정
SYSTEM_PROMPT = """\
당신은 모의투자(PAPER-TRADING) 실험을 위한 매매 신호 보조자입니다.
하나의 미국 주식에 대한 최근 시장 데이터가 주어집니다. 오직 제공된 데이터에만
근거하여 매매 제안 한 건을 출력하세요.

규칙:
- 오직 JSON 객체 하나만 응답하세요. 마크다운/추가 설명 금지.
- 스키마: {"action": "buy"|"sell"|"hold", "confidence": <0~100 정수>, "reason": "<한국어 짧은 사유, 200자 이내>"}
- "reason" 필드는 반드시 한국어로 작성하세요.
- 데이터의 "signal_strength" 는 '추세 강도/변동성' 라벨이며 '방향' 신호가 아닙니다.
  매수/매도 방향은 오직 price·sma5·sma20·sma5_above_sma20·change_5d_pct 등 데이터 필드로만
  판단하고, 라벨 자체가 특정 방향(매수 또는 매도)을 선호하도록 해석하지 마세요.
    * "weak"     → 추세 미약/저변동. 반드시 "hold" 를 출력하고 confidence 는 50 이하로 한정하세요.
    * "moderate" → 움직임 보통. 데이터 근거가 약하면 hold 를 권장. confidence 는 일반적으로 50~75.
    * "strong"   → 움직임이 큼(변동성 높음). 방향이 명확하다는 뜻이 아니며, 큰 변동은 오히려
                   신중할 이유입니다. 방향은 데이터로만 판단하고, 데이터가 한 방향을 충분히
                   뒷받침할 때에만 confidence 를 높게 부여하세요.
- 위 라벨은 코드가 산출한 결정적 값이므로 임의로 무시/재해석하지 마세요.
- 당신은 공인된 투자자문가가 아닙니다. 본 시스템은 후단에서 사람의 승인을 거치는 자동화 실험입니다.
"""


def get_advice(symbol: str, market_data: dict) -> dict:
    """시세/지표 dict를 받아 매매 제안 dict를 반환.

    market_data 예:
      {"price": 312.5, "sma5": 310.1, "sma20": 305.7,
       "change_pct": 1.2, "recent_prices": [...]}
    """
    if not _API_KEY:
        raise RuntimeError(".env 에 OPENAI_API_KEY 가 없습니다.")

    client = OpenAI(api_key=_API_KEY)

    user_content = (
        f"종목코드: {symbol}\n"
        f"시장 데이터(JSON):\n{json.dumps(market_data, ensure_ascii=False)}\n\n"
        f"매매 제안을 JSON 으로 출력하세요."
    )

    kwargs = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "response_format": {"type": "json_object"},  # JSON 강제
    }
    # gpt-5.x / o1 / o3 계열은 temperature 기본값(1)만 허용. 그 외에는 일관성 위해 낮게.
    if not MODEL.startswith(("gpt-5", "o1", "o3")):
        kwargs["temperature"] = 0.2
    resp = client.chat.completions.create(**kwargs)

    raw = resp.choices[0].message.content
    data = json.loads(raw)

    # 출력 검증 및 정규화 (LLM이 형식을 어겨도 안전하게)
    action = str(data.get("action", "hold")).lower()
    if action not in ("buy", "sell", "hold"):
        action = "hold"
    try:
        confidence = int(data.get("confidence", 0))
    except (TypeError, ValueError):
        confidence = 0
    confidence = max(0, min(100, confidence))
    reason = str(data.get("reason", ""))[:200]

    return {"action": action, "confidence": confidence, "reason": reason}


# 단독 테스트: 가상의 시세 데이터로 호출
if __name__ == "__main__":
    demo_data = {
        "price": 312.5,
        "sma5": 310.1,
        "sma20": 305.7,
        "change_5d_pct": 1.2,
        "signal_strength": "moderate",
        "recent_prices": [305, 307, 306, 309, 311, 312.5],
        "note": "demo data, not real",
    }
    print(f"[테스트] 모델={MODEL} 로 AAPL 제안 요청...")
    advice = get_advice("AAPL", demo_data)
    print(json.dumps(advice, ensure_ascii=False, indent=2))
    print("\n※ 이것은 데모 데이터에 대한 LLM의 제안일 뿐, 투자 추천이 아닙니다.")