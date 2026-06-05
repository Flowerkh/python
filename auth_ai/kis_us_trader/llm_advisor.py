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
You are a trading-signal assistant for a PAPER-TRADING experiment.
You are given recent market data for one US stock. Based ONLY on the data
provided, output a single trade suggestion.

Rules:
- Respond with ONLY a JSON object, no markdown, no extra text.
- Schema: {"action": "buy"|"sell"|"hold", "confidence": <integer 0-100>, "reason": "<short Korean, <=200 chars>"}
- The "reason" MUST be written in Korean (한국어).
- Be conservative: if the data is weak or unclear, prefer "hold" with low confidence.
- You are NOT a licensed advisor; this is an automated experiment with human approval downstream.
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
        f"Ticker: {symbol}\n"
        f"Market data (JSON):\n{json.dumps(market_data, ensure_ascii=False)}\n\n"
        f"Give your trade suggestion as JSON."
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
        "change_pct": 1.2,
        "recent_prices": [305, 307, 306, 309, 311, 312.5],
        "note": "demo data, not real",
    }
    print(f"[테스트] 모델={MODEL} 로 AAPL 제안 요청...")
    advice = get_advice("AAPL", demo_data)
    print(json.dumps(advice, ensure_ascii=False, indent=2))
    print("\n※ 이것은 데모 데이터에 대한 LLM의 제안일 뿐, 투자 추천이 아닙니다.")