"""KIS 해외주식(미국) REST 호출 래퍼.

제공 기능:
  - get_price(symbol, exchange)        현재가 조회
  - get_balance()                      해외주식 잔고 조회
  - order(symbol, exchange, side, qty, price)  매수/매도 주문

모든 호출은 RateLimiter를 거칩니다.
"""
from __future__ import annotations

import requests

from . import config
from .auth import get_access_token
from .config import Settings, load_settings
from .notify import send_telegram
from .rate_limiter import RateLimiter


class KISClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or load_settings()
        self.token = get_access_token(self.settings)
        # KIS 호출 한도: 모의 1회/초, 실전 ~20회/초. 보수적으로 paper=1, prod=5.
        per_sec = 1 if self.settings.env == "paper" else 5
        self.limiter = RateLimiter(max_calls_per_sec=per_sec)

    # ---- 공통 헤더 ----
    def _headers(self, tr_id: str) -> dict:
        return {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self.token}",
            "appkey": self.settings.app_key,
            "appsecret": self.settings.app_secret,
            "tr_id": tr_id,
            "custtype": "P",  # 개인
        }

    def _parse_or_raise(self, resp: "requests.Response") -> dict:
        """JSON 본문을 우선 반환. KIS는 4xx/5xx에도 rt_cd/msg1을 담아 보내므로
        본문이 JSON으로 파싱되면 호출부에서 rt_cd로 판단하게 한다.
        JSON이 아니거나 빈 본문이면서 상태가 비정상이면 예외."""
        try:
            data = resp.json()
        except ValueError:
            data = None
        if data is not None:
            return data
        resp.raise_for_status()
        return {"rt_cd": "-1", "msg1": f"빈 응답(status={resp.status_code})"}

    def _get(self, path: str, tr_id: str, params: dict) -> dict:
        self.limiter.acquire()
        url = f"{self.settings.base_url}{path}"
        resp = requests.get(url, headers=self._headers(tr_id), params=params, timeout=10)
        return self._parse_or_raise(resp)

    def _post(self, path: str, tr_id: str, body: dict) -> dict:
        self.limiter.acquire()
        url = f"{self.settings.base_url}{path}"
        resp = requests.post(url, headers=self._headers(tr_id), json=body, timeout=10)
        return self._parse_or_raise(resp)

    # ---- 현재가 조회 ----
    def get_price(self, symbol: str, exchange: str = "NASD") -> dict:
        excd = config.EXCHANGE_PRICE.get(exchange, exchange)  # NASD -> NAS 변환
        data = self._get(
            "/uapi/overseas-price/v1/quotations/price",
            tr_id="HHDFS00000300",
            params={"AUTH": "", "EXCD": excd, "SYMB": symbol},
        )
        return data

    def get_last_price(self, symbol: str, exchange: str = "NASD") -> float:
        data = self.get_price(symbol, exchange)
        out = data.get("output", {})
        last = out.get("last") or "0"
        return float(last)

    # ---- 일봉(기간별 시세) 조회 ----
    def get_daily_prices(self, symbol: str, exchange: str = "NASD", days: int = 30) -> list:
        """최근 일봉 종가 리스트 반환(과거→현재 순). 추세/이동평균 계산용."""
        data = self._get(
            "/uapi/overseas-price/v1/quotations/dailyprice",
            tr_id="HHDFS76240000",
            params={
                "AUTH": "",
                "EXCD": config.EXCHANGE_PRICE.get(exchange, exchange),
                "SYMB": symbol,
                "GUBN": "0",
                "BYMD": "",
                "MODP": "1",
            },
        )
        rows = data.get("output2", []) or []
        closes = []
        for r in rows:
            c = r.get("clos")
            if c:
                try:
                    closes.append(float(c))
                except ValueError:
                    pass
        closes = closes[:days]
        closes.reverse()
        return closes

    # ---- 잔고 조회 ----
    def get_balance(self, exchange: str = "NASD", currency: str = "USD") -> dict:
        tr_id = config.TR_BALANCE[self.settings.env]
        data = self._get(
            "/uapi/overseas-stock/v1/trading/inquire-balance",
            tr_id=tr_id,
            params={
                "CANO": self.settings.cano,
                "ACNT_PRDT_CD": self.settings.acnt_prdt_cd,
                "OVRS_EXCG_CD": exchange,
                "TR_CRCY_CD": currency,
                "CTX_AREA_FK200": "",
                "CTX_AREA_NK200": "",
            },
        )
        return data

    # ---- 주문 ----
    def order(
        self,
        symbol: str,
        side: str,            # "buy" | "sell"
        qty: int,
        price: float,
        exchange: str = "NASD",
    ) -> dict:
        """미국 주식 지정가 주문.
        시장가 개념이 제한적이므로 지정가(현재가 근처) 사용을 권장.
        """
        if side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        tr_id = config.TR_BUY[self.settings.env] if side == "buy" else config.TR_SELL[self.settings.env]

        body = {
            "CANO": self.settings.cano,
            "ACNT_PRDT_CD": self.settings.acnt_prdt_cd,
            "OVRS_EXCG_CD": exchange,
            "PDNO": symbol,
            "ORD_QTY": str(int(qty)),
            "OVRS_ORD_UNPR": f"{price:.2f}",
            "ORD_SVR_DVSN_CD": "0",
            "ORD_DVSN": "00",  # 00: 지정가
        }
        res = self._post(
            "/uapi/overseas-stock/v1/trading/order",
            tr_id=tr_id,
            body=body,
        )
        self._notify_order(symbol, side, qty, price, res)
        return res

    def _notify_order(self, symbol: str, side: str, qty: int, price: float, res: dict) -> None:
        env_label = "모의" if self.settings.env == "paper" else "실전"
        side_label = "매수" if side == "buy" else "매도"
        rt = res.get("rt_cd")
        if rt == "0":
            odno = (res.get("output") or {}).get("ODNO", "?")
            msg = (
                f"✅ {side_label} 접수 ({env_label})\n"
                f"종목: {symbol} {qty}주 @ ${price:.2f}\n"
                f"주문번호: {odno}"
            )
        else:
            msg = (
                f"⚠️ {side_label} 실패 ({env_label}) {symbol} {qty}주\n"
                f"rt_cd={rt}\n{res.get('msg1','')}"
            )
        send_telegram(msg)

    # ---- 주문 취소 ----
    def cancel_order(
        self,
        symbol: str,
        order_no: str,
        qty: int,
        exchange: str = "NASD",
    ) -> dict:
        """미국 주식 주문 취소.

        order_no: 원주문번호(ODNO). 주문 응답 output.ODNO에서 받는다.
        qty: 취소 수량(원주문 수량을 그대로 넣으면 전량 취소).
        """
        tr_id = config.TR_CANCEL[self.settings.env]
        body = {
            "CANO": self.settings.cano,
            "ACNT_PRDT_CD": self.settings.acnt_prdt_cd,
            "OVRS_EXCG_CD": exchange,
            "PDNO": symbol,
            "ORGN_ODNO": str(order_no),
            "RVSE_CNCL_DVSN_CD": "02",  # 02: 취소
            "ORD_QTY": str(int(qty)),
            "OVRS_ORD_UNPR": "0",       # 취소 시 0
            "MGCO_APTM_ODNO": "",
            "ORD_SVR_DVSN_CD": "0",
        }
        res = self._post(
            "/uapi/overseas-stock/v1/trading/order-rvsecncl",
            tr_id=tr_id,
            body=body,
        )
        self._notify_cancel(symbol, order_no, qty, res)
        return res

    def _notify_cancel(self, symbol: str, order_no: str, qty: int, res: dict) -> None:
        env_label = "모의" if self.settings.env == "paper" else "실전"
        rt = res.get("rt_cd")
        if rt == "0":
            msg = (
                f"🚫 주문 취소 ({env_label})\n"
                f"종목: {symbol} {qty}주\n"
                f"원주문번호: {order_no}"
            )
        else:
            msg = (
                f"⚠️ 취소 실패 ({env_label}) {symbol}\n"
                f"원주문번호: {order_no}\n"
                f"rt_cd={rt}\n{res.get('msg1','')}"
            )
        send_telegram(msg)


# 연결 점검용: python -m kis.client
if __name__ == "__main__":
    client = KISClient()
    print(f"[OK] 환경={client.settings.env}, 토큰 발급 성공")
    price = client.get_last_price("AAPL", "NASD")
    print(f"AAPL 현재가: {price} USD")
