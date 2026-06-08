"""KIS 잔고 API 응답 캡처 + parse_balance_positions 검증.

목적:
  1) 실제 KIS paper inquire-balance API가 어떤 필드를 반환하는지 캡처(처음 1회)
  2) parse_balance_positions 헬퍼가 빈 응답/이상 응답에서도 빈 dict로 닫히는지(fail-closed) 확인

실행(프로젝트 루트): python test/test_balance_parse.py

미국장 운영시간이 아니어도 잔고 API는 동작합니다(현재가/주문과 달리).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kis.client import KISClient, parse_balance_positions


def _check(label: str, expected: dict, actual) -> bool:
    ok = actual == expected and isinstance(actual, dict)
    mark = "OK " if ok else "FAIL"
    print(f"  [{mark}] {label}: expected={expected!r} actual={actual!r}")
    return ok


def main() -> int:
    client = KISClient()
    env = client.settings.env
    print(f"환경: {env}")
    if env != "paper":
        print("❌ KIS_ENV가 paper가 아닙니다. 안전을 위해 중단.")
        return 2

    # Part 1: 실제 잔고 API 호출 — 응답 모양 캡처
    print("\n=== Part 1: live get_balance() 응답 캡처 ===")
    try:
        resp = client.get_balance()
    except Exception as e:
        print(f"❌ get_balance 예외: {type(e).__name__}: {e}")
        return 1

    print(json.dumps(resp, ensure_ascii=False, indent=2))
    rt = resp.get("rt_cd")
    if rt != "0":
        print(f"⚠️ rt_cd={rt}, msg={resp.get('msg1')} — 응답 모양만 참고하고 다음 검증으로 진행.")

    parsed = parse_balance_positions(resp)
    print("\n--- parse_balance_positions 결과 ---")
    print(json.dumps(parsed, ensure_ascii=False, indent=2))

    if parsed:
        # 각 항목 스키마 검증
        for sym, pos in parsed.items():
            assert isinstance(sym, str) and sym, f"symbol 비정상: {sym!r}"
            for k in ("qty", "avg_price", "eval_usd"):
                assert k in pos, f"{sym}: {k} 누락"
            assert isinstance(pos["qty"], int) and pos["qty"] > 0, f"{sym}: qty {pos['qty']}"
            assert isinstance(pos["avg_price"], float), f"{sym}: avg_price 타입"
            assert isinstance(pos["eval_usd"], float), f"{sym}: eval_usd 타입"
        print(f"✅ 보유 종목 {len(parsed)}개의 스키마 정상")
    else:
        print("ℹ️ 현재 보유 종목 없음(또는 빈 응답). Part 2의 fail-closed 검증으로 진행.")

    # Part 2: 빈/이상 응답 fail-closed
    print("\n=== Part 2: parse_balance_positions fail-closed ===")
    all_ok = True
    cases = [
        ("None", None),
        ("빈 dict", {}),
        ("output1 누락", {"rt_cd": "0"}),
        ("output1 None", {"output1": None}),
        ("output1 빈 list", {"output1": []}),
        ("output1 list of None", {"output1": [None]}),
        ("ovrs_pdno 누락", {"output1": [{"ovrs_cblc_qty": "1"}]}),
        ("qty=0", {"output1": [{"ovrs_pdno": "AAPL", "ovrs_cblc_qty": "0", "pchs_avg_pric": "200"}]}),
        ("qty 이상문자열", {"output1": [{"ovrs_pdno": "AAPL", "ovrs_cblc_qty": "abc"}]}),
    ]
    for label, payload in cases:
        actual = parse_balance_positions(payload)
        all_ok &= _check(label, {}, actual)

    # Part 3: 정상 응답 1건
    print("\n=== Part 3: 정상 형태 응답 파싱 ===")
    sample = {
        "output1": [
            {
                "ovrs_pdno": "AAPL",
                "ovrs_cblc_qty": "3",
                "pchs_avg_pric": "201.50",
                "ovrs_stck_evlu_amt": "619.50",
            },
            {
                "ovrs_pdno": "NVDA",
                "ovrs_cblc_qty": "2",
                "pchs_avg_pric": "150.00",
                "ovrs_stck_evlu_amt": "320.00",
            },
        ]
    }
    actual = parse_balance_positions(sample)
    expected = {
        "AAPL": {"qty": 3, "avg_price": 201.50, "eval_usd": 619.50},
        "NVDA": {"qty": 2, "avg_price": 150.00, "eval_usd": 320.00},
    }
    if actual == expected:
        print("  [OK ] 정상 응답 파싱")
    else:
        print(f"  [FAIL] 정상 응답 파싱: expected={expected!r}\n         actual  ={actual!r}")
        all_ok = False

    print("\n" + ("✅ 모든 검증 통과" if all_ok else "❌ 일부 실패"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
