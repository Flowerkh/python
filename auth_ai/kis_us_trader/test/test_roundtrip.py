"""AAPL 1주 BUY → 30초 후 SELL 왕복 검증.

목적: KIS 미국 주문 API의 BUY/SELL 양방향 + 체결 + 잔고 sync까지 한 번에 검증.
설계 안전장치 #4 '잔고 sync fail-closed'의 토대.

흐름:
  1) AAPL 현재가 조회
  2) 현재가 +0.5% 지정가로 1주 BUY 접수
  3) 체결 대기(최대 30초). get_balance + parse_balance_positions로 확인.
  4) 체결됐으면 → 현재가 -0.5%로 1주 SELL 접수 → 체결 확인
     체결 안 됐으면 → BUY 자동 취소 → 안전 종료(exit 3)
  5) 모든 단계의 텔레그램 알림은 KISClient가 자동 발송

실행 조건:
  - 미국 정규장(한국시간 22:30~05:00 DST / 23:30~06:00 표준)
  - KIS_ENV=paper. prod에서는 실행 거부.

실행(프로젝트 루트): python test/test_roundtrip.py

주의: 이건 실제 주문이 체결됩니다(모의). 1주만 사거나 팔게 만들어져 있지만 실수로
prod로 돌리면 진짜 돈이 움직입니다. 코드가 prod를 거부하지만 .env도 확인하세요.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kis.client import KISClient, parse_balance_positions

SYMBOL = "AAPL"
EXCHANGE = "NASD"
QTY = 1
FILL_WAIT_SECONDS = 30  # 체결 대기 최대 시간
POLL_INTERVAL = 5       # 잔고 폴링 간격


def pp(label: str, data) -> None:
    print(f"\n--- {label} ---")
    if isinstance(data, (dict, list)):
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(data)


def wait_for_qty(client: KISClient, target_qty: int, max_seconds: int) -> tuple[bool, int]:
    """잔고에서 SYMBOL 수량이 target_qty가 될 때까지 폴링. (도달 여부, 마지막 관측 수량)"""
    deadline = time.monotonic() + max_seconds
    last_qty = -1
    while time.monotonic() < deadline:
        resp = client.get_balance(EXCHANGE)
        positions = parse_balance_positions(resp)
        last_qty = positions.get(SYMBOL, {}).get("qty", 0)
        print(f"  [폴링 t={int(time.monotonic())}s] {SYMBOL} 보유 = {last_qty}주 (목표 {target_qty})")
        if last_qty == target_qty:
            return True, last_qty
        time.sleep(POLL_INTERVAL)
    return False, last_qty


def main() -> int:
    client = KISClient()
    env = client.settings.env
    print(f"환경: {env}")
    if env != "paper":
        print("❌ KIS_ENV가 paper가 아닙니다. 안전을 위해 중단.")
        return 2

    # 0) 초기 잔고 — 이미 AAPL 보유면 정확한 왕복 검증이 어려우므로 경고
    initial = parse_balance_positions(client.get_balance(EXCHANGE))
    initial_qty = initial.get(SYMBOL, {}).get("qty", 0)
    pp("초기 보유", initial)
    if initial_qty != 0:
        print(f"⚠️ {SYMBOL} 이미 {initial_qty}주 보유 중. 왕복 검증 정확도가 떨어집니다.")
        print("   계속 진행하지만, 최종 검증은 '초기+1 → 초기' 변화로 본다.")

    target_after_buy = initial_qty + QTY

    # 1) 현재가
    price = client.get_last_price(SYMBOL, EXCHANGE)
    print(f"\n{SYMBOL} 현재가: ${price}")
    if price <= 0:
        print("❌ 현재가 0. 미국장 운영시간에 다시 시도.")
        return 2

    # 2) BUY 접수 — 현재가 +0.5% (체결 유도)
    buy_limit = round(price * 1.005, 2)
    print(f"\n[BUY] {SYMBOL} {QTY}주 @ ${buy_limit} (현재가의 100.5%, 체결 유도)")
    buy_res = client.order(SYMBOL, "buy", QTY, buy_limit, EXCHANGE)
    pp("BUY 응답", buy_res)

    if buy_res.get("rt_cd") != "0":
        print(f"❌ BUY 접수 실패: {buy_res.get('msg1')}")
        return 1

    buy_odno = (buy_res.get("output") or {}).get("ODNO")
    print(f"✅ BUY 접수 OK. 주문번호={buy_odno}")

    # 3) 체결 대기
    print(f"\n[WAIT] 최대 {FILL_WAIT_SECONDS}초 동안 잔고 폴링 ({POLL_INTERVAL}초 간격)")
    filled, observed_qty = wait_for_qty(client, target_after_buy, FILL_WAIT_SECONDS)

    if not filled:
        print(f"\n⚠️ BUY 미체결: 목표 {target_after_buy}주, 관측 {observed_qty}주.")
        print(f"   → 안전을 위해 BUY 주문 취소 시도(주문번호 {buy_odno}).")
        if buy_odno:
            cancel_res = client.cancel_order(SYMBOL, buy_odno, QTY, EXCHANGE)
            pp("CANCEL 응답", cancel_res)
        return 3

    print(f"\n✅ BUY 체결 확인 — {SYMBOL} {observed_qty}주")

    # 30초 대기(설계상 명시된 30초 후 SELL)
    print(f"\n[PAUSE] 30초 후 SELL 진행")
    time.sleep(30)

    # 4) SELL 접수 — 현재가 -0.5% (체결 유도)
    sell_price = client.get_last_price(SYMBOL, EXCHANGE)
    sell_limit = round(sell_price * 0.995, 2)
    print(f"\n[SELL] {SYMBOL} {QTY}주 @ ${sell_limit} (현재가 ${sell_price}의 99.5%)")
    sell_res = client.order(SYMBOL, "sell", QTY, sell_limit, EXCHANGE)
    pp("SELL 응답", sell_res)

    if sell_res.get("rt_cd") != "0":
        print(f"❌ SELL 접수 실패: {sell_res.get('msg1')}")
        return 1

    sell_odno = (sell_res.get("output") or {}).get("ODNO")
    print(f"✅ SELL 접수 OK. 주문번호={sell_odno}")

    # 5) SELL 체결 대기
    print(f"\n[WAIT] 최대 {FILL_WAIT_SECONDS}초 동안 잔고 폴링")
    target_after_sell = initial_qty
    sold, final_qty = wait_for_qty(client, target_after_sell, FILL_WAIT_SECONDS)

    if not sold:
        print(f"\n⚠️ SELL 미체결: 목표 {target_after_sell}주, 관측 {final_qty}주.")
        print(f"   → SELL 주문 취소 시도.")
        if sell_odno:
            cancel_res = client.cancel_order(SYMBOL, sell_odno, QTY, EXCHANGE)
            pp("CANCEL 응답", cancel_res)
        return 3

    print(f"\n✅ SELL 체결 확인 — {SYMBOL} {final_qty}주")
    print("\n🎉 BUY→SELL 왕복 검증 완료. 주문 API + 체결 추적 + 잔고 sync 정상 동작.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
