"""8개 안전 검사 게이트 — LLM picks가 실제 주문에 도달하기 전 마지막 방어선.

검사 순서(BUY): whitelist → invalid_pick → paper_tradable → sync_failed → symbol_cap
                → sector_cap → total_cap → cooldown → daily_limit
검사 순서(SELL): whitelist → invalid_pick → holding (sync_failed 무시)

설계 원칙:
- short-circuit: 첫 실패 사유만 반환.
- fail-closed: 모든 내부 예외는 GateResult(ok=False, check=CHECK_INTERNAL_ERROR).
  검사 내부에서 raise하지 않음 — 한 종목 실패가 다음 종목을 막지 않게.
- state는 dict, portfolio는 duck-typed → 단위 테스트가 mock으로 가능.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional
from zoneinfo import ZoneInfo

from kis import universe

ET = ZoneInfo("America/New_York")

# 검사 식별자(audit 로그용)
CHECK_WHITELIST       = "whitelist"
CHECK_INVALID_PICK    = "invalid_pick"
CHECK_PAPER_TRADABLE  = "paper_tradable"
CHECK_SYNC_FAILED     = "sync_failed"
CHECK_SYMBOL_CAP      = "symbol_cap"
CHECK_SECTOR_CAP      = "sector_cap"
CHECK_TOTAL_CAP       = "total_cap"
CHECK_COOLDOWN        = "cooldown"
CHECK_DAILY_LIMIT     = "daily_limit"
CHECK_HOLDING         = "holding"
CHECK_INTERNAL_ERROR  = "internal_error"

DEFAULT_CONSTANTS: dict = {
    "MAX_POSITION_PER_SYMBOL_USD": 2000,
    "MAX_TOTAL_EXPOSURE_USD":      10000,
    "MAX_SECTOR_EXPOSURE_PCT":     40,
    "MAX_NEW_BUYS_PER_DAY":        3,
    "REBUY_COOLDOWN_DAYS":         3,
    "DAILY_TOTAL_BUDGET_USD":      600,
    "DAILY_LOSS_LIMIT_USD":        -500,
    "MAX_CONSECUTIVE_ERRORS":      3,
}


@dataclass(frozen=True)
class Pick:
    """LLM 출력(action/confidence/reason) + 코드 계산(qty/limit_price)을 합친 거래 후보."""
    symbol: str
    side: Literal["buy", "sell"]
    qty: int
    limit_price: float
    confidence: int = 0
    reason: str = ""


@dataclass(frozen=True)
class GateResult:
    ok: bool
    reason: Optional[str] = None
    check: Optional[str] = None


def _merge(consts: dict | None) -> dict:
    out = dict(DEFAULT_CONSTANTS)
    if consts:
        out.update({k: v for k, v in consts.items() if v is not None})
    return out


def _today_et() -> str:
    return datetime.now(ET).date().isoformat()


def _days_since(iso_date: str) -> int | None:
    try:
        d = datetime.strptime(iso_date, "%Y-%m-%d").date()
        today = datetime.strptime(_today_et(), "%Y-%m-%d").date()
        return (today - d).days
    except (ValueError, TypeError):
        return None


def can_buy(pick: Pick, portfolio, state: dict, constants: dict | None = None) -> GateResult:
    """BUY pick에 대한 8단계 검사. 첫 실패 시 즉시 반환."""
    try:
        C = _merge(constants)
        sym = pick.symbol.upper()

        # 1) whitelist
        if not universe.is_whitelisted(sym):
            return GateResult(False, f"화이트리스트 외 종목({sym})", CHECK_WHITELIST)

        # 2) invalid_pick
        if pick.qty <= 0 or pick.limit_price <= 0:
            return GateResult(False, "주문 수량/가격이 0 이하", CHECK_INVALID_PICK)

        # 3) paper_tradable
        if not universe.is_paper_tradable(sym):
            return GateResult(False, f"paper_tradable 캐시 불가({sym})", CHECK_PAPER_TRADABLE)

        # 4) sync_failed
        if getattr(portfolio, "sync_failed", False):
            return GateResult(False, "잔고 동기화 실패(BUY 차단)", CHECK_SYNC_FAILED)

        # 5) symbol_cap
        cur = portfolio.symbol_exposure_usd(sym)
        delta = pick.qty * pick.limit_price
        cap_sym = C["MAX_POSITION_PER_SYMBOL_USD"]
        if cur + delta > cap_sym:
            return GateResult(
                False,
                f"종목별 cap 초과(${cur:.0f}+${delta:.0f}>${cap_sym:.0f})",
                CHECK_SYMBOL_CAP,
            )

        # 6) sector_cap
        sector = universe.get_sector(sym)
        equity = portfolio.account_equity_usd
        if sector and equity > 0:
            sector_lookup = {s.symbol: s.sector for s in universe.list_all()}
            cur_pct = portfolio.sector_exposure_pct(sector, sector_lookup=sector_lookup)
            new_pct = cur_pct + (delta / equity * 100)
            if new_pct > C["MAX_SECTOR_EXPOSURE_PCT"]:
                return GateResult(
                    False,
                    f"섹터 cap 초과({sector} {new_pct:.1f}%>{C['MAX_SECTOR_EXPOSURE_PCT']}%)",
                    CHECK_SECTOR_CAP,
                )

        # 7) total_cap
        new_total = portfolio.total_exposure_usd() + delta
        if new_total > C["MAX_TOTAL_EXPOSURE_USD"]:
            return GateResult(
                False,
                f"전체 cap 초과(${new_total:.0f}>${C['MAX_TOTAL_EXPOSURE_USD']:.0f})",
                CHECK_TOTAL_CAP,
            )

        # 8) cooldown
        last_at = (state.get("last_buy_at") or {}).get(sym)
        if last_at:
            days = _days_since(last_at)
            if days is None:
                return GateResult(False, f"last_buy_at 파싱 실패({last_at})", CHECK_COOLDOWN)
            if days < C["REBUY_COOLDOWN_DAYS"]:
                return GateResult(
                    False,
                    f"쿨다운 중(D+{days} < {C['REBUY_COOLDOWN_DAYS']}, 마지막 매수 {last_at})",
                    CHECK_COOLDOWN,
                )

        # 9) daily_limit (3가지 합쳐서)
        #   ⚠️ daily_buy_count/amount 는 apply_fill(체결 시)에만 증가하는데, 07:30 사이클은 장 마감
        #   후라 픽이 전부 pending 큐잉(미체결)된다 → 한 사이클 안에서 state 값이 안 변해 누적 검사가
        #   무력화된다(precommit review #2/#5/#14). 그래서 exposure cap 처럼 staged_buys 를 합산해
        #   '이번 사이클에 이미 승인된 BUY'까지 같이 센다(체결되면 apply_fill 이 staged 를 비우므로 이중계산 없음).
        staged = getattr(portfolio, "staged_buys", None) or {}
        staged_count = sum(1 for r in staged.values() if r.get("qty", 0) > 0)
        staged_usd = sum(r.get("usd", 0.0) for r in staged.values())
        buy_count = state.get("daily_buy_count", 0) + staged_count
        if buy_count >= C["MAX_NEW_BUYS_PER_DAY"]:
            return GateResult(
                False,
                f"당일 신규 매수 한도({buy_count}/{C['MAX_NEW_BUYS_PER_DAY']}) 도달",
                CHECK_DAILY_LIMIT,
            )
        buy_amt = state.get("daily_buy_amount_usd", 0.0) + staged_usd
        if buy_amt + delta > C["DAILY_TOTAL_BUDGET_USD"]:
            return GateResult(
                False,
                f"DAILY_TOTAL_BUDGET 초과(${buy_amt:.0f}+${delta:.0f}>${C['DAILY_TOTAL_BUDGET_USD']:.0f})",
                CHECK_DAILY_LIMIT,
            )
        loss = state.get("daily_loss_realized_usd", 0.0)
        if loss <= C["DAILY_LOSS_LIMIT_USD"]:
            return GateResult(
                False,
                f"일일 손실 한도(${C['DAILY_LOSS_LIMIT_USD']}) 도달(현재 ${loss:.0f})",
                CHECK_DAILY_LIMIT,
            )

        return GateResult(True)
    except Exception as e:
        return GateResult(False, f"내부 오류: {type(e).__name__}: {e}", CHECK_INTERNAL_ERROR)


def can_sell(pick: Pick, portfolio, state: dict, constants: dict | None = None) -> GateResult:
    """SELL pick: whitelist + invalid_pick + 보유분 확인. sync_failed 무시."""
    try:
        sym = pick.symbol.upper()
        if not universe.is_whitelisted(sym):
            return GateResult(False, f"화이트리스트 외 종목({sym})", CHECK_WHITELIST)
        if pick.qty <= 0 or pick.limit_price <= 0:
            return GateResult(False, "주문 수량/가격이 0 이하", CHECK_INVALID_PICK)
        held = portfolio.positions.get(sym, {}).get("qty", 0)
        if held < pick.qty:
            return GateResult(False, f"보유 수량 부족(보유 {held} < 요청 {pick.qty})", CHECK_HOLDING)
        return GateResult(True)
    except Exception as e:
        return GateResult(False, f"내부 오류: {type(e).__name__}: {e}", CHECK_INTERNAL_ERROR)


def evaluate(pick: Pick, portfolio, state: dict, constants: dict | None = None) -> GateResult:
    """side로 라우팅."""
    if pick.side == "buy":
        return can_buy(pick, portfolio, state, constants)
    if pick.side == "sell":
        return can_sell(pick, portfolio, state, constants)
    raise ValueError(f"pick.side must be 'buy' or 'sell', got {pick.side!r}")
