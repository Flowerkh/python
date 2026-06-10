"""portfolio.apply_fill 회계 + 실현손익 회귀 — 네트워크 0(FakeClient + 격리 state).

review #4 회귀: SELL 체결 시 realized_pnl_usd 미지정이면 평단 대비로 자동 산출 →
daily_loss_realized_usd 가 누적되고 DAILY_LOSS_LIMIT 게이트가 실제로 작동.

실행(프로젝트 루트): python test/test_portfolio.py
"""
import os
import sys
import tempfile
from pathlib import Path

# ⚠️ kis import 보다 먼저 STATE_DIR 를 임시 폴더로 — 실제 .state/state.json 오염 방지.
os.environ["STATE_DIR"] = tempfile.mkdtemp(prefix="kis_test_state_")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from portfolio import Portfolio
from safety_gate import CHECK_DAILY_LIMIT, Pick, can_buy

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


class FakeClient:
    """Portfolio 가 쓰는 get_balance 만 모사(빈 잔고 = sync 성공)."""

    def get_balance(self, exchange="NASD", currency="USD"):
        return {"rt_cd": "0", "output1": []}


def new_pf():
    return Portfolio(FakeClient())


# ============================================================
print("\n=== 1) SELL 실현손익 자동 산출 → daily_loss_realized_usd 누적 (review #4) ===")
pf = new_pf()
check(pf.sync_failed is False, "빈 잔고 sync 성공(sync_failed=False)")
pf.positions["INTC"] = {"qty": 60, "avg_price": 200.0, "eval_usd": 12000.0}
st = pf.apply_fill("INTC", 60, "sell", 190.0)  # (190-200)*60 = -600, 포지션 전량 청산
check(abs(st["daily_loss_realized_usd"] - (-600.0)) < 1e-6,
      f"SELL 손실 -600 누적 (실측 {st['daily_loss_realized_usd']})")
check("INTC" not in pf.positions, "전량 매도 → 포지션 제거")


# ============================================================
print("\n=== 2) 누적 손실 -600 ≤ DAILY_LOSS_LIMIT(-500) → can_buy 차단 (review #4 게이트 부활) ===")
# NVDA: 보유 0, 쿨다운 없음, 노출 0 → symbol/sector/total/cooldown 통과하고 일일 손실에서 막혀야.
r = can_buy(Pick("NVDA", "buy", 1, 100.0, 90, "x"), pf, pf.state)
check(r.ok is False and r.check == CHECK_DAILY_LIMIT, f"손실 한도 도달 → BUY 차단 (실측 {r.check})")
check("일일 손실" in (r.reason or ""), f"차단 사유가 일일 손실 (실측 {r.reason})")


# ============================================================
print("\n=== 3) 이익 SELL → 실현손익 양수(손실 카운터 회복) ===")
pf3 = new_pf()
pf3.positions["AMD"] = {"qty": 10, "avg_price": 100.0, "eval_usd": 1000.0}
before = pf3.state.get("daily_loss_realized_usd", 0.0)
st3 = pf3.apply_fill("AMD", 10, "sell", 120.0)  # (120-100)*10 = +200
check(abs((st3["daily_loss_realized_usd"] - before) - 200.0) < 1e-6,
      f"이익 +200 반영 (Δ 실측 {st3['daily_loss_realized_usd'] - before})")


# ============================================================
print("\n=== 4) BUY 체결 회계: staged 비움 + daily_buy_count/amount + last_buy_at ===")
pf4 = new_pf()
pf4.record_staged_buy("MU", 2, 50.0)  # staged MU {qty2, usd100}
check(pf4.staged_buys.get("MU", {}).get("usd") == 100.0, "staged 누적 100")
cnt_before = pf4.state.get("daily_buy_count", 0)
amt_before = pf4.state.get("daily_buy_amount_usd", 0.0)
st4 = pf4.apply_fill("MU", 2, "buy", 50.0)
check(pf4.staged_buys.get("MU") == {"qty": 0, "usd": 0.0}, "체결 후 staged 비움")
check(pf4.positions.get("MU", {}).get("qty") == 2, "포지션 2주 반영")
check(st4["daily_buy_count"] == cnt_before + 1, "daily_buy_count +1")
check(abs(st4["daily_buy_amount_usd"] - (amt_before + 100.0)) < 1e-6, "daily_buy_amount +100")
check(st4.get("last_buy_at", {}).get("MU") is not None, "last_buy_at[MU] 기록")
check(st4["consecutive_errors"] == 0, "성공 매수 → consecutive_errors 리셋")


# ============================================================
print("\n=== 5) unstage_buy → staged 제거 (review #1 비체결 해제) ===")
pf5 = new_pf()
pf5.record_staged_buy("AMD", 1, 200.0)
check(pf5.staged_buys.get("AMD", {}).get("usd") == 200.0, "staged AMD 200")
pf5.unstage_buy("AMD")
check("AMD" not in pf5.staged_buys, "unstage 후 staged 제거")
pf5.unstage_buy("AMD")  # 멱등(없어도 예외 X)
check("AMD" not in pf5.staged_buys, "unstage 멱등")


print(f"\n총 {_fails}건 실패")
sys.exit(1 if _fails else 0)
