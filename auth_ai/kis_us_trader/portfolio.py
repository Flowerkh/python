"""포지션 + 사이클 내 누적 + 상태 영속을 한곳에 묶는 가변 객체.

설계 안전장치 #4(잔고 sync fail-closed) 적용 지점.
설계 안전장치 #3(staged_buys 사이클 내 누적 합산) 적용 지점.

state.json(last_buy_at/daily_*) 갱신은 apply_fill 한 곳에서만 일어난다 —
이중 갱신 방지.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from kis.client import KISClient, parse_balance_positions
from kis.state import load_state, update_state

ET = ZoneInfo("America/New_York")


class Portfolio:
    """KIS 잔고를 source-of-truth로 잡고, 사이클 내 staged_buys를 누적해
    cap 검사 기준으로 합산한다.

    잔고 동기화 실패(빈/이상 응답, HTTP 에러)는 sync_failed=True로 흡수해
    BUY를 전면 차단(safety_gate가 이걸 보고 컷). SELL은 sync_failed여도 허용.
    """

    def __init__(self, client: KISClient, *, exchange: str = "NASD", currency: str = "USD") -> None:
        self.client = client
        self.exchange = exchange
        self.currency = currency
        self.positions: dict[str, dict] = {}
        self.staged_buys: dict[str, dict] = {}
        self.sync_failed: bool = False
        self.state: dict = load_state()
        self.sync()

    def sync(self) -> bool:
        """잔고 재조회. rt_cd != '0' 또는 예외 발생 시 fail-closed."""
        try:
            raw = self.client.get_balance(self.exchange, self.currency)
        except Exception:
            self.positions = {}
            self.sync_failed = True
            return False
        if (
            not isinstance(raw, dict)
            or raw.get("rt_cd") != "0"
            or not isinstance(raw.get("output1"), list)
        ):
            self.positions = {}
            self.sync_failed = True
            return False
        self.positions = parse_balance_positions(raw)
        self.sync_failed = False
        return True

    @property
    def account_equity_usd(self) -> float:
        return self.total_exposure_usd()

    def symbol_exposure_usd(self, symbol: str) -> float:
        sym = symbol.upper()
        pos = self.positions.get(sym, {}).get("eval_usd", 0.0)
        staged = self.staged_buys.get(sym, {}).get("usd", 0.0)
        return float(pos) + float(staged)

    def total_exposure_usd(self) -> float:
        pos_sum = sum(p.get("eval_usd", 0.0) for p in self.positions.values())
        staged_sum = sum(r.get("usd", 0.0) for r in self.staged_buys.values())
        return float(pos_sum + staged_sum)

    def sector_exposure_pct(self, sector: str, *, sector_lookup: dict[str, str]) -> float:
        """섹터별 노출 비율(0~100). sector_lookup은 {symbol: sector} 매핑."""
        total = self.total_exposure_usd()
        if total <= 0:
            return 0.0
        sec_total = 0.0
        for sym, p in self.positions.items():
            if sector_lookup.get(sym) == sector:
                sec_total += p.get("eval_usd", 0.0)
        for sym, r in self.staged_buys.items():
            if sector_lookup.get(sym) == sector:
                sec_total += r.get("usd", 0.0)
        return round(sec_total / total * 100, 4)

    def can_buy(self, symbol: str, qty: int, price: float, *,
                max_per_symbol_usd: float = 2000.0) -> tuple[bool, str | None]:
        """종목별 cap만 본다. 섹터/전체/쿨다운/일일은 safety_gate 책임."""
        if self.sync_failed:
            return False, "sync_failed"
        if qty <= 0 or price <= 0:
            return False, "invalid_qty"
        new_total = self.symbol_exposure_usd(symbol) + qty * price
        if new_total > max_per_symbol_usd:
            return False, "per_symbol_cap_exceeded"
        return True, None

    def record_staged_buy(self, symbol: str, qty: int, price_usd: float) -> None:
        """사이클 내 누적. qty 또는 price 0 이하면 no-op."""
        if qty <= 0 or price_usd <= 0:
            return
        sym = symbol.upper()
        row = self.staged_buys.setdefault(sym, {"qty": 0, "usd": 0.0})
        row["qty"] += int(qty)
        row["usd"] += float(qty * price_usd)

    def unstage_buy(self, symbol: str) -> None:
        """staged_buys 에서 해당 종목 누적을 제거(0 리셋).

        체결로 끝나지 않은 BUY(거절/타임아웃/주문거부/접수-미체결)는 staged 를 남기면 안 된다 —
        같은 사이클 뒤 픽들의 cap/일일예산 검사가 phantom 노출로 오염되기 때문(precommit review #1).
        apply_fill 은 체결 시에만 staged 를 비우므로, 비체결 경로는 이 메서드로 명시 해제한다.
        """
        self.staged_buys.pop(symbol.upper(), None)

    def apply_fill(self, symbol: str, qty: int, side: str, price: float,
                   *, realized_pnl_usd: float | None = None) -> dict:
        """체결 확정 반영. positions/staged_buys/state를 원자적으로 갱신.

        side='buy': positions 평단 가중 평균 + staged 차감 + state.last_buy_at/daily_*
        side='sell': positions qty 차감(0이면 제거) + (realized_pnl_usd 주면) daily_loss 누적
        """
        if side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        sym = symbol.upper()
        cur = self.positions.get(sym, {"qty": 0, "avg_price": 0.0, "eval_usd": 0.0})

        if side == "buy":
            old_qty = cur["qty"]
            new_qty = old_qty + qty
            new_avg = (
                price if old_qty <= 0
                else (old_qty * cur["avg_price"] + qty * price) / new_qty
            )
            self.positions[sym] = {
                "qty": new_qty,
                "avg_price": round(new_avg, 4),
                "eval_usd": round(new_qty * price, 2),
            }
            if sym in self.staged_buys:
                self.staged_buys[sym] = {"qty": 0, "usd": 0.0}
        else:  # sell
            # 실현손익 미지정 시 보유 평단 대비로 산출(DAILY_LOSS_LIMIT 게이트가 살아있도록 —
            # 호출부가 realized_pnl_usd 를 안 넘기면 daily_loss_realized_usd 가 영영 0 → 손실 한도
            # 차단이 죽는다, precommit review #4). 평단 0(미동기화)이면 산출 불가 → None 유지.
            if realized_pnl_usd is None and cur.get("avg_price", 0) > 0:
                realized_pnl_usd = (price - cur["avg_price"]) * qty
            new_qty = max(0, cur["qty"] - qty)
            if new_qty == 0:
                self.positions.pop(sym, None)
            else:
                ratio = new_qty / cur["qty"]
                self.positions[sym] = {
                    "qty": new_qty,
                    "avg_price": cur["avg_price"],
                    "eval_usd": round(cur["eval_usd"] * ratio, 2),
                }

        today_et = datetime.now(ET).date().isoformat()

        def _mut(s: dict) -> None:
            if side == "buy":
                s.setdefault("last_buy_at", {})[sym] = today_et
                s["daily_buy_count"] = s.get("daily_buy_count", 0) + 1
                s["daily_buy_amount_usd"] = s.get("daily_buy_amount_usd", 0.0) + qty * price
                s["consecutive_errors"] = 0
            else:
                if realized_pnl_usd is not None:
                    s["daily_loss_realized_usd"] = (
                        s.get("daily_loss_realized_usd", 0.0) + float(realized_pnl_usd)
                    )

        self.state = update_state(_mut)
        return self.state

    def allocate_budget(self, picks: list[dict], total_usd: float,
                        mode: str = "confidence_weighted") -> dict[str, dict]:
        """picks에 USD 예산을 배분해 {symbol: {qty, usd}} 반환.

        mode='confidence_weighted': confidence 비율 가중. qty=int(usd//price), 0은 제외.
        mode='equal': 균등 배분.
        """
        if mode not in ("confidence_weighted", "equal"):
            raise ValueError(f"mode must be 'confidence_weighted' or 'equal', got {mode!r}")
        if not picks or total_usd <= 0:
            return {}
        out: dict[str, dict] = {}
        if mode == "confidence_weighted":
            total_conf = sum(max(0, p.get("confidence", 0)) for p in picks)
            if total_conf <= 0:
                return {}
            for p in picks:
                price = float(p.get("price") or 0)
                if price <= 0:
                    continue
                w = max(0, p.get("confidence", 0)) / total_conf
                usd = total_usd * w
                qty = int(usd // price)
                if qty > 0:
                    out[p["symbol"]] = {"qty": qty, "usd": round(qty * price, 2)}
        else:  # equal
            per = total_usd / len(picks)
            for p in picks:
                price = float(p.get("price") or 0)
                if price <= 0:
                    continue
                qty = int(per // price)
                if qty > 0:
                    out[p["symbol"]] = {"qty": qty, "usd": round(qty * price, 2)}
        return out
