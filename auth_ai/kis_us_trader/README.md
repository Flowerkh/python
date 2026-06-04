# KIS 미국주식 자동매매 (모의투자)

한국투자증권 KIS Developers 공식 REST API를 직접 호출(requests)하여
미국 주식을 다루는 자동매매 골격입니다. **기본값은 모의투자(VTS) 환경**입니다.

> ⚠️ 면책: 포함된 예시 전략(이동평균 교차)은 코드 흐름을 보여주기 위한
> 교과서적 데모일 뿐, 수익을 보장하거나 매매를 추천하는 것이 아닙니다.
> 실제 매매 판단과 그 결과의 책임은 전적으로 사용자에게 있습니다.

## 구조

```
kis_us_trader/
├─ .env.example        # 환경변수 템플릿 (복사해서 .env 작성)
├─ requirements.txt
├─ kis/
│  ├─ config.py        # .env 로드, 모의/실전 도메인·TR ID 분기
│  ├─ auth.py          # 접근토큰 발급 + 파일 캐시(24h)
│  ├─ client.py        # 시세/잔고/주문 REST 호출 래퍼
│  └─ rate_limiter.py  # 초당 호출 제한 관리
├─ strategy.py         # 매매 신호 로직 (여기에 본인 전략을 넣음)
└─ run_trader.py       # 자동매매 루프 (진입점)
```

## 준비 (사용자가 직접)

1. 한국투자증권 계좌 개설
2. KIS Developers(https://apiportal.koreainvestment.com)에서
   **모의투자용** API 신청 → AppKey / AppSecret / 모의계좌번호 발급
3. `.env.example`를 `.env`로 복사 후 값 채우기

## 설치 & 실행

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 1) 먼저 연결 점검 (토큰+현재가)
python -m kis.client

# 2) 자동매매 루프 (모의투자)
python run_trader.py
```

## 단계별 권장 진행

1. `python -m kis.client` 로 토큰 발급 + AAPL 현재가가 찍히는지 확인
2. 잔고 조회가 되는지 확인
3. 모의계좌에서 1주 매수/매도가 실제로 체결되는지 확인
4. 그 다음에 `run_trader.py` 루프를 켜기
5. 충분히 검증된 후에만 `.env`의 KIS_ENV를 prod로 (자기 책임 하에)
