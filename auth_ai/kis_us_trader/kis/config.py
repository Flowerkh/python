"""환경설정: .env 로드 및 모의/실전 도메인·TR ID 분기.

KIS는 모의투자와 실전투자의 도메인과 TR ID가 다릅니다.
이 모듈에서 한 곳으로 모아 관리하여 실수를 줄입니다.
"""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

# 모의/실전 REST 도메인
DOMAINS = {
    "paper": "https://openapivts.koreainvestment.com:29443",  # 모의투자
    "prod": "https://openapi.koreainvestment.com:9443",        # 실전투자
}

# 해외주식 거래소 코드 (미국)
#   주간거래 기준 코드. NASD=나스닥, NYSE=뉴욕, AMEX=아멕스
EXCHANGE = {
    "NASD": "나스닥",
    "NYSE": "뉴욕",
    "AMEX": "아멕스",
}
# 시세조회용 거래소 코드 (주문용과 다름!)
EXCHANGE_PRICE = {
    "NASD": "NAS",
    "NYSE": "NYS",
    "AMEX": "AMS",
}

# 미국주식 주문 TR ID (모의 vs 실전이 다름)
#   매수: 실전 TTTT1002U / 모의 VTTT1002U
#   매도: 실전 TTTT1006U / 모의 VTTT1001U
TR_BUY = {"paper": "VTTT1002U", "prod": "TTTT1002U"}
TR_SELL = {"paper": "VTTT1001U", "prod": "TTTT1006U"}
# 정정/취소(미국): 실전 TTTT1004U / 모의 VTTT1004U
#   엔드포인트: /uapi/overseas-stock/v1/trading/order-rvsecncl
#   RVSE_CNCL_DVSN_CD: "01"=정정, "02"=취소
TR_CANCEL = {"paper": "VTTT1004U", "prod": "TTTT1004U"}
# 잔고조회: 실전 TTTS3012R / 모의 VTTS3012R
TR_BALANCE = {"paper": "VTTS3012R", "prod": "TTTS3012R"}
# 미국 현재가(시세)는 모의/실전 동일: HHDFS00000300


@dataclass
class Settings:
    env: str            # "paper" | "prod"
    base_url: str
    app_key: str
    app_secret: str
    cano: str           # 계좌 앞 8자리
    acnt_prdt_cd: str   # 계좌 뒤 2자리

    @property
    def is_paper(self) -> bool:
        return self.env == "paper"


def load_settings() -> Settings:
    env = os.getenv("KIS_ENV", "paper").strip().lower()
    if env not in DOMAINS:
        raise ValueError(f"KIS_ENV must be 'paper' or 'prod', got: {env!r}")

    if env == "prod":
        app_key = os.getenv("KIS_PROD_APP_KEY") or os.getenv("KIS_APP_KEY")
        app_secret = os.getenv("KIS_PROD_APP_SECRET") or os.getenv("KIS_APP_SECRET")
        cano = os.getenv("KIS_PROD_CANO") or os.getenv("KIS_CANO")
        acnt = os.getenv("KIS_PROD_ACNT_PRDT_CD") or os.getenv("KIS_ACNT_PRDT_CD")
    else:
        app_key = os.getenv("KIS_APP_KEY")
        app_secret = os.getenv("KIS_APP_SECRET")
        cano = os.getenv("KIS_CANO")
        acnt = os.getenv("KIS_ACNT_PRDT_CD")

    missing = [n for n, v in {
        "APP_KEY": app_key, "APP_SECRET": app_secret,
        "CANO": cano, "ACNT_PRDT_CD": acnt,
    }.items() if not v]
    if missing:
        raise RuntimeError(
            f"{env} 환경 필수값 누락: {', '.join(missing)}. .env 파일을 확인하세요."
        )

    return Settings(
        env=env,
        base_url=DOMAINS[env],
        app_key=app_key,
        app_secret=app_secret,
        cano=cano,
        acnt_prdt_cd=acnt,
    )
