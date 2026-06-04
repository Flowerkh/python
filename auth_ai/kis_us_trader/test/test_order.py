"""모의 주문 접수 → 즉시 취소 단독 테스트.

목적: KIS 미국주식 주문/취소 API, 거래소코드(NASD), TR ID(VTTT1002U/VTTT1004U) 검증.

방법:
  1) AAPL 현재가 조회
  2) 현재가의 80% 지정가로 1주 매수 접수 (체결 가능성 거의 0)
  3) rt_cd=0 확인 + 주문번호(ODNO) 추출
  4) 같은 주문번호로 즉시 취소
  5) rt_cd=0 확인

실행 조건:
  - 미국 거래소 운영시간(한국시간 23:30~06:00, 썸머타임 22:30~05:00)
  - KIS_ENV=paper (모의투자) — prod 환경에서는 실행 거부

실행(프로젝트 루트에서): python test/test_order.py
"""
import json
import sys
import time
from pathlib import Path

# test/ 하위에서 실행되어도 kis 패키지를 찾을 수 있도록 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kis.client import KISClient

SYMBOL = "AAPL"
EXCHANGE = "NASD"
QTY = 1
LIMIT_PCT = 0.80   # 현재가의 80% → 체결 안 되는 안전한 위치


def pp(label: str, data: dict) -> None:
    print(f"\n--- {label} ---")
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main() -> int:
    client = KISClient()
    env = client.settings.env
    print(f"환경: {env}")
    if env != "paper":
        print("❌ KIS_ENV가 paper가 아닙니다. 안전을 위해 중단합니다.")
        return 2

    # 1) 현재가
    price = client.get_last_price(SYMBOL, EXCHANGE)
    print(f"{SYMBOL} 현재가: ${price}")
    if price <= 0:
        print("❌ 현재가 0 또는 비정상. 미국장 운영시간에 다시 실행하세요.")
        return 2

    limit = round(price * LIMIT_PCT, 2)
    print(f"매수 지정가: ${limit} (현재가의 {int(LIMIT_PCT*100)}%) / 수량: {QTY}주")

    # 2) 매수 접수
    buy_res = client.order(SYMBOL, "buy", QTY, limit, EXCHANGE)
    pp("BUY 응답", buy_res)

    if buy_res.get("rt_cd") != "0":
        print(f"❌ 매수 실패: rt_cd={buy_res.get('rt_cd')}, msg={buy_res.get('msg1')}")
        return 1

    output = buy_res.get("output") or {}
    order_no = output.get("ODNO") or output.get("odno")
    if not order_no:
        print("❌ 주문번호(ODNO)를 응답에서 찾지 못했습니다. 출력 확인 필요.")
        return 1
    print(f"✅ 매수 접수 OK. 주문번호={order_no}")

    # KIS 측 주문 등록 안정화 대기
    time.sleep(2)

    # 3) 취소
    cancel_res = client.cancel_order(SYMBOL, order_no, QTY, EXCHANGE)
    pp("CANCEL 응답", cancel_res)

    if cancel_res.get("rt_cd") != "0":
        print(f"⚠️ 취소 실패: rt_cd={cancel_res.get('rt_cd')}, msg={cancel_res.get('msg1')}")
        print("   → 이미 체결되었거나, 원주문번호/필드 형식이 잘못되었을 수 있음.")
        return 1

    print("✅ 취소 OK. 주문/취소 흐름 검증 완료.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
