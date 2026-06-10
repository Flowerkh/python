# Phase 2 라이브 배포 + 2주 운영 검증 런북

> 반도체 다종목(11) Phase 2(커밋 `95fc503`)를 네이버클라우드 VM(`/opt/kis_us_trader_repo/auth_ai/kis_us_trader`,
> systemd `kis-trader.service`, root, `.venv`)에 **재배포(git pull + restart)**하고 2주 검증하는 절차.
> 최초 셋업은 [DEPLOY_NAVER_CLOUD.md](./DEPLOY_NAVER_CLOUD.md). 이 문서는 **업데이트 배포** 전용.
> 근거: 2026-06-11 배포준비 워크플로(3 에이전트, 코드/문서 실측). 서버 `test_universe_health.py` 11/11 통과(선결 해제).

---

## 0. ⚠️ 배포 전 필수 게이트 2개 (둘 다 통과해야 배포)

Phase 2는 단위테스트로 못 잡는 **서버 환경 의존 2가지**가 매수 경로를 조용히 무력화할 수 있다. **배포 전에 반드시 서버에서 실측**한다(읽기 전용, 주문 0).

### 게이트 A — SMH(반도체 ETF)가 KIS paper 일봉 조회되는가 [CRITICAL]
`macro_bias`는 `SMH` 일봉으로 산출된다. SMH가 paper 엔드포인트에서 조회 안 되면(ETF는 모의에서 막힐 수 있음 — KIS 함정 #4) `bias='unknown' → N=0 → 모든 BUY 영구 컷`이 되는데 **에러 없이 hold만 계속**되어 정상으로 오인된다.

```bash
cd /opt/kis_us_trader_repo/auth_ai/kis_us_trader && source .venv/bin/activate
python sector.py
```
- **통과**: `bias` 가 `risk_on/neutral/risk_off` 중 하나 + `smh_price/smh_sma20/smh_sma50` 숫자 + `samples≥50`.
- **실패**(`bias=unknown`, `smh_price=None`, `samples<50` 또는 0): SMH 조회 불가. **배포 보류**.
  → 대안: breadth(10종목 above_sma20, 추가 KIS 호출 0) 기반으로 bias 산출하도록 `sector.py` 수정 후 재배포.
  (이 경우 알려주세요 — `compute_macro_bias`의 SMH 실패 시 breadth 폴백을 구현합니다.)

### 게이트 B — 서버 .env의 OpenAI 키가 유효한가 [HIGH]
`decide_parallel`이 사이클당 11콜. 키가 무효면(과거 `sk-svcac…` 401 사고) **11종목 전부 hold 폴백 + consecutive_errors 증가 안 함 → auto-pause도 안 걸림 → 조용히 거래 0**.

```bash
python llm_advisor.py
```
- **통과**: 실제 JSON advice(`{"action":...,"confidence":...}`) 출력.
- **실패**(401/AuthenticationError): `.env`의 `OPENAI_API_KEY`를 유효 키(`sk-proj…`)로 교체 → **서비스 재시작 필수**(키는 프로세스 시작 시 1회 로드).

---

## 1. 재배포 절차 (9단계, 서버에서)

> 07:30 KST 사이클 밖 시간대에 수행 권장(사이클 중 파일 변경 회피).

```bash
# 1) 구 프로세스 정지
sudo systemctl stop kis-trader && sudo systemctl status kis-trader --no-pager | head -5
# → Active: inactive (dead) 확인. (pgrep -af daily_trader.py 비어야 함)

# 2) 런타임 상태 백업(.state/logs는 git-ignore라 pull이 안 건드리지만 보험)
cd /opt/kis_us_trader_repo/auth_ai/kis_us_trader
tar czf /root/kis_state_backup_$(date +%Y%m%d_%H%M).tgz .state logs/cycles-*.jsonl 2>/dev/null
cp .state/state.json /root/state.json.bak_$(date +%Y%m%d_%H%M)

# 3) 새 커밋 확인(읽기 전용)
cd /opt/kis_us_trader_repo && git fetch origin && git log --oneline -1 origin/master && git rev-parse --short HEAD
# → origin/master == 95fc503, 현재 HEAD == 구 sha(c51bf12 등)

# 4) fast-forward pull (sparse cone 안이라 sector.py/researcher.py 자동 반영)
git pull --ff-only origin master && git rev-parse --short HEAD
ls auth_ai/kis_us_trader/sector.py auth_ai/kis_us_trader/researcher.py
# → HEAD == 95fc503, 두 신규 파일 존재. (--ff-only 실패 시 서버 트리에 로컬 변경 있음 → 조사)

# 5) 의존성(신규 tzdata 1개, Linux엔 무해·멱등)
cd auth_ai/kis_us_trader && source .venv/bin/activate && pip install -r requirements.txt
# → 기존 5개 already satisfied + tzdata 설치. venv 재생성 금지.

# 6) 오프라인 빌드 체크(신규 Phase 2 코드 경로, 네트워크·주문 0) — 실패 시 재시작 금지
python test/test_sector.py && python test/test_researcher.py && python test/test_llm_advisor.py \
 && python test/test_daily_trader.py && python test/test_safety_gate.py && python test/test_portfolio.py \
 && python test/test_signals.py
# → 각 '총 0건 실패' / test_safety_gate '[OK] safety_gate 25 cases all passed'

# 7) 새 코드 기동
sudo systemctl start kis-trader && sleep 3 && sudo systemctl status kis-trader --no-pager | head -12
# → Active: active (running), 단일 PID, 재시작 루프 없음.
#   텔레그램 '🚀 하루1회 자동매매 시작 (모의)...' 도착.

# 8) 기동 로그 확인
tail -n 30 logs/daily_trader.out; echo '--- ERR ---'; tail -n 20 logs/daily_trader.err
journalctl -u kis-trader -n 20 --no-pager
# → '=== 하루 1회 자동매매 시작 ===' + '다음 실행까지 X.X시간 대기...' + '[submit] 다음 제출 창까지 ...'.
#   err 비어있고 Traceback/30초 재시작 루프 없음.

# 9) 감사체인 + state 후방호환 확인
python -m kis.audit verify && python -m kis.state
# → 체인 OK. state.json에 pending_orders/open_orders 키 존재 + 기존 last_buy_at/consecutive_errors 보존
#   (_merge_defaults가 구 state.json을 무손실 업그레이드).
```

**배포영향 변경 요약**: 신규 파일 `sector.py`/`researcher.py`(sparse cone 안 → pull 자동), 신규 의존성 `tzdata`(Linux 무해),
state 스키마 신규 필드 없음(`pending_orders`/`open_orders`는 이미 DEFAULT_STATE), systemd unit 무변경. KIS IP/토큰 캐시 영향 없음.

---

## 2. 롤백 (새 코드 이상 시 → AAPL 단종목 구버전)

```bash
sudo systemctl stop kis-trader
cd /opt/kis_us_trader_repo && git checkout c51bf12         # Phase 2 직전(AAPL-only). detached HEAD 운영 OK
cd auth_ai/kis_us_trader && source .venv/bin/activate && pip install -r requirements.txt   # 선택(tzdata 남아도 무해)
# state 손상 시에만: cp /root/state.json.bak_<TS> .state/state.json  (구 코드는 신규 키 무시)
sudo systemctl start kis-trader && sudo systemctl status kis-trader --no-pager | head -8
# 복귀: git checkout master && git pull --ff-only origin master 후 §1의 5~9 재실행.
```
> state.json은 전/후방 호환(구 코드는 신규 키 무시, 신 코드는 `_merge_defaults`로 추가) → DB 마이그레이션 없음, 순수 코드 레벨 롤백.

---

## 3. 2주 운영 검증 체크리스트

### 3.1 매일 아침(KST 07:35+) 점검
- 텔레그램 **'📋 점검 요약'** 1건: `🧭 매크로 bias=… → 신규매수 상한 N=…` + `선정: 매수 […] / 매도 […]`. (Phase 2 핵심 신규 산출물)
- `systemctl status kis-trader` → `active (running)`, uptime 길게(30초 재시작 반복 X).
- `tail -40 logs/daily_trader.out` → **11종목** `[SYM] price=… signal=… above20=…` 라인 + `macro_bias …` 한 줄. **AAPL만 보이면 구 코드**.
- `python -m kis.audit verify` → `OK (N줄)`, N 매일 증가.
- `cat .state/state.json | python -m json.tool` → `consecutive_errors`(0~1), `paused_until: null`, `pending_orders`, `last_buy_at`.
- **macro_bias 값 매일 메모** — `unknown` 연속이면 SMH 조회 실패(BUY 전면 정지). 정상 아님.
- (KST ~22:35 개장 직후) pending 있었으면 `📊 체결` 또는 `🟡 체결 미확인` 도착 여부.

### 3.2 audit 이벤트 의미 (logs/cycles-YYYYMM.jsonl)
| event | 의미 | 조치 |
|---|---|---|
| `cycle_summary` | 사이클 결과(bias/n_buys/selected_buys/sells/candidates). 사이클당 1줄 | candidates=평일 11, selected_buys 길이 ≤ n_buys 확인 |
| `reason_foreign_ticker` | reason에 다른 화이트리스트 ticker → hold 강등(교차오염 차단) | 발생=안전장치 정상. 그 종목 매수승인 요청 0건 교차확인 |
| `auto_paused` | consecutive_errors≥3 → 24h 자동정지(🛑) | **STOP·조사**. 원인 해소 후 `paused_until=null` + `consecutive_errors=0` 둘 다 리셋 |
| `order_queued` | 07:30 승인분 pending 큐잉(Rank 2) | ~22:35 제출창서 cycle_complete/accepted_unfilled로 짝 확인 |
| `order_dedup_skipped` | 같은 (symbol,side) 미만료 pending 중복 → 재큐잉 차단(↩️) | 정상. 반복되면 submission_loop 미발화 의심 |
| `cycle_complete` | 정규장 제출+잔고확인 체결(odno). 실거래 증거 | 한투 앱서 odno 교차확인. 이후 3일 cooldown 추적 |
| `cycle_accepted_unfilled` | 접수(rt_cd=0)됐으나 미체결 → apply_fill 안 함 | 단건 정상. 같은 종목 반복 누적이면 review#8 갭 — 한투 앱 미체결 확인 |
| `cycle_error` | 제출서 KIS rt_cd≠0 거부 | msg1로 원인. consecutive_errors+1 |
| `pending_blocked` / `pending_expired` / `pending_skipped` | 제출직전 재검증 차단 / 18h 만료 / 매도시 보유0 | 전부 정상 안전장치. check id 기록 |
| `cycle_skipped reason=et_weekend` | KST 일·월(=ET 토·일) 전면 skip | 주 2회 정확히. 평일에 뜨면 TZ 오류 |
| `cycle_skipped check=<id>` | safety_gate 차단(sector_cap/daily_limit/cooldown 등) | check별 빈도 기록 — Phase 2 cap 검증 핵심 |

### 3.3 🚩 즉시 STOP/조사 red flags
- 화이트리스트 **외 ticker**(TSLA/MSFT 등) 매수 승인 요청 1건이라도 → universe 누수. 즉시 STOP.
- AAPL만 보이고 반도체 9종목 안 보임 → 구 코드 가동 중(재배포 실패).
- 30초 주기 재시작 반복 → 신규 import(sector/researcher) ImportError 또는 .env 누락. `journalctl -u kis-trader -n 100`.
- `auto_paused` 발생 → 24h 정지. 원인(LLM 401/KIS 거부/네트워크) 미해소 시 STOP.
- 평일 `macro_bias=unknown` 반복 → SMH 조회 실패. `python sector.py`로 smh_price=None 확인.
- `selected_buys > n_buys` 또는 risk_off/unknown인데 BUY 승인 요청 → select_picks N 상한 회귀.
- `reason_foreign_ticker` 강등됐어야 할 종목이 매수승인 도달 → sanitize_advice 차단 깨짐.
- 같은 종목 같은 ET날짜 2회+ cycle_complete(BUY) → cooldown/dedup 실패.
- pending_orders 며칠째 누적 → submission_loop 미발화.
- `kis.audit verify` FAIL → audit 손상. 백업 후 조사.
- `KIS_ENV`가 paper 아님 → 즉시 STOP.

### 3.4 2주 합격 기준(전부 충족 = Phase 2 운영 검증 완료)
- [ ] 화이트리스트 외 종목 누수 **0건**(승인요청·audit symbol 전부 11종목 내).
- [ ] macro_bias N 매핑 100% 일치(risk_on3/neutral2/off0/unknown0), risk_off·unknown 날 selected_buys 항상 빈 배열. bias 2종 이상 관측.
- [ ] staged/일일 cap 차단 실증 1건+ (BUY 후보 N+1개 시 daily_limit, 또는 반도체 누적 시 sector_cap 차단 박제).
- [ ] 주말 스킵 정확: KST 일·월만 `et_weekend` skip, 평일 0건.
- [ ] 중복 큐잉 방지: `order_dedup_skipped` 발생 또는 pending이 매 개장 정상 비워짐(둘 중 하나).
- [ ] 실거래 라운드트립 1~2건: 승인→order_queued→~22:35 제출→cycle_complete(odno). 미체결은 가짜 포지션 안 만듦(last_buy_at 미갱신).
- [ ] cooldown: BUY 체결 종목 3일 내 재매수 `cycle_skipped(check=cooldown)`.
- [ ] 교차오염 차단: `reason_foreign_ticker` 종목은 동일 사이클 매수승인 0건.
- [ ] 무에러 안정성: 2주 내내 active(running), `auto_paused` 0건, consecutive_errors가 2 초과한 적 없음.
- [ ] 감사 무결성: 매일 `audit verify` OK, 줄 수 단조 증가.

---

## 4. 잔여/후속 (운영 중 발견 시)
- **review #8** — `submit_open_orders` 제출 루프는 staged 미사용이라 접수-미체결 주문이 일일 cap(state)에 안 잡힘.
  슬로우필 + 다중 근접예산 BUY 한정(paper+사람승인으로 폭발반경 작음). `open_orders` 예약회계로 보강(후속).
- **approval.py 다이제스트** — per-pick 승인이 N개 메시지. 무인 운영 시 30분×N 직렬 대기 → 다이제스트/타임아웃 단축 검토.
- **US 공휴일 미반영** — 공휴일 KST 화~토에도 사이클 발화(pending 큐잉 후 다음 개장 제출, 무해). 향후 휴장 캘린더.
- **auto-pause 풋건** — 정지 해제 시 `paused_until`만 지우면 다음 사이클 재정지. **항상 `consecutive_errors=0`도 함께** 리셋.
