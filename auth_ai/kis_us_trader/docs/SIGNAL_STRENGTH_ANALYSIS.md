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

## 로드맵

### P0 — 후속 동기화 (진행 중)
- [x] `kis/signals.py`로 임계값/분류 로직 단일화 → `daily_trader`·`tools/tune_thresholds` 공유
      (도구의 옛 AND-gate 복제본이 production과 어긋나는 드리프트 제거).
- [x] `DAILY_CHECK.md` 기대값 갱신(weak ~0% → ~30%, 시나리오 A(hold) 흔해짐).

### P1 — 결정적 검증: end-to-end 의사결정 백테스트
- [ ] 2년 walk-forward(과거 데이터로만 라벨) → 옛/새 매핑이 허가하는 행동 → **비겹침 5일 P&L**
      → 5종목 패널(고정효과 + HAC SE) + 검정력 곡선. 옛 "strong→하락추세 매도 허가"가 실제로
      지는 거래를 냈는지 달러 단위로 측정. C3의 "검정력 부족 vs 진짜 0" 모호성도 종결.

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
