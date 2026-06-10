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
│  ├─ audit.py           # logs/cycles-YYYYMM.jsonl. SHA-256 hash chain + verify_chain.
│  ├─ universe.py        # 매매 가능 종목 화이트리스트(Phase 1: AAPL) + paper_tradable 24h 캐시.
│  └─ signals.py         # signal_strength 임계값/분류 단일 진실 소스. classify_strength + compute_vol_factor
│                        # (P2 vol 정규화, BASELINE_VOL=0.015). daily_trader/tune_thresholds 공유.
├─ llm_advisor.py        # OpenAI 호출 → {action, confidence, reason, flagged} JSON. sanitize_advice(인젝션
│                        # 방어 + reason 외부 ticker 환각 검증→hold 강등) + macro_bias 사실블록 + aget_advice 비동기.
├─ sector.py             # compute_macro_bias(SMH 1콜 + breadth) → risk_on/neutral/risk_off/unknown
│                        # + max_buys_for_bias(N=3/2/0/0). classify_bias 순수함수(단일 진실 소스).
├─ researcher.py         # decide_parallel(종목당 1콜 asyncio.gather + retry 2 + 실패=hold 폴백, advisor 주입).
├─ portfolio.py          # Portfolio 클래스: 잔고 sync(fail-closed) + staged_buys + apply_fill + allocate_budget.
├─ safety_gate.py        # 8개 안전 검사 게이트(Pick, GateResult, can_buy/can_sell/evaluate).
├─ daily_trader.py       # ★현재 메인: 07:30 점검 = 전종목 trend 수집 → sector.macro_bias(N 결정) →
│                        # researcher.decide_parallel → select_picks(conf≥80 BUY 상위 N + SELL) → 픽별
│                        # safety_gate→승인→Rank 2 제출(pending 큐잉 → submission_loop 개장 제출).
│                        # main_loop(07:30)+submission_loop(개장) asyncio.gather 동시 실행.
├─ tools/
│  ├─ tune_thresholds.py # signal_strength 임계값 분포/방향성 검증(읽기 전용 분석 도구)
│  ├─ flipped_day_pnl.py # P1-후속: weak 라벨 개편 flipped-day forward P&L + strong-down EXIT 시뮬
│  └─ vol_calibration.py # P2: BASELINE_VOL 후보 sweep + 종목별 weak 균일화 측정(Phase 2 재캘리브용)
├─ docs/                 # 설계·운영 문서
│  ├─ DESIGN.md          # 다종목/반도체 섹터 확장 설계 + Phase 0~4 로드맵 + §9 변경이력
│  ├─ DEPLOY_NAVER_CLOUD.md  # 네이버클라우드 배포 절차 (Python 3.11, sparse-checkout, systemd 등)
│  ├─ DAILY_CHECK.md     # 매일 아침 점검 체크리스트 + 텔레그램 시나리오 A~G + 트러블슈팅
│  ├─ SIGNAL_STRENGTH_ANALYSIS.md  # signal_strength 2년 분석 + P1 백테스트(throttle이지 알파 아님)
│  └─ ORDER_TIMING_ISSUE.md  # 07:30=정규장 마감 후 결함 + Rank 0/2 수정 기록
├─ test/                 # 검증용 단독 스크립트. 프로젝트 루트에서 실행.
│  ├─ test_order.py       # 주문/취소 API 단독 검증(매수 접수 → 즉시 취소)
│  ├─ test_balance_parse.py  # 잔고 API 응답 캡처 + parse_balance_positions 9케이스 fail-closed
│  ├─ test_roundtrip.py   # AAPL 1주 BUY → 30초 → SELL 왕복 + 잔고 폴링
│  ├─ test_safety_gate.py # 8개 안전 검사 단위 검증 22 케이스(네트워크 무, mock Portfolio)
│  ├─ test_trader.py      # 일봉조회 + 추세지표 계산 단독 검증
│  ├─ test_offhours_order.py  # 장외 주문 거동 실증(07:30 타이밍 결함 확정용)
│  ├─ test_rank2_pending.py   # Rank 2 pending 라운드트립 + 정규장 제출 통합 smoke
│  ├─ test_signals.py     # kis.signals(P2 vol 정규화 + classify_strength 회귀) 23 케이스
│  ├─ test_sector.py      # sector(classify_bias/max_buys_for_bias/compute_macro_bias) 33 케이스, FakeClient
│  ├─ test_llm_advisor.py # sanitize_advice/foreign_tickers_in_reason 17 케이스(OpenAI 무)
│  ├─ test_researcher.py  # decide_parallel 15 케이스(가짜 advisor 주입, asyncio)
│  ├─ test_daily_trader.py# select_picks(macro N 제한 + conf 임계 + 동률 결정성) 10 케이스
│  ├─ test_universe_health.py # 유니버스 종목 get_price 헬스체크 + paper_tradable 캐시(서버/운영시간 실행)
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
   - 운영시간 외 현재가 API는 에러 가능. **일봉(dailyprice)/잔고는 휴장에도 조회됨**(확인됨).
   - ⚠️ **07:30 KST 사이클은 정규장 마감 후**라 정규주문이 거부됨(`rt_cd=1 / 40580000 "장종료"`, 모의도 동일).
     → daily_trader 는 승인된 주문을 `state.pending_orders`에 큐잉하고 **미국 개장 직후 제출**(Rank 2).
     배경/수정: docs/ORDER_TIMING_ISSUE.md.
   - KIS 미국 **예약주문**도 지원(접수 `VTTT3014U`/`order-resv`, 단 모의 조회 불가) — 현재 미사용, 향후 옵션.
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

### Phase 1 — 다종목 골격 (코드 완료, 운영 검증 대기)
- [x] kis/universe.py — SEMI_UNIVERSE_CORE 화이트리스트(AAPL) + paper_tradable 24h 캐시
- [x] portfolio.py — Portfolio(잔고 sync fail-closed + staged_buys + apply_fill + allocate_budget)
- [x] safety_gate.py — 8개 검사 게이트(can_buy/can_sell/evaluate)
- [x] test/test_safety_gate.py 22 케이스 통과(네트워크 무, mock Portfolio)
- [x] daily_trader.py 12단계 흐름 리팩터(_position_qty 전역 삭제, universe 순회, Pick/GateResult)
- [ ] Phase 1 운영 검증 — AAPL 1종목 1주 운영(staged_buys 사이클 종료 0 리셋 + last_buy_at 갱신 흔적 확인)

### Phase 2 — 반도체 다종목 (코드+오프라인테스트 완료, 운영 검증 대기) ⏳ 2026-06-11
- [x] kis/universe.py — 반도체 10종목 추가(NVDA/AMD/AVGO/MU/INTC/QCOM/TXN/AMAT/LRCX/TSM, TSM만 NYSE)
- [x] sector.py — compute_macro_bias(SMH 1콜 + breadth) → risk_on/neutral/risk_off/unknown + max_buys_for_bias(N=3/2/0/0)
- [x] llm_advisor.py — symbol 의무화 + 인젝션 방어([NEWS]/[EXTERNAL]) + macro_bias 사실블록 + reason 환각(외부 ticker) 검증 → hold 강등(sanitize_advice) + aget_advice 비동기
- [x] researcher.py — decide_parallel(asyncio.gather + retry 2 + 실패종목 hold 폴백, advisor 주입)
- [x] daily_trader.py — 전종목 trend 수집 → macro_bias N 결정 → decide_parallel → select_picks(conf≥80 BUY 상위 N + SELL) → 픽별 safety_gate/승인/Rank2
- [x] test/ 신규: test_sector(33)·test_llm_advisor(17)·test_researcher(15)·test_daily_trader(10) + test_universe_health.py(서버 실행용) + test_safety_gate NVDA→FAKE 갱신
- [ ] **운영 검증 선결**: 서버에서 `python test/test_universe_health.py`(운영시간) → 10종목 paper_tradable 실측·캐시. 거래불가 종목 paper_tradable=False 로 내릴 것
- [ ] **잔여 UX**: approval.py 텔레그램 종목별 토글 다이제스트(현재 per-pick 단건 승인으로 기능 대체됨, 실거동 검증 필요)
- [ ] 2주 라이브 운영 — 화이트리스트 외 ticker 누출 0 + staged_buys cap 정확 차단 + macro_bias N 의도대로

### 그 이후 (계획)
- [ ] Phase 3: weekly_researcher (web_search 매크로 정성 요약 주 1회)
- [ ] Phase 4: 운영 강화 (dead-man switch, hash chain, prod 이중 잠금, cost cap)
- [ ] (먼 미래) 실전 전환 — 충분한 검증 후, 사용자 책임 하에만

상세 설계와 단계별 절차는 [docs/DESIGN.md](docs/DESIGN.md), 배포는 [docs/DEPLOY_NAVER_CLOUD.md](docs/DEPLOY_NAVER_CLOUD.md).

## 운영 파라미터 (daily_trader.py 상단 상수)

- 종목은 `kis/universe.py` 화이트리스트(Phase 2: AAPL + 반도체 10종목 = 11). 전역 SYMBOL 없음.
- PER_PICK_BUDGET_USD=200.0 (종목당 매수 예산, 수량=예산//현재가)
- CONFIDENCE_THRESHOLD=80 (이 이상만 BUY/SELL 후보 → moderate≤75라 사실상 strong 만 거래 경로)
- macro_bias N(그날 신규 매수 상한): risk_on=3 / neutral=2 / risk_off=0 / unknown=0 (`sector.MAX_BUYS_BY_BIAS`).
  SELL(청산)은 N 무관 허용. breadth 임계 risk_on≥60% / risk_off≤40% (`sector.py`).
- CONSTANTS: MAX_POSITION_PER_SYMBOL_USD=2000, MAX_TOTAL_EXPOSURE_USD=10000 등 safety_gate 운영상수
- RUN_HOUR=7, RUN_MINUTE=30 (매일 점검 시각 KST — 미국장 마감 후)
- SUBMIT_HOUR_ET=9, SUBMIT_MINUTE_ET=35 (Rank 2 제출 = 개장 직후 ≈ 22:35 KST), PENDING_TTL_HOURS=18
- APPROVAL_TIMEOUT=1800 (승인 무응답 30분 → 자동 거절)
- signal_strength 임계값은 `kis/signals.py`(WEAK_SCORE_CUT=3.5, **BASELINE_VOL=0.015, VOL_WINDOW=20 — P2 vol 정규화**). 근거: docs/SIGNAL_STRENGTH_ANALYSIS.md P2 절.

## 다음 할 일 (2026-06 기준 — 상세 이력은 DESIGN.md §9)

최근 완료: signal_strength 분석·개편(kis/signals.py, weak score<3.5) + P1 백테스트(방향 엣지 없음,
throttle이지 알파 아님) + **P1-후속**(2026-06-10, `tools/flipped_day_pnl.py` — flipped uptrend
+1.089% ≈ non-flipped uptrend +0.962% → throttle 확정, strong-down EXIT 시뮬 5종목 -22~-82%p 일관
→ 구 매도 넛지 제거 정당화) + **P2 완료**(2026-06-10, vol 정규화: `BASELINE_VOL=0.015` + `compute_vol_factor` +
`classify_strength(vol_factor=1.0)`, AAPL p50 vol round, 종목 가로 weak 발동률 23.3pp→12.3pp 균일화,
AMD strong 과발동 동시 throttle, `test_signals.py` 23 케이스), 주문 타이밍 결함 발견·실증
(07:30=장종료) + Rank 0 안전패치 + **Rank 2 승인-제출 분리**(거래 경로 완성) + **Rank 2 정규장 제출
실증 완료**(2026-06-10 22:30 KST 개장 직후, `test_rank2_pending.py RUN` Part 2 — pending→submit→체결
ODNO 0000039098 BUY 1주 @ $292.25 + 안전 청산 SELL 0000039135 @ $289.35). 텔레그램 메시지 추세+LLM
사유 풍부화.

최근 완료(2026-06-11): **A(로컬 코드 헬스 게이트)** — venv + test_signals(23)/test_safety_gate(22) 통과,
tzdata requirements 추가(Windows zoneinfo). **B(Phase 2 코드 골격)** — universe 10종목 + sector.py +
llm_advisor 강화 + researcher.decide_parallel + daily_trader 통합(macro_bias N + select_picks). 오프라인
테스트 6스위트 전부 green(test_sector/llm_advisor/researcher/daily_trader 신규). **+ 커밋전 적대적 정밀리뷰
(워크플로 23 에이전트, 6차원→발견별 적대검증) 15건 수정**: staged 누수 해제(unstage_buy), 일일 cap 사이클내
누적(staged 합산), loss-limit·dead-man(consecutive_errors) 실배선, 환각 정규식 CJK 조사 대응, ET 주말가드+
pending dedup, breadth 반도체 한정, SMH 충분성 50, OpenAI timeout. 회귀 test_portfolio 신규 + 7스위트 green.
상세: DESIGN §9(2026-06-11) 표. ⚠️ **A의 서버 soak(7일) + audit verify, B의 운영 검증은 네이버클라우드 VM
에서 수행 — 로컬 dev 박스에는 .state/logs 없음.**

남은 후보:
1. **Phase 2 운영 검증(선결)**: 서버에서 `test/test_universe_health.py`(운영시간 22:30~ KST) 실행 →
   반도체 10종목 모의 거래가능 실측. 일부는 모의 매매 불가일 수 있음(KIS 함정 #4) → paper_tradable=False.
   ⚠️ **배포 순서**: universe 확장이 서버에 배포되면 다음 사이클부터 11종목을 도는다. health 실측 전 라이브
   배포 금지. macro_bias N(risk_off→0) 이 1차 throttle.
2. **잔여 UX — approval.py 다이제스트**: 종목별 토글(기본 OFF) 텔레그램 다이제스트. 현재는 per-pick 단건
   승인으로 다중 픽도 기능 동작(픽 N개=메시지 N개). 친화도 개선이라 실거동 검증과 함께 별도 진행.
3. **A 운영 soak 마저**: daily_trader 7일 무에러(KST 07:30) + `python -m kis.audit verify`(7줄) + Phase 1
   staged_buys 0 리셋/last_buy_at 흔적 — 전부 서버 런타임 증거(VM 에서 점검).
4. **Strong AND-gate 정규화 (P2 잔류)**: Phase 2 운영 중 종목별 strong 빈도 불균일 발견되면 spread/chg
   도 vol_factor 로 정규화 검토.

## 안전/보안 규칙 (반드시 지킬 것)

- `.env`(KIS키, OpenAI키, 텔레그램토큰)는 절대 커밋/푸시 금지. `.gitignore`에 포함.
- 토큰 캐시 폴더 `~/.kis_us_trader/`도 git 제외.
- KIS_ENV는 **paper** 유지. prod 전환은 사용자가 명시적으로 결정하기 전까지 금지.
- 주문/송금/git push 등 되돌리기 어려운 작업은 자동 승인하지 말고 사용자 확인.
- 투자 판단 자체(어떤 종목/전략이 좋은지)는 조언하지 않는다. 구현만 돕는다.