"""safety_gate 단위 검증 — 22 케이스.

네트워크 없이 mock Portfolio + 합성 state로 검증. KIS/Telegram/OpenAI 호출 0.

실행(프로젝트 루트): python test/test_safety_gate.py
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kis import universe
from safety_gate import (
    CHECK_COOLDOWN,
    CHECK_DAILY_LIMIT,
    CHECK_HOLDING,
    CHECK_INVALID_PICK,
    CHECK_PAPER_TRADABLE,
    CHECK_SYMBOL_CAP,
    CHECK_SYNC_FAILED,
    CHECK_TOTAL_CAP,
    CHECK_WHITELIST,
    Pick,
    can_buy,
    can_sell,
    evaluate,
)
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


# ===== 픽스처 =====
class FakePortfolio:
    """safety_gate가 portfolio에서 호출하는 메서드/속성만 모사."""

    def __init__(self, positions=None, staged=None, sync_failed=False):
        self.positions = positions or {}
        self.staged_buys = staged or {}
        self.sync_failed = sync_failed

    def symbol_exposure_usd(self, sym):
        return (
            self.positions.get(sym, {}).get("eval_usd", 0.0)
            + self.staged_buys.get(sym, {}).get("usd", 0.0)
        )

    def total_exposure_usd(self):
        return (
            sum(p.get("eval_usd", 0.0) for p in self.positions.values())
            + sum(r.get("usd", 0.0) for r in self.staged_buys.values())
        )

    @property
    def account_equity_usd(self):
        return self.total_exposure_usd()

    def sector_exposure_pct(self, sector, *, sector_lookup):
        total = self.total_exposure_usd()
        if total <= 0:
            return 0.0
        s = 0.0
        for sym, p in self.positions.items():
            if sector_lookup.get(sym) == sector:
                s += p.get("eval_usd", 0.0)
        for sym, r in self.staged_buys.items():
            if sector_lookup.get(sym) == sector:
                s += r.get("usd", 0.0)
        return s / total * 100


def fresh_state(**over):
    s = {
        "paused_until": None,
        "consecutive_errors": 0,
        "last_buy_at": {},
        "daily_buy_count": 0,
        "daily_buy_amount_usd": 0.0,
        "daily_loss_realized_usd": 0.0,
        "daily_reset_date_et": None,
        "open_orders": [],
    }
    s.update(over)
    return s


def aapl_pick(qty=1, limit=180.0, side="buy", conf=85):
    return Pick("AAPL", side, qty, limit, conf, "test")


def _et_today_iso():
    return datetime.now(ET).date().isoformat()


def _et_days_ago_iso(n):
    return (datetime.now(ET).date() - timedelta(days=n)).isoformat()


# ===== 22 케이스 =====
def test_whitelist_fail():
    r = can_buy(Pick("NVDA", "buy", 1, 100.0, 90, "x"), FakePortfolio(), fresh_state())
    assert r.ok is False and r.check == CHECK_WHITELIST, r


def test_invalid_pick_qty_zero():
    r = can_buy(aapl_pick(qty=0), FakePortfolio(), fresh_state())
    assert r.ok is False and r.check == CHECK_INVALID_PICK, r


def test_invalid_pick_price_zero():
    r = can_buy(aapl_pick(limit=0), FakePortfolio(), fresh_state())
    assert r.ok is False and r.check == CHECK_INVALID_PICK, r


def test_paper_tradable_fail():
    saved = dict(universe._CACHE)
    try:
        universe._CACHE["AAPL"] = {
            "paper_tradable": False,
            "checked_at": datetime.now().isoformat(timespec="seconds"),
            "last_error": None,
        }
        r = can_buy(aapl_pick(), FakePortfolio(), fresh_state())
        assert r.ok is False and r.check == CHECK_PAPER_TRADABLE, r
    finally:
        universe._CACHE.clear()
        universe._CACHE.update(saved)


def test_sync_failed_buy_blocked():
    r = can_buy(aapl_pick(), FakePortfolio(sync_failed=True), fresh_state())
    assert r.ok is False and r.check == CHECK_SYNC_FAILED, r


def test_sync_failed_sell_allowed():
    # SELL은 sync_failed 무시(설계 #4: 빈 응답 시 SELL/HOLD만 허용)
    pf = FakePortfolio(
        positions={"AAPL": {"qty": 1, "avg_price": 180.0, "eval_usd": 180.0}},
        sync_failed=True,
    )
    r = can_sell(aapl_pick(side="sell"), pf, fresh_state())
    assert r.ok is True, r


def test_symbol_cap_fail():
    # 1850 + 200 = 2050 > 2000
    pf = FakePortfolio(positions={"AAPL": {"qty": 10, "avg_price": 185, "eval_usd": 1850.0}})
    r = can_buy(aapl_pick(qty=2, limit=100.0), pf, fresh_state())
    assert r.ok is False and r.check == CHECK_SYMBOL_CAP, r


def test_symbol_cap_pass_at_edge():
    # 1850 + 100 = 1950 ≤ 2000 (symbol_cap edge)
    # AAPL이 megacap_tech 단독이면 100% 집중 → sector_cap에 먼저 걸리므로
    # 비-megacap 종목(sector_lookup 매치 없음)을 추가해 섹터 비중을 분산.
    pf = FakePortfolio(positions={
        "AAPL":  {"qty": 10, "avg_price": 185, "eval_usd": 1850.0},
        "OTHER": {"qty": 1,  "avg_price": 5000, "eval_usd": 5000.0},  # 비-megacap
    })
    r = can_buy(aapl_pick(qty=1, limit=100.0), pf, fresh_state())
    assert r.ok is True, r


def test_total_cap_fail():
    # 9900 + 400 = 10300 > 10000
    pf = FakePortfolio(positions={"AAPL": {"qty": 50, "avg_price": 198, "eval_usd": 9900.0}})
    # symbol_cap(2000)보다 큰 케이스이므로 우선 symbol_cap에 걸려야 하나, 보유 1주 추가가 종목 cap만
    # 정확히 통과하면서 total만 깨지도록 setup 조정:
    pf = FakePortfolio(
        positions={
            "AAPL": {"qty": 10, "avg_price": 190, "eval_usd": 1900.0},
            # 다른 종목으로 8000 더 채워서 total=9900 (Phase 1 화이트리스트엔 AAPL뿐이지만
            # safety_gate는 portfolio.positions를 그대로 합산하므로 동작 가능)
            "OTHER": {"qty": 1, "avg_price": 8000, "eval_usd": 8000.0},
        }
    )
    # AAPL에 +50: 1900+50=1950 ≤ 2000 (symbol pass)
    # total 9900+50=9950 ≤ 10000 (pass) ← 통과 케이스라 cap 안 닿음
    # 실제 fail 유도: AAPL +200 → 2100>2000으로 symbol_cap 먼저 걸림.
    # 따라서 정확히 total_cap만 트리거하려면 AAPL을 다른 종목 +200으로:
    pf = FakePortfolio(
        positions={
            "AAPL": {"qty": 1, "avg_price": 100, "eval_usd": 100.0},
            "OTHER": {"qty": 1, "avg_price": 9900, "eval_usd": 9900.0},
        }
    )
    # AAPL +200: symbol 300 ≤ 2000 OK / total 10000+200=10200 > 10000
    r = can_buy(aapl_pick(qty=2, limit=100.0), pf, fresh_state())
    assert r.ok is False and r.check == CHECK_TOTAL_CAP, r


def test_cooldown_fail():
    state = fresh_state(last_buy_at={"AAPL": _et_days_ago_iso(1)})  # D+1
    r = can_buy(aapl_pick(), FakePortfolio(), state)
    assert r.ok is False and r.check == CHECK_COOLDOWN, r


def test_cooldown_pass_after_3_days():
    state = fresh_state(last_buy_at={"AAPL": _et_days_ago_iso(4)})  # D+4 ≥ 3
    r = can_buy(aapl_pick(), FakePortfolio(), state)
    assert r.ok is True, r


def test_cooldown_parse_fail():
    state = fresh_state(last_buy_at={"AAPL": "2026-13-99"})  # invalid date
    r = can_buy(aapl_pick(), FakePortfolio(), state)
    assert r.ok is False and r.check == CHECK_COOLDOWN, r


def test_daily_count_fail():
    state = fresh_state(daily_buy_count=3)
    r = can_buy(aapl_pick(), FakePortfolio(), state)
    assert r.ok is False and r.check == CHECK_DAILY_LIMIT, r
    assert "3/3" in r.reason, r.reason


def test_daily_budget_fail():
    state = fresh_state(daily_buy_amount_usd=500.0)
    # pick total: 1주 × $150 = $150. 500+150=650 > 600
    r = can_buy(aapl_pick(qty=1, limit=150.0), FakePortfolio(), state)
    assert r.ok is False and r.check == CHECK_DAILY_LIMIT, r
    assert "DAILY_TOTAL_BUDGET" in r.reason, r.reason


def test_daily_loss_limit_fail():
    state = fresh_state(daily_loss_realized_usd=-500.0)
    r = can_buy(aapl_pick(), FakePortfolio(), state)
    assert r.ok is False and r.check == CHECK_DAILY_LIMIT, r
    assert "일일 손실" in r.reason, r.reason


def test_sell_holding_short():
    pf = FakePortfolio(positions={"AAPL": {"qty": 1, "avg_price": 180, "eval_usd": 180.0}})
    r = can_sell(aapl_pick(side="sell", qty=2), pf, fresh_state())
    assert r.ok is False and r.check == CHECK_HOLDING, r


def test_sell_holding_exact():
    pf = FakePortfolio(positions={"AAPL": {"qty": 1, "avg_price": 180, "eval_usd": 180.0}})
    r = can_sell(aapl_pick(side="sell", qty=1), pf, fresh_state())
    assert r.ok is True, r


def test_sell_whitelist_fail():
    r = can_sell(Pick("NVDA", "sell", 1, 100.0, 90, "x"), FakePortfolio(), fresh_state())
    assert r.ok is False and r.check == CHECK_WHITELIST, r


def test_evaluate_routes():
    try:
        evaluate(Pick("AAPL", "hold", 1, 180.0, 80, "x"), FakePortfolio(), fresh_state())
    except ValueError as e:
        assert "side" in str(e).lower(), e
        return
    raise AssertionError("ValueError가 발생해야 함")


def test_partial_constants_merge():
    # 사용자 정의로 종목별 cap만 500으로 강제. 나머지는 DEFAULT 사용.
    consts = {"MAX_POSITION_PER_SYMBOL_USD": 500}
    # 1주 × $400 = $400 ≤ $500 통과해야 함
    r = can_buy(aapl_pick(qty=1, limit=400.0), FakePortfolio(), fresh_state(), consts)
    assert r.ok is True, r


def test_all_checks_pass():
    r = can_buy(aapl_pick(qty=1, limit=180.0), FakePortfolio(), fresh_state())
    assert r.ok is True and r.reason is None and r.check is None, r


def test_same_cycle_double_pick():
    """같은 사이클 내 같은 종목 2번 BUY 시도 → staged_buys 누적으로 cap 차단."""
    pf = FakePortfolio(
        staged={"AAPL": {"qty": 10, "usd": 1900.0}},  # 이미 1번 BUY 누적
    )
    # 1900 + 1*200 = 2100 > 2000
    r = can_buy(aapl_pick(qty=1, limit=200.0), pf, fresh_state())
    assert r.ok is False and r.check == CHECK_SYMBOL_CAP, r


if __name__ == "__main__":
    # 캐시 초기화 → AAPL은 시드값(True) 사용
    universe._CACHE.clear()

    test_whitelist_fail()
    test_invalid_pick_qty_zero()
    test_invalid_pick_price_zero()
    test_paper_tradable_fail()
    test_sync_failed_buy_blocked()
    test_sync_failed_sell_allowed()
    test_symbol_cap_fail()
    test_symbol_cap_pass_at_edge()
    test_total_cap_fail()
    test_cooldown_fail()
    test_cooldown_pass_after_3_days()
    test_cooldown_parse_fail()
    test_daily_count_fail()
    test_daily_budget_fail()
    test_daily_loss_limit_fail()
    test_sell_holding_short()
    test_sell_holding_exact()
    test_sell_whitelist_fail()
    test_evaluate_routes()
    test_partial_constants_merge()
    test_all_checks_pass()
    test_same_cycle_double_pick()

    print("[OK] safety_gate 22 cases all passed")
