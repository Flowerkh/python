# 주문 타이밍 문제 (07:30 KST = 정규장 마감 후)

> 상태: 확인됨 + 실증 확정(2026-06-09) → **Rank 0 + Rank 2 구현 완료 (2026-06-10)**.
> paper 도 장외 주문 거부(`40580000 "모의투자 장종료"`). Rank 0(장 시간 가드 + phantom-fill 방지)
> 위에 **Rank 2(승인-제출 분리)** 로 실제 체결 경로 구현 — 07:30 승인 → 다음 미국 개장에 검증 TR로 제출.
> 사이클이 07:30 KST에 발화·승인하는데 그 시점 미국 정규장은 닫혀 있고, 주문 코드는
> 정규장 전용 TR만 쓴다 → 실전(prod)에서 체결 불가. + 가짜 체결(phantom-fill) 버그 동반.

---

## TL;DR
1. **07:30 KST 승인 시점엔 미국 정규장이 닫혀 있다.** 07:30 KST = **18:30 ET(여름)/17:30 ET(겨울)**,
   30분 승인창 포함 주문 발화는 07:30~08:00 KST = 18:30~19:00 ET → 전부 **애프터마켓
   (16:00~20:00 ET)** 안, 정규장(16:00 ET 마감) **이후**. 두 시간대 모두 정규장 안 열림.
2. **주문 경로는 정규장 라이브 지정가 TR만** 쓴다(`VTTT1002U/VTTT1001U`, `ORD_DVSN="00"`).
   예약주문/시간외 구분코드 없음. → 정규장 마감 후 정규주문은 **실전에서 거부/미체결**.
3. **가짜 체결 버그(별개):** `daily_trader.py:279`가 `rt_cd=="0"`만 보고 `apply_fill`.
   그런데 `rt_cd=="0"`는 **'접수'이지 '체결'이 아니다**. DESIGN §주문(line 72)은 주문 직후
   `get_balance` 재확인을 요구하나 **미구현** → 접수만 되고 미체결인 주문이 보유 포지션으로 잘못 기록.

---

## 검증된 사실 (확실)
- **시각 산술**(ET = KST−13 여름 / −14 겨울): 정규장 09:30~16:00 ET = 22:30~05:00 KST(여름)
  / 23:30~06:00 KST(겨울). 사용자 제시 숫자와 정확히 일치. 07:30 KST는 어느 시기든 post-market.
- **코드 사실**: `kis/client.py order()`는 `ORD_DVSN="00"`+`ORD_SVR_DVSN_CD="0"`, TR은 정규장용.
  grep 결과 예약주문 TR/시간외 구분코드 **전무**(audit.py의 '예약' 1건은 무관).
- **테스트가 통과한 이유 = 거짓 양성**: `test_roundtrip.py`(2026-06-04 즉시 체결)는 docstring상
  "정규장(22:30~05:00 KST DST)"에 실행하게 돼 있음. **22:30 KST = 09:30 ET = 정규장 OPEN**.
  즉 장중에 돌려서 체결된 것이지 07:30 타이밍을 검증한 게 아님. `get_last_price<=0`이면 bail 하는데
  비영(非零) 가격을 받았다는 것 자체가 장중 실행 증거. → **라이브 사이클엔 거짓 양성**.
- **왜 1주일 운영에서 안 터졌나**: LLM hold 편향 + `CONFIDENCE_THRESHOLD=80`로 대부분 사이클이
  주문 단계 전에 skip. (weak 부활 후 hold 더 잦아 더 가려짐.)

## 실증 결과 (2026-06-09 · 서버 paper 실측 → 확정)
`test/test_offhours_order.py` 로 미국 완전 마감 시각에 봇과 동일한 marketable 매수(AAPL 1주 @ +0.5%)를
실제 paper 주문 전송:
- **거부**: `rt_cd="1"`, `msg_cd="40580000"`, `msg1="모의투자 장종료 입니다."`. 포지션 변화 없음.
- → **KIS 모의(paper)도 장외 주문을 거부**한다(장외 체결 시뮬레이션 안 함). 결함은 prod 한정이 아니라
  **paper 에서도 active** — 07:30 사이클이 매매를 시도하면 매번 `장종료` 거부된다.
- 봇 경로: `client.order()` 가 `rt_cd!="0"` → `_process_symbol` else 분기(daily_trader.py:284) →
  `consecutive_errors += 1` + `cycle_error` 로그 + 텔레그램 "⚠️ 매수 실패 … 모의투자 장종료".
  → **3일 연속 strong 신호면 3회 거부 누적 → 자동 24h pause** 연쇄 위험.
- phantom-fill 은 이 경로에선 **미발동**(rt_cd≠0이라 apply_fill 안 탐). 단 장중 비-marketable 미체결
  케이스(rt_cd=0+미체결)에선 여전히 잠복 → Rank 0 안전패치 대상으로 유지.
- 1주일 운영이 무사했던 건 hold/skip 으로 **주문 단계에 도달한 적이 없어서**. test_roundtrip 즉시체결은
  정규장중(22:30 KST=09:30 ET) 수동 실행이라 라이브 사이클 검증이 아님(거짓 양성).

## KIS 미국 예약주문 = 지원 확인됨 (2026-06-10, 공식 repo 검증, HIGH)
- 공식 repo `koreainvestment/open-trading-api` 직접 검증: 접수 `/uapi/overseas-stock/v1/trading/order-resv`
  (매수 `VTTT3014U`·매도 `VTTT3016U` 모의 / `TTTT3014U`·`TTTT3016U` 실전), 취소 `/order-resv-ccnl`
  (`VTTT3017U`/`TTTT3017U`). 바디는 `FT_ORD_QTY`/`FT_ORD_UNPR3`(일반 주문과 필드명 다름). **조회(order-resv-list)는 모의 미지원.**
- 접수창 **10:00~23:20 KST**(개장에 라우팅, 마감 후 자동취소). → Rank 1 가능하나 (a) 07:30 승인이 접수창
  밖이라 어차피 리스케줄 필요, (b) 모의 조회 불가로 체결 관측성 저하 → **Rank 2 채택**(검증 TR + 잔고확인 재사용).
- (검증됨) 07:30 KST 완전마감 조건에서 paper 정규주문 거부(`40580000`). 애프터마켓 조건도 동일할 가능성 높음.

---

## 수정안 (랭크) — "마감 후 분석 + 아침 사람 승인" UX 보존 기준

> 실증으로 paper/prod 모두 장외 거부 확정 → 정규 TR 즉시주문으로는 07:30 체결 불가.
> **권장 경로: Rank 0(즉시 안전패치) → Rank 1 또는 Rank 2 중 KIS 예약주문 지원 여부로 결정.**

**Rank 0 — 안전 패치  ✅ 구현됨 (2026-06-09)**
- `daily_trader.us_regular_session_open()` 추가(ZoneInfo, DST 자동). safety_gate 통과 후 주문 전
  장 시간 가드: 정규장(09:30~16:00 ET) 밖이면 `cycle_skipped/out_of_session` + 텔레그램 "⏰ 주문 보류",
  주문 미발송 → 거부+`consecutive_errors`+auto-pause 연쇄 차단.
- **`rt_cd=="0"`만으로 체결 처리 금지**: 주문 직후 `_broker_held_qty()`로 잔고 재조회해 실제 수량
  증가/감소를 확인한 뒤에만 `apply_fill`. 미확인 시 `cycle_accepted_unfilled` + "🟡 체결 미확인" 알림
  (가짜 포지션 안 만듦). DESIGN line 72 요구사항 구현.
- 단독으론 체결을 만들지 못함 → 실제 매매하려면 Rank 1/2/3 중 하나 필요(현재 보류).

**Rank 1 — KIS 미국 예약주문(reserved/pre-open)** *(지원 확인됨, 향후 옵션)*
- 승인된 주문을 예약주문으로 접수 → 브로커가 다음 정규장 open에 라우팅, 마감 후 자동취소(stale 관리 불필요).
- TR/엔드포인트 확보(위 섹션). 단 (a) 07:30이 접수창(10:00~) 밖, (b) 모의 조회 불가 → Rank 2 대비 이점
  작아 **보류**. 추후 접수창/DST 실측 + 관측성 확보 후 전환 고려.

**Rank 2 — 승인/제출 분리  ✅ 구현됨 (2026-06-10)**
- 07:30 승인된 pick을 `state.pending_orders`에 저장(`order_queued`) → `submission_loop`가 미국 개장 직후
  (09:35 ET ≈ 22:35 KST, DST 자동)에 **검증된 정규 TR**로 제출. 제출 직전 보유/safety_gate 재검증 + 잔고
  재조회 체결 확인(phantom-fill 방지). **18h TTL**로 주말/장애 stale 승인 자동 만료.
- 구현: `daily_trader`(`submission_loop`/`submit_open_orders`/`_submit_one`/`_place_and_confirm`/
  `seconds_until_submit_window`), `kis/state.py`(`pending_orders`). **재가격 안 함** — 사람이 승인한 지정가를
  그대로 제출(갭으로 미체결 시 `🟡 체결 미확인`). main_loop(07:30)과 submission_loop를 asyncio.gather로 동시 실행.

**Rank 3 — 트리거를 정규장 안으로 이동**
- 22:35 KST(DST)/23:35 KST(표준) 발화, 전일 확정 일봉 분석, 장중 즉시 정규주문. 코드 변경 최소.
- ⚠️ **아침 07:30 승인 UX 깨짐**(승인이 심야로). DST 인지 스케줄 필요. 모닝승인 요건 완화 가능할 때만.

---

## 결정적 실증 테스트 (지금 = 한국 낮 = 미국 완전 마감, 적기)
`KIS_ENV=paper`에서 실제 `client.order()` 경로로 **소액 1주 지정가**(체결 안 될 만큼 먼 가격) 주문 후
즉시 `get_balance`/`get_orders` 확인. **raw `rt_cd`·`msg1`/`msg_cd`** 와 포지션 생성 여부를 보면:
1. paper가 **장외 체결**하는지(포지션 생김) vs ACK만 vs 거부, 그리고
2. **마감장 주문이 반환하는 정확한 코드**(예: "장 운영시간 외") → prod 거동 예측 + Rank 0 가드 코드 확보.

→ 유일하게 불확실한 변수(paper 장외 체결 정책)를 한 번에 해소.

---

## 관련 파일
- `kis/client.py` — `order()` (TR/ORD_DVSN), `_notify_order`
- `kis/config.py` — `TR_BUY/TR_SELL`(정규장 전용)
- `daily_trader.py` — `RUN_HOUR/RUN_MINUTE=07:30`(49–50), `apply_fill` on `rt_cd=="0"`(279), `APPROVAL_TIMEOUT=1800`
- `docs/DESIGN.md` — §1(07:30 발화), §8(정규장만 거래), line 72(get_balance 재확인 요구)
