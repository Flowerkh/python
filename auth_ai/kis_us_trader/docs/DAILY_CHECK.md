# 매일 아침 점검 체크리스트

Phase 1 운영 검증 기간(7일) 동안 매일 한국시간 **07:35 이후**(daily_cycle이 07:30에 발화 후 약 5분 뒤)에 수행할 점검 절차.

> 모든 명령은 서버(`root@wedding:/opt/kis_us_trader_repo/auth_ai/kis_us_trader/`)에서 가상환경 활성화(`source .venv/bin/activate`) 후 실행.

---

## 0. 점검 5분 루틴 (요약)

| 순서 | 명령 | 본다 |
|---|---|---|
| 1 | 텔레그램 폰에서 확인 | 시나리오 A/B/C 중 하나의 메시지 도착 여부 |
| 2 | `sudo systemctl status kis-trader --no-pager` | `Active: active (running)` |
| 3 | `tail -30 logs/daily_trader.out` | "price=... signal=... LLM: ..." 로그 |
| 4 | `cat logs/cycles-YYYYMM.jsonl \| tail -1` | 새 audit 한 줄 추가 |
| 5 | `python -m kis.audit verify` | `체인 검증: OK (N줄)` |

다섯 줄 모두 정상이면 그날 점검 끝. 이상이 있으면 §3 트러블슈팅으로.

---

## 1. 사이클 시나리오 — 텔레그램 메시지로 즉시 식별

### 시나리오 A · LLM이 hold 판단 (가장 흔함)
```
😴 AAPL 관망(hold). 사유: <LLM이 설명한 사유>
```
- **추가 메시지 없음.** 주문 안 일어남.
- audit log: `event: cycle_skipped, reason_skip: hold`
- 정상 동작. state.json 변화 없음.

### 시나리오 B · LLM이 buy/sell + confidence ≥ 80 → safety_gate 통과 → 사람 승인 요청
```
🤖 매매 승인 (paper)
종목: AAPL
동작: 매수 1주
지정가: $313.06 (현재 $311.50)
확신도: 88
사유: <LLM 사유>
추세: SMA5>SMA20=True, 5일 +2.3%
현재 노출: $0
[ ✅ 승인 ] [ ❌ 거절 ]
```

#### B-1: ✅ 승인 누름
```
✅ 매수 접수 (모의)
종목: AAPL 1주 @ $313.06
주문번호: 0000034XXX
```
이어서:
```
📊 AAPL 매수 체결 — 보유 1주
```
- audit log: `event: cycle_complete, qty/limit/rt_cd=0/odno` 채워짐.
- state.json: `last_buy_at['AAPL']` = 오늘 ET 날짜, `daily_buy_count=1`, `daily_buy_amount_usd ≈ $313`.

#### B-2: ❌ 거절 누름 (또는 30분 무응답)
- audit log: `event: cycle_skipped, reason_skip: user_reject` (또는 `user_timeout`).
- 주문 안 일어남.

### 시나리오 C · safety_gate가 차단
```
🛡️ AAPL 차단(<check_id>): <한국어 사유>
```
- audit log: `event: cycle_skipped, reason_skip: <사유>, check: <check_id>`
- 11개 가능한 `check_id`:

| check_id | 의미 | 자주 보는 상황 |
|---|---|---|
| `whitelist` | 화이트리스트 외 종목 | Phase 1엔 AAPL뿐이라 안 나옴. Phase 2부터 의미 있음 |
| `invalid_pick` | qty/price ≤ 0 | LLM이 이상하게 hold 외 신호 + 0 가격 — 드묾 |
| `paper_tradable` | universe 캐시에서 paper_tradable=False | 캐시 손상 시 가능. 시드값(True) 폴백되므로 드묾 |
| `sync_failed` | 잔고 sync 실패(빈 응답 등) | KIS 일시 장애 또는 IP 변경 후 인증 만료 |
| `symbol_cap` | 종목 누적 노출이 $2,000 초과 | 이미 10주 이상 보유 + 추가 매수 시도 |
| `sector_cap` | 섹터 노출이 40% 초과 | Phase 1 단일 종목이면 자주 발생 가능(megacap_tech 100% 집중) |
| `total_cap` | 전체 노출이 $10,000 초과 | 누적이 충분히 쌓이지 않으면 안 나옴 |
| `cooldown` | 같은 종목 매수 3일 이내 재시도 | BUY 다음날 또 BUY 신호 나오면 발동 |
| `daily_limit` | 일일 매수 종목수/금액/손실 한도 도달 | 모든 종목 분기에 적용 |
| `holding` | 매도 시 보유 수량 부족 | LLM이 보유 없는데 sell 제안 |
| `internal_error` | safety_gate 내부 예외 | 0이어야 정상 |

### 시나리오 D · 데이터 부족
```
ℹ️ AAPL 일봉 부족(N개). 휴장/운영시간 외일 수 있음.
```
- 한국 시간 07:30 발화 시점이 미국 토/일 휴장이거나 미국 공휴일이면 일봉이 60일 못 받을 수 있음.
- audit log: `cycle_skipped, reason_skip: insufficient_candles`
- 정상 (주말/공휴일 케이스).

### 시나리오 E · 봇 일시 정지
```
⏸️ BOT PAUSED (paused_until=YYYY-MM-DDTHH:MM:SS) → 사이클 skip
```
- `consecutive_errors ≥ 3` 누적 시 자동 24h pause.
- 텔레그램 `/resume` 명령은 아직 미구현(Phase 4) → state.json 직접 편집해 해제:
  ```bash
  python -c "from kis.state import update_state; update_state(lambda s: s.update({'paused_until': None, 'consecutive_errors': 0}))"
  ```

### 시나리오 F · 종목 사이클 오류 (LLM/KIS 등 예외)
```
⚠️ AAPL 사이클 오류: AuthenticationError: Error code: 401 - ...
```
- 종목 처리 중 예외 발생 (LLM 인증 실패, KIS 조회 실패 등). 해당 종목만 건너뛰고 다음 종목/사이클은 계속됨.
- audit log: `event: error, symbol, error`
- state.json: `consecutive_errors += 1` (3 누적 시 자동 24h pause → 시나리오 E)
- 처치: 메시지의 예외 타입으로 원인 판별. `AuthenticationError 401`이면 §3.7 참고.

### 시나리오 G · 승인 → 개장 대기 → 제출 (Rank 2 승인-제출 분리)
07:30 승인(시나리오 B) 후 곧바로 주문되지 않고, **다음 미국 개장(~22:35 KST)** 에 제출된다(07:30은 정규장 마감 후라 즉시주문이 거부되기 때문).
```
✅ AAPL 매수 1주 @ $303.05 승인 → 다음 미국 개장(~22:35 KST)에 제출 예정.   ← 07:30 승인 직후
📊 AAPL 매수 체결 — 보유 1주                                              ← ~22:35 KST 개장 제출+체결
```
- 07:30 승인 시 `state.pending_orders`에 저장, audit `order_queued`. ~22:35 KST `submission_loop`가
  제출 → `cycle_complete`(체결) 또는 `🟡 체결 미확인`(`cycle_accepted_unfilled`, 갭으로 미체결 — 가짜 포지션 안 만듦).
- 변형: 제출 직전 차단 `🛡️ 제출 직전 차단`(`pending_blocked`) / 만료 `⏳ 예약 만료`(18h 초과, `pending_expired`) /
  보유 없어 매도 취소(`pending_skipped`). 배경: docs/ORDER_TIMING_ISSUE.md

---

## 2. 점검 명령 (정상 동작 확인)

### 2.1 서비스 가동 상태
```bash
sudo systemctl status kis-trader --no-pager
```
- ✅ 정상: `Active: active (running) since 2026-06-XX HH:MM:SS KST; Xh Xmin ago`
- ❌ 이상: `Active: failed` 또는 30초 단위로 재시작 반복(Active 시간이 짧으면 의심)

### 2.2 stdout 로그 (오늘 사이클이 정상 발화했나)
```bash
tail -30 /opt/kis_us_trader_repo/auth_ai/kis_us_trader/logs/daily_trader.out
```
- ✅ 정상 (사이클 발화 후):
  ```
  [2026-06-XX 07:30] 일일 사이클 시작
    [AAPL] price=311.5 sma20=305.2 sma5>sma20=True signal=moderate vol_factor=0.95
    [AAPL] LLM: buy (확신도 88) - <사유>
  다음 실행까지 23.9시간 대기...
  ```
  - `signal=weak | moderate | strong` 은 `kis.signals.classify_strength` 가 산출한 추세 강도/변동성 라벨(**방향 신호 아님**). **P2(2026-06-10)**: weak=normalized score<3.5 (score=(spread%+|chg%|)/vol_factor), strong=spread%≥1 & |chg%|≥3 AND norm score≥3.5.
  - `vol_factor` = trailing 20d daily-return stdev / BASELINE_VOL(0.015). AAPL ≈ 1.0(현행 보존), 고변동 종목(AMD/INTC 등) > 1 → score 분모 커져 weak 발동 ↑. Phase 2 진입 시 종목별 weak throttle 균일 보장(측정 12.3pp 범위).
  - `signal=weak` 이면 LLM 프롬프트 룰상 강제로 `hold` + confidence ≤ 50 → 시나리오 A. weak 은 설계상 **AAPL 기준 ~27%(P2 후), 고변동 종목 ~30~39% 발동**(보수 브레이크).
  - `signal=strong` 은 `CONFIDENCE_THRESHOLD=80` 을 넘길 수 있는 유일한 밴드 → 데이터가 한 방향을 충분히 뒷받침하면 시나리오 B. 고변동 종목은 raw spread/chg 가 strong 임계를 넘어도 norm score 가 낮으면 weak (AMD strong 과발동 throttle).
- ❌ 이상:
  - "일일 사이클 시작" 줄 자체가 없으면 시각/스케줄러 문제.
  - Python traceback이 있으면 §3.2 참고.

### 2.3 audit log 한 줄 추가됐는지
```bash
ls /opt/kis_us_trader_repo/auth_ai/kis_us_trader/logs/
# cycles-202606.jsonl 같은 월별 파일 보임

# 마지막 한 줄
tail -1 /opt/kis_us_trader_repo/auth_ai/kis_us_trader/logs/cycles-202606.jsonl | python -m json.tool
```
- ✅ 정상: `ts`/`prev_hash`/`event`/`symbol`/`action`/`confidence`/`hash` 필드 모두 채워짐.
- ❌ 이상: 어제와 같은 hash가 마지막 줄이면 → 오늘 사이클이 발화 안 함.

### 2.4 state.json 변화 (BUY가 일어났다면)
```bash
cat /opt/kis_us_trader_repo/auth_ai/kis_us_trader/.state/state.json | python -m json.tool
```
- ✅ BUY 후: `last_buy_at: {"AAPL": "2026-06-XX"}` (ET 날짜) + `daily_buy_count ≥ 1` + `daily_buy_amount_usd > 0`
- ✅ hold/skip만 일어난 날: 변화 없음 (정상)
- ❌ 이상: `consecutive_errors ≥ 1`이면 어제 무슨 문제가 있었던 것 → §3 참고

### 2.5 hash chain 무결성
```bash
python -m kis.audit verify
```
- ✅ 정상: `체인 검증: OK (N줄)` (N은 누적 사이클 수)
- ❌ 이상: `FAIL` + 사유 출력 → audit 파일이 손상되었거나 변조된 것. 즉시 백업하고 조사.

---

## 3. 트러블슈팅

### 3.1 텔레그램 메시지가 안 옴
1. systemd 가동 여부 확인:
   ```bash
   sudo systemctl status kis-trader
   ```
   `inactive (dead)`이면 → `sudo systemctl restart kis-trader`
2. 사이클이 발화는 했는데 메시지 누락이면 (rare):
   - 텔레그램 API 장애 가능성 → 30분 후 재시도
   - `.env`의 `TELEGRAM_CHAT_ID` 변경되지 않았는지 확인
3. 시각 자체가 안 맞으면:
   ```bash
   timedatectl status   # NTP synchronized: yes 여야 함
   ```

### 3.2 systemd 서비스가 30초마다 재시작 반복
```bash
sudo journalctl -u kis-trader -n 100 --no-pager
```
흔한 원인:
| 증상 | 원인 | 처치 |
|---|---|---|
| `ModuleNotFoundError: No module named 'X'` | 의존성 누락 | `source .venv/bin/activate && pip install -r requirements.txt` |
| `SystemExit: .env에 TELEGRAM_BOT_TOKEN...` | `.env` 누락 또는 권한 | `ls -la .env` 확인, chmod 600 |
| `requests.exceptions.HTTPError` 등 KIS API | IP 변경/토큰 발급 한도 | 24h 대기 또는 KIS IP 재등록 |
| Telegram 401/403 | 봇 토큰 무효화 | BotFather에서 토큰 재발급 후 `.env` 갱신 |

### 3.3 사이클은 발화했는데 hold만 계속 나옴
- 상당 부분 정상 — weak 은 설계상 종목별 ~27~39% 발동(P2 vol 정규화 후, LLM 에 hold 강제하는 보수 브레이크)이고, `CONFIDENCE_THRESHOLD=80` 상 strong 만 거래 문턱을 넘으므로 hold/skip 이 흔하다.
- `signal=...` / `vol_factor=...` 라벨로 구분:
  - `signal=weak` 비중이 과도하면 (a) `vol_factor` 가 큰 시점(고변동 국면)인지, (b) `kis/signals.py` 의 `WEAK_SCORE_CUT`(현 3.5)/`BASELINE_VOL`(현 0.015)이 현재 변동성 대비 높을 수 있음 → `tools/tune_thresholds.py` 로 분포 재확인, `tools/vol_calibration.py` 로 BASELINE_VOL sweep 후 조정 검토.
  - `signal=moderate/strong` 인데도 매일 hold/skip 이면 LLM 이 보수적이거나 confidence<80 으로 걸러진 것. 라벨은 '방향' 신호가 아니라(분석상 방향 예측력 없음) 정상 범주.
  - 구 AND-gate 시절엔 반대로 weak 이 ~1.7%만 떠 브레이크가 死문자였음(P1 개편으로 해소). P2 후엔 종목별 균일화 + AMD strong 과발동도 동시 throttle — docs/SIGNAL_STRENGTH_ANALYSIS.md P2 절.
- 7일 전부 hold 라도 audit log에 `signal_strength` + `vol_factor`(P2)가 박혀 있어 사후 회고 가능.

### 3.4 `consecutive_errors`가 누적되고 있음
```bash
cat .state/state.json
```
- `consecutive_errors: 1~2` → 일시적 오류, 다음 정상 사이클에서 리셋됨
- `consecutive_errors: 3` 이상 → 다음 사이클에서 자동 24h pause 발동 직전
- 원인 추적: `sudo journalctl -u kis-trader --since '24 hours ago' --no-pager | grep -i error`

### 3.5 paused_until 풀고 싶음
```bash
source .venv/bin/activate
python -c "from kis.state import update_state; update_state(lambda s: s.update({'paused_until': None, 'consecutive_errors': 0}))"
cat .state/state.json   # paused_until: null 확인
```
서비스 재시작 불필요 — 다음 사이클 시작 시 `is_paused` 검사가 다시 통과.

### 3.6 audit chain이 깨졌다면
1. 백업: `cp logs/cycles-YYYYMM.jsonl logs/cycles-YYYYMM.jsonl.bak`
2. 깨진 위치 확인: 출력에 `line N: ...` 형식 사유 표시됨
3. 그 줄이 사람 손에 닿은 적 없는데 깨졌다면 파일시스템/디스크 이슈 가능 — VM 스냅샷 복구 검토
4. 정상 케이스: 운영 중에는 절대 발생하지 않아야 함. 발생 자체가 적신호.

### 3.7 `⚠️ 사이클 오류: AuthenticationError ... 401` (OpenAI 키)
- `.env`의 `OPENAI_API_KEY`가 무효(폐기/오타/서버-로컬 불일치).
- 확인: `grep OPENAI_API_KEY .env` 로 키 출처 점검. `.venv/bin/python llm_advisor.py` 단독 실행으로 키 유효성 즉시 검증.
- ⚠️ `.env` 수정 후엔 반드시 `sudo systemctl restart kis-trader` — 떠 있는 프로세스는 시작 시점의 키를 메모리에 들고 있어 재시작 전까지 안 바뀜.
- `OPENAI_MODEL`도 유효한 모델명인지 확인 (잘못되면 `model_not_found`).

---

## 4. 7일 운영 누적 체크 (Phase 1 종료 기준)

매일 점검 후 아래 표 한 줄씩 채우면 7일 후 한 번에 판단 가능.

| 날짜(KST) | 사이클 시각 | LLM 결과 | safety_gate | 사람 승인 | 체결 | audit 줄 수 | consecutive_errors |
|---|---|---|---|---|---|---|---|
| 2026-06-05 | 07:30 | hold/buy/sell (conf) | pass/check_id | ✅/❌/skip | 매수 N주/없음 | (누적 N줄) | 0 |
| 2026-06-06 | | | | | | | |
| 2026-06-07 | | | | | | | |
| 2026-06-08 | | | | | | | |
| 2026-06-09 | | | | | | | |
| 2026-06-10 | | | | | | | |
| 2026-06-11 | | | | | | | |

### Phase 1 통과 조건 (7일 후 평가)
- [ ] **7일 모두 사이클 정상 발화** (이상 0건). 휴장으로 `insufficient_candles` skip된 날은 정상으로 카운트.
- [ ] `python -m kis.audit verify` → `OK (≥7줄)`
- [ ] state.json의 `consecutive_errors ≤ 1`
- [ ] safety_gate 차단이 발생했다면 audit log에 `check` 필드가 정확히 기록됨
- [ ] BUY가 일어났다면 그 다음 3일간 `cooldown` check로 차단되는 게 확인됨 (REBUY_COOLDOWN_DAYS=3 동작 검증)
- [ ] Phase 0 회귀: `python test/test_balance_parse.py` / `test/test_order.py` / `test/test_roundtrip.py` 여전히 통과 (월 1회 정도 실측)

모두 충족하면 → **Phase 2 진입**(`kis/universe.py`에 반도체 10종목 추가, `sector.py` 작성, llm_advisor.py 수정 등).

---

## 5. 응급 절차

### 5.1 즉시 매매 중단
```bash
sudo systemctl stop kis-trader
sudo systemctl disable kis-trader   # 부팅 시 자동 시작도 차단
```
- 진행 중인 사이클 끝나고 종료 (이미 접수된 주문은 KIS 측에서 진행)
- 미체결 주문 잡혀 있으면 한국투자증권 앱에서 수동 취소

### 5.2 봇 일시 정지(서비스는 가동, 사이클만 skip)
```bash
source .venv/bin/activate
python -c "from datetime import datetime, timedelta; from kis.state import update_state; until = (datetime.now() + timedelta(hours=24)).isoformat(timespec='seconds'); update_state(lambda s: s.update({'paused_until': until}))"
```
- 다음 24h 동안 사이클이 발화해도 즉시 skip + 텔레그램 `⏸️ BOT PAUSED` 메시지 1건.

### 5.3 prod 전환 절대 금지 확인
`.env`의 `KIS_ENV=paper` 유지. prod로 바꾸려면 충분한 검증 + 명시적 의사결정 필요. 본 봇 운영 중에는 절대 prod 전환 금지.

---

## 6. 메모 (자유 기록)

매일 점검하면서 발견한 이상/패턴/개선 아이디어는 다음 형식으로 기록:

```
[2026-06-XX] 관찰: ...
[2026-06-XX] 조치: ...
[2026-06-XX] TODO: ...
```

이 메모가 쌓이면 Phase 2 진입 시 우선순위 결정에 활용됩니다.
