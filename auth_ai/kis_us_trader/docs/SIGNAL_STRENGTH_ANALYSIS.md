# signal_strength 분석 & 튜닝 로드맵

> `compute_trend()`의 `signal_strength`(weak/moderate/strong) 라벨이 실제로 무엇을
> 예측하는지 2년 × 5종목 데이터로 검증하고, 그 결과로 코드를 어떻게 바꿀지 정리한 문서.
> 작성: 2026-06-09. 분석 하네스는 Yahoo 일봉(=KIS와 일치 검증됨) 기반, KIS 토큰 미사용.

---

## TL;DR (적대적 검증을 거친 결론)

1. **`weak` 레버가 죽어 있었다.** 구 AND-gate(`spread<0.3% AND chg<1%`)는 실측상 weak이
   모든 종목에서 ≤1.7%만 발동 → 설계의 "weak → hold 강제 + confidence≤50" 보수 브레이크가
   사실상 死문자였다. **→ 수정함(아래).**
2. **단일 전역 임계값은 종목마다 의미가 다르다.** `strong`이 AAPL은 상위 31%지만 AMD는 64%.
   변동성에 좌우됨. Phase 1(AAPL 단일)에선 잠복, Phase 2에서 문제화.
3. **라벨은 가격 '방향'을 예측하지 못한다.** 2년 5종목 전부에서 `strong`이 base 적중률을
   넘지 못함(0/5). 최근 80일 AAPL은 모멘텀처럼 보였으나(5일 적중 74%, t+3.1) **표본 밖에서
   역전**(48%, t−2.4; 겹침 보정 시 t−1.18) — 국면 아티팩트. 겹침 보정 후 "약한 역추세"
   주장도 사라짐 → 정직한 표현은 **"이 표본에서 강건한 방향 엣지 미관측"**(검정력 부족 포함).
4. **라벨은 forward '변동성'을 일부 예측한다**(NVDA·INTC 유의, 2/5). 대부분 `|chg|`항의
   평범한 변동성 군집에서 옴. 따라서 라벨의 정당한 용도는 **방향 신호가 아니라 보수성/사이징
   throttle**.
5. **결정타:** `CONFIDENCE_THRESHOLD=80`상 weak(≤50)·moderate(50~75)는 거래 문턱을 못 넘고
   **strong만 거래 경로**다. 그런데 옛 프롬프트는 `strong → "명확한 추세, buy/sell 결정 가능"`
   이라 방향성 넛지가 사실상 **유일한 매매 트리거**였다. **→ 수정함(아래).**

---

## 증거 요약 (full 2y = 480 표본/종목)

| 항목 | AAPL | NVDA | AMD | TSM | INTC |
|---|---|---|---|---|---|
| 구 weak 발동률 | 1.7% | 1.5% | 0.2% | 0.6% | 0.6% |
| strong 5일 적중 vs base | 48 vs 49 | 48 vs 49 | 53 vs 55 | 54 vs 56 | 42 vs 44 |
| fwd|vol| strong>weak 유의? | n.s. | **t4.31** | n.s. | 반대 | **t2.95** |
| spread p30/p75 | 1.32/3.53 | 1.54/5.35 | 2.91/8.17 | 2.02/5.03 | 2.37/8.92 |

- **방향:** 0/5 종목에서 strong이 base 적중률 초과 못함. 겹침 보정(Newey-West/비겹침 부분표본)
  시 모든 strong t값 |t|<1.4로 붕괴 → null.
- **국면 의존:** AAPL 최근 80일 strong 5일 적중 74%(t+3.1) → full-2y 48%(t−2.4). 80일 창에
  튜닝하면 과적합.
- **검증 방법:** 통계·퀀트·시스템 3개 독립 렌즈의 적대적 검증 통과(겹침 보정, 다중비교,
  검정력, event-study, 방향 분리 테스트 포함).

---

## 적용된 변경

커밋 `809967e` (P 이전):
- **`kis.signals.classify_strength` 신설**(이 커밋 이후 `kis/signals.py`로 단일화) —
  weak 판정을 `score(=spread%+|chg%|) < WEAK_SCORE_CUT(3.5)`로 교체. AAPL 2년 weak ~31%
  (전 구간 22~31%)로 정상화. `strong` AND-gate(spread≥1.0 AND chg≥3.0)는 유지.
- **`llm_advisor` SYSTEM_PROMPT** — `strong → buy/sell 결정 가능` 방향성 넛지 삭제.
  `signal_strength`를 '강도/변동성' 라벨로 재정의, 방향은 데이터 필드로만 판단하도록 명시.

이전 관련 커밋: `58fc1f6`(종목 오류 텔레그램 알림), `b3f68e6`/`4cd4ac4`(tune_thresholds 도구).

---

## P1 결과 — end-to-end 백테스트 (2026-06-10 · 3렌즈 적대적 검증)

> 2년×5종목(AAPL/NVDA/AMD/TSM/INTC) Yahoo 일봉, 결정적 Python, 미look-ahead. 하네스: `%TEMP%\sma_analysis\p1_backtest.py`.
> **총평: 이번 세션 변경(weak 부활 + strong 방향성 넛지 제거)은 long-only 봇에서 알파가 아니라
> 안전성/정합성 수정. signal_strength엔 거래가능한 방향 엣지 미검출 — "throttle이지 알파 아님" 재확인.**

- **P1a (확정·HIGH) — 방향 엣지 없음.** 비겹침 strong−weak 적중차 −6.8%p(z=−1.09), MDE 17.5%p ≫ 6.8%p.
  교차종목 상관(ρ̄=0.417, VIF=2.67) 보정 시 CI [−26.7,+13.2]로 더 넓어져 "엣지 없음"이 강화됨.
  ⚠️ 초안의 "strong은 약한 평균회귀(45%)"는 **삭제** — 5개 위상 중 최극단값(나머지 51/51/49/49%)인
  단일위상 아티팩트(p=0.13~0.55). 결론은 "미검출"(0 증명 아님).
- **P1b (결론 유지·근거 강등) — "P&L 중립"은 long-only 진입 트리거(룰 프록시)에 한해 참.**
  0/480 포지션 동일은 측정이 아니라 **항등식**(old/new strong 정의 동일 + 진입조건 "strong&up" 동일).
  실제 라벨은 363/2400일(15.1%) 바뀜(weak 0.9%→16%). → "알파 아님·안전성 수정" 메시지는 옳으나
  **실제 LLM이 안 변했다는 증거는 아님**. 근거는 flipped-day 분석으로 재정립 필요(아래 P1-후속).
- **P1c (확정·HIGH, 문구수정) — 시그널 타이밍은 buy&hold 열위 = 타이밍 알파 없음.**
  +41.7 vs +133.3%, Sharpe 1.15 vs 1.38, 거래 433 vs 5, 노출 30%. 단 "가치 없음"은 과장 —
  선택일 일평균이 오히려 높고(+0.288 vs +0.205%), MDD 약 1/3 감소(−24.1 vs −35.8%).
  **가치는 하락방어(throttle)**, 격차 대부분은 상승장 70% 현금보유 기회비용.
- **P1d (확정·MED) — strong에 방향 베팅(하락추세 숏 포함)은 손실.** Strong_LS −14.5%,
  그중 **숏 레그 단독 −40.0%**(롱 +41.7%) = 손실 전부 방향성 숏. 넛지 제거 정당화.
  단 (i) 2년 상승장 효과(최근 250/120일은 +27.9/+15.2 양전), (ii) "보유 롱을 strong-하락에 청산"하는
  실제 위해경로는 미시뮬(숏을 flat서 시작).
- **P1e (확정·HIGH) — 한계:** 2년 상승장+생존편향(5종목 전부 급등), 프록시≠LLM, 검정력 부족,
  5bps 가정(50bps서 음전), 위상 1/5만 샘플, 교차상관으로 SE ~1.63× 과소. **0/480 항등식은 P1b의 1급 한계.**

**P1-후속 (가장 가치 큼):** 0/480이 빠뜨린 **flipped-day P&L** — 라벨 바뀐 363일(특히 weak 0.9%→16%)에서
구 파이프라인 행동 vs `weak→hold`의 forward P&L 비교 + "보유 롱을 strong-하락에 청산 vs 유지" 시뮬.
이것이 P1b를 항등식에서 측정으로 바꾸고 P1d 위해경로를 직접 테스트함.

---

## 현재 상태 (2026-06-10 · 다음 세션 resume 지점)

- **P0·P1 완료 + 서버 배포·검증 끝.** production 라벨(kis.signals) 동작 확인(AAPL weak ~25%, 브레이크 부활),
  첫 라이브 07:30 사이클 정상 완주, P1 백테스트 + 적대적 검증 완료(위 "P1 결과" 참고).
- **다음 후보 (택1)**: ① **P1-후속**(flipped-day 측정 — P1b를 항등식→측정으로) / ② **P2**(종목별 정규화) /
  ③ **주문 실행 Rank 1·2**(`ORDER_TIMING_ISSUE.md` — 봇이 실제 거래 못 하는 결함). 새 세션은 이 문서 +
  `ORDER_TIMING_ISSUE.md`를 읽고 이어가면 됨.
- ⚠️ KIS `dailyprice`는 ~100일만 반환 → 서버 `tune_thresholds`는 최근 80일 창만 보여
  방향 적중률이 좋아 **보임**(국면 아티팩트). 방향 엣지 판정 금지. 2년 분석이 진짜 그림.
- ⚠️ 2년×5종목 분석 원본(Yahoo JSON + 하네스)은 repo 밖 `%TEMP%\sma_analysis`(휘발성).
  P1은 Yahoo 재수집으로 재현 가능. 하네스 보존이 필요하면 `tools/`로 이전할 것.

---

## 로드맵

### P0 — 후속 동기화 (진행 중)
- [x] `kis/signals.py`로 임계값/분류 로직 단일화 → `daily_trader`·`tools/tune_thresholds` 공유
      (도구의 옛 AND-gate 복제본이 production과 어긋나는 드리프트 제거).
- [x] `DAILY_CHECK.md` 기대값 갱신(weak ~0% → ~30%, 시나리오 A(hold) 흔해짐).

### P1 — 결정적 검증: end-to-end 백테스트  ✅ 완료(2026-06-10)
- [x] 2년×5종목 백테스트 + 3렌즈 적대적 검증 → **위 "P1 결과" 섹션** 참고. 결론: 방향 엣지 미검출(P1a),
      변경은 P&L 중립=안전성 수정(P1b), 타이밍 알파 없음·하락방어만(P1c), 방향 베팅은 손실(P1d).
- [ ] **P1-후속**: flipped-day P&L(라벨 바뀐 363일) + "보유 롱 strong-하락 청산" 시뮬 → P1b를
      항등식에서 측정으로 전환, P1d 위해경로 직접 테스트.

### P2 — Phase 2 진입 시
- [ ] **종목별/변동성정규화 임계값.** `WEAK_SCORE_CUT=3.5`는 AAPL 전용(증거: weak이 AAPL 31%
      vs AMD 8%). score를 종목 자체 변동성(트레일링 실현변동성 or ATR)으로 정규화하면 컷 1세트로
      통일. 반도체 10종목 추가 시 같이.

### 설계 질문 (정해두면 좋음)
방향 엣지가 없고 strong이 유일 거래 경로인 구조에서 Phase 1 의도:
- (a) 현 상태: strong + 데이터 명확할 때만 사람 승인 하 매매 *(무난)*
- (b) 라벨을 순수 자문/보수용으로 강등, 방향·결정은 사람이 *(가장 보수적)*
- (c) moderate도 거래 가능하게 문턱 하향 *(공격적, 비권장)*

---

## 재현 방법

```bash
# 서버(KIS IP 등록 환경)에서: 종목별 분포 + production/score 라벨의 directional 검증
.venv/bin/python tools/tune_thresholds.py AAPL
.venv/bin/python tools/tune_thresholds.py AAPL 250    # 일봉 일수 지정
```

분석 하네스 원본(Yahoo 일봉, KIS 토큰 미사용, 2년×5종목)은 임시 분석용으로 repo 밖에서
수행됨. production 라벨링은 `kis/signals.py` 한 곳이 진실 소스.

## 관련 파일
- `kis/signals.py` — 임계값 상수 + `classify_strength` (단일 진실 소스)
- `daily_trader.py` — `compute_trend`(라벨 사용), `CONFIDENCE_THRESHOLD=80`(거래 문턱), 게이트
- `llm_advisor.py` — `SYSTEM_PROMPT`(라벨 해석 규칙)
- `tools/tune_thresholds.py` — 읽기 전용 분포/검증 도구
- `safety_gate.py` — signal_strength 미참조(라벨은 주문을 직접 막지 않음)
