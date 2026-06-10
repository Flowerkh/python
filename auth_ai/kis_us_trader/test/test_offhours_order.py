"""KIS 장외(미국 정규장 마감 후) 주문 거동 실증 테스트 — 07:30 타이밍 결함 확정용.

⚠️ 실제 paper 주문을 전송한다. 미국 정규장이 '완전히' 마감된 시각(= 한국 낮, 프리마켓
   시작 17:00 KST DST 이전)에 실행할 것. 봇과 동일한 marketable 지정가(+0.5%) 1주 매수를
   보내 raw rt_cd/msg 와 체결 여부를 관측하고, 체결되면 즉시 매도 청산, 미체결 잔량은 취소한다.

판정:
  rt_cd != "0"              → 장외 주문 거부. 봇은 이 상황에서 cycle_error(매매 불가).
  rt_cd == "0" + 포지션 증가  → paper 가 장외 체결을 시뮬레이션(실전과 다름). 즉시 청산.
  rt_cd == "0" + 포지션 그대로 → 접수만 됨(미체결). rt_cd==0 은 '체결'이 아님
                               → daily_trader.py:279 phantom-fill 버그 실측 확정. 주문 취소.

참고: client.order()/cancel_order() 는 텔레그램 알림(✅/⚠️)을 자동 발송한다(정상).
      systemd 서비스(대기 중)와 충돌 없음 — 이 스크립트는 텔레그램 poller 를 띄우지 않음.

실행(서버, 미국 완전 마감 시):
  .venv/bin/python test/test_offhours_order.py RUN
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kis.client import KISClient, parse_balance_positions

SYM, EXCH = "AAPL", "NASD"


def held_qty(client) -> int:
    pos = parse_balance_positions(client.get_balance(EXCH))
    return int(pos.get(SYM, {}).get("qty", 0))


def main():
    if len(sys.argv) < 2 or sys.argv[1] != "RUN":
        raise SystemExit("안전장치: 실제 paper 주문을 보냅니다. 실행하려면:  python test/test_offhours_order.py RUN")

    c = KISClient()
    print(f"env={c.settings.env}")
    if c.settings.env != "paper":
        raise SystemExit("paper 환경에서만 실행하세요. KIS_ENV=paper 확인.")

    closes = c.get_daily_prices(SYM, EXCH, days=5)
    if not closes:
        raise SystemExit("일봉 조회 실패 — 기준가를 못 구함.")
    ref = closes[-1]
    buy_limit = round(ref * 1.005, 2)
    print(f"기준가(최근 종가)={ref}  →  marketable 매수 지정가(+0.5%)={buy_limit}")

    before = held_qty(c)
    print(f"주문 전 {SYM} 보유수량 = {before}")

    print(f"\n>>> BUY 1 {SYM} @ {buy_limit} 전송 (봇과 동일 형태)...")
    res = c.order(SYM, "buy", 1, buy_limit, EXCH)
    rt = res.get("rt_cd")
    odno = (res.get("output") or {}).get("ODNO")
    print("    raw:", json.dumps({k: res.get(k) for k in ("rt_cd", "msg_cd", "msg1", "output")}, ensure_ascii=False))

    time.sleep(3)
    after = held_qty(c)
    print(f"주문 후 {SYM} 보유수량 = {after}")

    print("\n========== 판정 ==========")
    if rt != "0":
        print(f"[거부] 장외 정규주문 거부됨. msg_cd={res.get('msg_cd')!r} msg1={res.get('msg1')!r}")
        print("  -> 결론: 실전 07:30 주문은 이렇게 거부됨. 봇은 cycle_error 로 처리(매매 불가).")
        return
    if after > before:
        print("[체결] paper 가 장외에서도 체결을 시뮬레이션함(rt_cd==0 + 포지션 증가).")
        print("  -> 결론: 모의에선 동작하나 실전과 다름. 청산 진행.")
        sres = c.order(SYM, "sell", 1, round(ref * 0.995, 2), EXCH)
        print(f"  청산 SELL rt_cd={sres.get('rt_cd')!r} msg1={sres.get('msg1')!r}")
        if sres.get("rt_cd") != "0":
            print("  ⚠️ 청산 실패 — KIS 앱에서 수동으로 1주 매도하세요.")
        return
    print("[접수·미체결] rt_cd==0 이지만 포지션 변화 없음.")
    print("  -> 결론: rt_cd==0 은 '접수'일 뿐 '체결'이 아님. daily_trader.py:279 phantom-fill 버그 실측 확정")
    print("           (봇이라면 이 응답으로 apply_fill 을 호출해 가짜 포지션을 기록).")
    if odno:
        print(f"  -> 잔존 주문 취소: ODNO={odno}")
        cres = c.cancel_order(SYM, odno, 1, EXCH)
        print(f"  취소 rt_cd={cres.get('rt_cd')!r} msg1={cres.get('msg1')!r}")
        if cres.get("rt_cd") != "0":
            print("  ⚠️ 취소 실패 — KIS 앱에서 잔존 주문 확인/취소하세요.")


if __name__ == "__main__":
    main()
