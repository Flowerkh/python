# CLAUDE.md — 프로젝트 컨텍스트

이 파일은 Claude Code가 세션 시작 시 자동으로 읽는 프로젝트 맥락입니다.

## 프로젝트 개요

한국투자증권(KIS) 공식 REST API + OpenAI(LLM) + 텔레그램 승인을 결합한
**미국주식 자동매매 시스템**. 현재 **모의투자(paper)** 단계.

핵심 설계 철학:
- **추세 계산은 코드가, 매매 해석/판단은 LLM이** 담당한다.
- LLM 제안은 '제안'일 뿐, 실제 주문은 **코드 안전장치 + 사람의 텔레그램 승인**을 반드시 거친다.
- LLM은 실시간 시장을 모르므로, 코드가 일봉/지표를 계산해 사실로 넣어준다.
- **투자 추천이 아님.** 포함된 전략(SMA/추세)은 데모이며 수익 보장이 아니다.

## 환경

- OS: Windows, PowerShell
- Python: **3.11** (`C:\Users\cdffe\AppData\Local\Programs\Python\Python311`)
  - 주의: 과거 시스템 Python 3.7과 충돌 이력 있음. 반드시 3.11 + 가상환경(.venv) 사용.
- 가상환경: 프로젝트 내 `.venv` (작업 전 `.\.venv\Scripts\Activate.ps1`)

## 디렉터리 구조

```
kis_us_trader/
├─ .env                  # 비밀키 (git 제외 필수). .env.example 참고해 작성
├─ .env.example
├─ .gitignore            # 프로젝트 로컬 ignore (.state/, logs/, 토큰 캐시)
├─ requirements.txt      # requests, python-dotenv, python-telegram-bot, openai, portalocker
├─ Claude.md             # 이 파일. 세션 시작 시 자동 로드.
├─ README.md
├─ kis/                  # 운영 패키지
│  ├─ config.py          # .env 로드, paper/prod 도메인·TR ID 분기(매수/매도/취소/잔고), 거래소코드
│  ├─ auth.py            # 접근토큰 발급 + 파일캐시(~/.kis_us_trader/token_<env>.json)
│  ├─ client.py          # 현재가/일봉/잔고/주문/취소 REST 래퍼 + RateLimiter + 자동 텔레그램 알림
│  │                     # + parse_balance_positions(잔고 응답 정규화, fail-closed)
│  ├─ notify.py          # 텔레그램 동기 전송 헬퍼(주문/취소 시 client가 자동 호출)
│  ├─ rate_limiter.py    # 슬라이딩 윈도우 호출 제한 (sync acquire + async acquire_async)
│  ├─ state.py           # .state/state.json 영속화. portalocker + asyncio.Lock + ET 자정 리셋.
│  └─ audit.py           # logs/cycles-YYYYMM.jsonl. SHA-256 hash chain + verify_chain.
├─ llm_advisor.py        # OpenAI 호출 → {action, confidence, reason} JSON
├─ daily_trader.py       # ★현재 메인: 하루 1회 추세 기반 매매 (KST 07:30 발화, 비동기)
├─ docs/                 # 설계·배포 문서
│  ├─ DESIGN.md          # 다종목/반도체 섹터 확장 설계 + Phase 0~4 로드맵 + 검증 시나리오
│  └─ DEPLOY_NAVER_CLOUD.md  # 네이버클라우드 배포 절차 (Python 3.11, sparse-checkout, systemd 등)
├─ test/                 # 검증용 단독 스크립트. 프로젝트 루트에서 실행.
│  ├─ test_order.py       # 주문/취소 API 단독 검증(매수 접수 → 즉시 취소)
│  ├─ test_balance_parse.py  # 잔고 API 응답 캡처 + parse_balance_positions 9케이스 fail-closed
│  ├─ test_roundtrip.py   # AAPL 1주 BUY → 30초 → SELL 왕복 + 잔고 폴링
│  ├─ test_trader.py      # 일봉조회 + 추세지표 계산 단독 검증
│  └─ Telegram.py         # 텔레그램 승인 흐름 단독 검증
├─ .state/               # ★런타임 생성. git 제외. state.json 영속화.
└─ logs/                 # ★런타임 생성. git 제외. daily_trader.{out,err} + cycles-YYYYMM.jsonl.
```

실행은 항상 프로젝트 루트에서: `python test/test_order.py` 형태.
test 스크립트는 `sys.path`에 루트를 주입하므로 어디서나 import가 동작합니다.

## 중요한 KIS API 함정 (반복해서 틀리는 부분)

1. **거래소 코드가 용도별로 다름**:
   - 시세/일봉 조회(EXCD): `NAS`/`NYS`/`AMS`
   - 주문/잔고(OVRS_EXCG_CD): `NASD`/`NYSE`/`AMEX`
   - 코드에서는 항상 `NASD`를 넘기고, 시세계열은 `config.EXCHANGE_PRICE`로 내부 변환.
2. **모의/실전 TR ID 다름**: `config.py`의 TR_BUY/TR_SELL/TR_BALANCE에서 env로 분기.
   - 미국 매수 모의 `VTTT1002U`/실전 `TTTT1002U`, 매도 모의 `VTTT1001U`/실전 `TTTT1006U`.
3. **미국 거래소 운영시간(한국시간)**: 23:30~06:00 (썸머타임 22:30~05:00).
   - 운영시간 외 주문/현재가 API는 에러 가능. **일봉(dailyprice)은 휴장에도 조회됨**(확인됨).
4. **모의투자는 일부 종목만 매매 가능**. 테스트는 AAPL 등 대형주로.
5. **토큰**: 약 24h 유효. 재발급 횟수 제한 있으므로 캐시 재사용(이미 auth.py가 처리).
6. **호출 제한**: 초당 제한 있음(rate_limiter.py로 보수적 관리). 환경별 분기: paper=1회/초, prod=5회/초.
7. **모의 USD 예수금 확인**: KIS 모의계좌가 USD 예수금이 0이면 BUY 거부됨. 가입 시 가상 USD가 자동 충전되어야 정상.

## 현재 진행 상황 (검증 체크리스트)

### 초기 검증 (완료)
- [x] KIS 토큰 발급
- [x] 미국 현재가 조회 (거래소코드 NAS 이슈 해결)
- [x] 일봉 조회 + 추세지표(SMA 5/20/60) 계산 (test_trader.py로 확인)
- [x] LLM 판단 (gpt-4o-mini, JSON 강제 출력)
- [x] 텔레그램 메시지 전송 + 버튼 승인 수신 (run_polling, drop_pending_updates)

### Phase 0 — 다종목 확장 토대 (진행 중)
- [x] kis/state.py 영속화 (.state/state.json + portalocker + ET 자정 리셋)
- [x] kis/audit.py hash chain 로그 (logs/cycles-YYYYMM.jsonl)
- [x] kis/client.py: parse_balance_positions 헬퍼 (잔고 응답 fail-closed)
- [x] kis/rate_limiter.py: acquire_async (비동기 메서드)
- [x] daily_trader 트리거 23:45 → 07:30 KST 변경 + state/audit 통합
- [x] 네이버클라우드 VM 환경 셋업 (Ubuntu 22.04 + Python 3.11.15 + systemd)
- [x] test_balance_parse.py 통과 (KIS 잔고 API + parser 9케이스 fail-closed)
- [x] test_order.py 통과 (매수 접수→즉시 취소, 텔레그램 ✅/🚫 도착 확인)
- [x] test_roundtrip.py 통과 (AAPL 1주 BUY→체결→30초→SELL→잔고 0주 복귀)
- [ ] daily_trader 1주일 무에러 운영 (KST 07:30 × 7일)
- [ ] python -m kis.audit verify — 7줄 hash chain 무결성

### 그 이후 (계획)
- [ ] Phase 1: 단일 종목으로 다종목 코드 골격 완성 (universe.py, portfolio.py, safety_gate.py)
- [ ] Phase 2: 반도체 화이트리스트 10종목 + macro_bias + decide_parallel + 다이제스트 토글 UI
- [ ] Phase 3: weekly_researcher (web_search 매크로 정성 요약 주 1회)
- [ ] Phase 4: 운영 강화 (dead-man switch, hash chain, prod 이중 잠금, cost cap)
- [ ] (먼 미래) 실전 전환 — 충분한 검증 후, 사용자 책임 하에만

상세 설계와 단계별 절차는 [docs/DESIGN.md](docs/DESIGN.md), 배포는 [docs/DEPLOY_NAVER_CLOUD.md](docs/DEPLOY_NAVER_CLOUD.md).

## 운영 파라미터 (daily_trader.py 상단 상수)

- SYMBOL=AAPL, EXCHANGE=NASD
- DAILY_BUDGET_USD=200 (금액기준 매수, 수량=예산//현재가)
- CONFIDENCE_THRESHOLD=80 (이 이상만 승인요청)
- MAX_POSITION_USD=2000 (최대 보유금액 한도)
- RUN_HOUR=7, RUN_MINUTE=30 (매일 점검 시각, 한국시간 — 미국장 마감 후)
- APPROVAL_TIMEOUT=1800 (승인 무응답 30분 → 자동 거절)

## 다음 할 일

1. **모의주문 단독 테스트** 작성/실행: 1주를 현재가에서 먼 지정가로 접수 →
   rt_cd=0 확인 → 즉시 취소. (장중에 실행. 주문 API/거래소코드/TR ID 검증 목적)
2. 잔고조회로 보유수량 실제 동기화 (지금은 메모리 변수로만 추적).
3. daily_trader 장중 전체 흐름 1회 실행 확인.

## 안전/보안 규칙 (반드시 지킬 것)

- `.env`(KIS키, OpenAI키, 텔레그램토큰)는 절대 커밋/푸시 금지. `.gitignore`에 포함.
- 토큰 캐시 폴더 `~/.kis_us_trader/`도 git 제외.
- KIS_ENV는 **paper** 유지. prod 전환은 사용자가 명시적으로 결정하기 전까지 금지.
- 주문/송금/git push 등 되돌리기 어려운 작업은 자동 승인하지 말고 사용자 확인.
- 투자 판단 자체(어떤 종목/전략이 좋은지)는 조언하지 않는다. 구현만 돕는다.