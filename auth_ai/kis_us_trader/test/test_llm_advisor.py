"""llm_advisor 의 순수 검증 함수 단위 테스트 — 네트워크/OpenAI 호출 0.

sanitize_advice / foreign_tickers_in_reason 만 검증(OpenAI 호출 경로는 제외).

실행(프로젝트 루트): python test/test_llm_advisor.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llm_advisor import foreign_tickers_in_reason, sanitize_advice

PASS = "[OK ]"
FAIL = "[FAIL]"
_fails = 0


def check(cond: bool, label: str) -> None:
    global _fails
    if cond:
        print(f"  {PASS} {label}")
    else:
        print(f"  {FAIL} {label}")
        _fails += 1


print("\n=== 1) foreign_tickers_in_reason — 교차 오염 탐지 ===")
check(foreign_tickers_in_reason("AAPL 추세가 좋아 매수 권장", "AAPL") == [],
      "자기 종목(AAPL)만 언급 → []")
check(foreign_tickers_in_reason("NVDA 가 더 매력적임", "AAPL") == ["NVDA"],
      "다른 화이트리스트 종목(NVDA) 언급 → ['NVDA']")
check(foreign_tickers_in_reason("AMD 와 NVDA 가 강세", "AAPL") == ["AMD", "NVDA"],
      "다중 외부 ticker → 정렬 ['AMD','NVDA']")
check(foreign_tickers_in_reason("AI 및 HBM 수요 증가, ETF 자금 유입", "AAPL") == [],
      "일반 영어 약어(AI/HBM/ETF)는 비화이트리스트 → 오탐 없음 []")
check(foreign_tickers_in_reason("", "AAPL") == [], "빈 reason → []")
check(foreign_tickers_in_reason("nvda 소문자", "AAPL") == [],
      "소문자 ticker 는 매칭 안 함(LLM 은 대문자 ticker 사용 가정)")
check(foreign_tickers_in_reason("TSM 동반 강세", "NVDA") == ["TSM"],
      "현재 종목이 NVDA 일 때 TSM 언급 → ['TSM']")
# CJK-glued (한국어 조사 부착) — 구 \b 정규식이 놓치던 케이스(review #3 회귀)
check(foreign_tickers_in_reason("NVDA가 AAPL보다 낫다", "AAPL") == ["NVDA"],
      "조사 부착 'NVDA가' → ['NVDA'] (CJK glued)")
check(foreign_tickers_in_reason("NVDA를 추천", "AAPL") == ["NVDA"], "'NVDA를' → ['NVDA']")
check(foreign_tickers_in_reason("여기서NVDA강세", "AAPL") == ["NVDA"],
      "한글에 둘러싸인 'NVDA' → ['NVDA']")
check(foreign_tickers_in_reason("AVGO와 LRCX 강세", "AAPL") == ["AVGO", "LRCX"],
      "glued+space 혼합 둘 다 탐지")
check(foreign_tickers_in_reason("XNVDA 추세", "AAPL") == [],
      "Latin 으로 붙은 'XNVDA' 는 별개 토큰(비화이트리스트) → [] (오탐 방지)")


print("\n=== 2) sanitize_advice — 정규화 ===")
r = sanitize_advice({"action": "buy", "confidence": 85, "reason": "상승 추세"}, "AAPL")
check(r == {"action": "buy", "confidence": 85, "reason": "상승 추세", "flagged": []},
      "정상 buy → 그대로 + flagged []")

check(sanitize_advice({"action": "long", "confidence": 90, "reason": "x"}, "AAPL")["action"] == "hold",
      "잘못된 action('long') → hold")

check(sanitize_advice({"action": "buy", "confidence": "abc", "reason": "x"}, "AAPL")["confidence"] == 0,
      "confidence 비정수('abc') → 0")
check(sanitize_advice({"action": "buy", "confidence": 150, "reason": "x"}, "AAPL")["confidence"] == 100,
      "confidence 150 → 100 클램프")
check(sanitize_advice({"action": "buy", "confidence": -5, "reason": "x"}, "AAPL")["confidence"] == 0,
      "confidence -5 → 0 클램프")

long_reason = "가" * 300
check(len(sanitize_advice({"action": "hold", "confidence": 10, "reason": long_reason}, "AAPL")["reason"]) == 200,
      "reason 300자 → 200자 컷")

# review #12/#13 회귀: 공백 action / 문자열·float confidence
check(sanitize_advice({"action": " buy ", "confidence": 80, "reason": "x"}, "AAPL")["action"] == "buy",
      "action ' buy '(공백) → strip → buy")
check(sanitize_advice({"action": "buy\n", "confidence": 80, "reason": "x"}, "AAPL")["action"] == "buy",
      "action 'buy\\n'(개행) → buy")
check(sanitize_advice({"action": "buy", "confidence": "85.7", "reason": "x"}, "AAPL")["confidence"] == 86,
      "confidence '85.7'(문자열 소수) → 86")
check(sanitize_advice({"action": "buy", "confidence": 85.7, "reason": "x"}, "AAPL")["confidence"] == 86,
      "confidence 85.7(float) → 86")
check(sanitize_advice({"action": "buy", "confidence": "abc", "reason": "x"}, "AAPL")["confidence"] == 0,
      "confidence 'abc'(비숫자) → 0(폴백 유지)")


print("\n=== 3) sanitize_advice — 교차 오염 픽 reject ===")
poisoned = sanitize_advice(
    {"action": "buy", "confidence": 95, "reason": "AAPL 보다 NVDA 가 더 좋다"}, "AAPL")
check(poisoned["action"] == "hold", "외부 ticker 섞인 buy → hold 강등")
check(poisoned["confidence"] == 0, "오염 픽 confidence → 0")
check(poisoned["flagged"] == ["NVDA"], "flagged 에 NVDA 기록")

clean = sanitize_advice({"action": "buy", "confidence": 88, "reason": "AAPL 자체 추세 양호"}, "AAPL")
check(clean["action"] == "buy" and clean["flagged"] == [], "자기 종목만 언급 → buy 유지")


print(f"\n총 {_fails}건 실패")
sys.exit(1 if _fails else 0)
