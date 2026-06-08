"""일봉 조회 + 추세 계산 단독 테스트 (주문/텔레그램/LLM 없음).

미국 거래소 운영시간(한국시간 23:30~06:00, 썸머타임 22:30~05:00)에
실행해야 정상 데이터가 옵니다. 운영시간 외에는 데이터가 비거나 에러날 수 있음.

실행(프로젝트 루트에서): python test/test_trader.py
"""
import json
import sys
from pathlib import Path

# test/ 하위에서 실행되어도 kis, daily_trader를 찾을 수 있도록 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kis.client import KISClient
from daily_trader import compute_trend

if __name__ == "__main__":
    c = KISClient()
    print(f"환경: {c.settings.env}")
    closes = c.get_daily_prices("AAPL", "NASD", days=60)
    print(f"받은 일봉 개수: {len(closes)}")
    if closes:
        print(f"최근 5개 종가(과거→현재): {closes[-5:]}")
    if len(closes) >= 20:
        print("추세 지표:")
        print(json.dumps(compute_trend(closes), ensure_ascii=False, indent=2))
    else:
        print("데이터 부족: 휴장/운영시간 외이거나 모의투자 미지원 종목일 수 있음.")