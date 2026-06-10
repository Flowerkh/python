"""Rank 2 (승인-제출 분리) smoke test.

검증:
  Part 1 (네트워크 없음, 항상 안전): pending_orders state 라운드트립 — 주입→로드→검증→정리.
  Part 2 (미국 정규장 시간 + "RUN" 인자): submit_open_orders 통합 — 테스트 pending 1건을 주입하고
          실제 제출→체결확인→포지션 청산→state 원복. 봇과 동일 경로(_submit_one/_place_and_confirm).

⚠️ Part 2 는 실제 paper 주문을 보낸다. **미국 정규장(한국시간 22:30~05:00 DST)** 에 실행할 것.
   안전장치: 시작 시 state.json 전체 스냅샷 → 끝나면 원복(daily 카운터/pending 복구) + 테스트로
   늘어난 보유분만 매도 청산. 충돌 방지를 위해 **systemd 서비스를 잠시 멈추고** 실행 권장:
       sudo systemctl stop kis-trader
       .venv/bin/python test/test_rank2_pending.py RUN
       sudo systemctl start kis-trader

실행:
  .venv/bin/python test/test_rank2_pending.py          # Part 1 만 (안전)
  .venv/bin/python test/test_rank2_pending.py RUN       # Part 1 + Part 2 (실주문, 정규장 시간)
"""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import daily_trader as dt
from kis.client import KISClient
from kis.state import STATE_FILE, load_state, update_state

MARKER = "__rank2_smoke__"
SYM, EXCH = "AAPL", "NASD"


def part1_state_roundtrip() -> None:
    """pending_orders 주입→로드→정리 (네트워크 없음)."""
    print("\n=== Part 1: pending_orders state 라운드트립 ===")
    test_po = {"symbol": SYM, "side": "buy", "qty": 1, "limit": 1.23, "exchange": EXCH,
               "confidence": 99, "reason": MARKER, "approved_at": "2000-01-01T00:00:00-05:00"}
    before = len(load_state().get("pending_orders") or [])
    update_state(lambda s: s.setdefault("pending_orders", []).append(test_po))
    loaded = load_state().get("pending_orders") or []
    assert any(p.get("reason") == MARKER for p in loaded), "주입 실패"
    print(f"  OK 주입: pending {before} -> {len(loaded)}")
    # 마커만 제거(실제 pending 보존)
    update_state(lambda s: s.update({
        "pending_orders": [p for p in (s.get("pending_orders") or []) if p.get("reason") != MARKER]}))
    after = len(load_state().get("pending_orders") or [])
    assert after == before, f"정리 실패: {before} != {after}"
    print(f"  OK 정리: pending -> {after}")


async def part2_submit_integration() -> None:
    """미국 정규장 시간에 submit_open_orders 통합 실행 + 안전 원복."""
    print("\n=== Part 2: submit_open_orders 통합 (실주문) ===")
    if not dt.us_regular_session_open():
        et = dt.datetime.now(dt.ET)
        print(f"  SKIP: 미국 정규장 외({et:%H:%M} ET). 한국시간 22:30~05:00(DST)에 실행하세요.")
        return

    client = KISClient()
    closes = client.get_daily_prices(SYM, EXCH, days=5)
    if not closes:
        print("  SKIP: 일봉 조회 실패")
        return
    ref = closes[-1]
    limit = round(ref * 1.005, 2)
    pre_held = dt._broker_held_qty(client, EXCH, SYM) or 0

    snap = STATE_FILE.read_text(encoding="utf-8")  # state 전체 스냅샷
    test_po = {"symbol": SYM, "side": "buy", "qty": 1, "limit": limit, "exchange": EXCH,
               "confidence": 99, "reason": MARKER,
               "approved_at": dt.datetime.now(dt.ET).isoformat(timespec="seconds")}
    print(f"  기준가 {ref} → BUY 1 @ {limit}. 제출 전 보유 {pre_held}.")

    from telegram import Bot
    bot = Bot(dt.TOKEN)
    try:
        update_state(lambda s: s.update({"pending_orders": [test_po]}))
        async with bot:
            await dt.submit_open_orders(bot)   # 봇과 동일 제출 경로
        time.sleep(2)
        post_held = dt._broker_held_qty(client, EXCH, SYM) or 0
        added = post_held - pre_held
        print(f"  제출 후 보유 {post_held} (증가 {added})")
        if added > 0:
            print("  [판정] 제출→체결 경로 정상 동작 (포지션 증가 확인).")
        else:
            print("  [판정] 접수됐으나 체결 미확인(🟡) 또는 거부 — 위 텔레그램/로그 확인.")
    finally:
        # 1) 테스트로 늘어난 보유분만 청산
        try:
            cur = dt._broker_held_qty(client, EXCH, SYM) or 0
            extra = cur - pre_held
            if extra > 0:
                print(f"  청산: SELL {extra} @ {round(ref*0.995,2)}")
                sres = client.order(SYM, "sell", extra, round(ref * 0.995, 2), EXCH)
                print(f"    청산 rt_cd={sres.get('rt_cd')!r} msg={sres.get('msg1','')!r}")
                if sres.get("rt_cd") != "0":
                    print("    ⚠️ 청산 실패 — KIS 앱에서 수동 매도하세요.")
        except Exception as e:
            print(f"    ⚠️ 청산 중 오류: {e} — 보유 수동 확인 요망.")
        # 2) state.json 원복(daily 카운터/last_buy_at/pending 복구)
        STATE_FILE.write_text(snap, encoding="utf-8")
        print("  state.json 원복 완료.")


def main():
    part1_state_roundtrip()
    if len(sys.argv) > 1 and sys.argv[1] == "RUN":
        asyncio.run(part2_submit_integration())
    else:
        print("\n(Part 2 생략 — 실주문 통합 테스트는 정규장 시간에 'RUN' 인자로: "
              "python test/test_rank2_pending.py RUN)")
    print("\n완료.")


if __name__ == "__main__":
    main()
