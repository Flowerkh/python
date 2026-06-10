"""유니버스 종목 헬스체크 — Phase 2 반도체 라이브 전 선결 점검.

각 화이트리스트 종목에 대해 KIS 현재가(get_last_price)를 조회해
  - 시세가 도는지(거래소코드/심볼 매핑이 맞는지)
  - 모의계좌에서 paper_tradable 인지(가격>0)
를 실측하고 .state/universe_cache.json 에 24h 캐시로 박제한다(safety_gate 가 신뢰).

⚠️ 네트워크 필요 + KIS IP 화이트리스트 등록 환경(서버)에서 실행. 읽기 전용(주문 없음).
   미국 운영시간 외에는 현재가 API 가 에러일 수 있다(일봉/잔고는 휴장에도 조회됨).
   → 운영시간(한국시간 22:30~05:00 DST)에 1회 실행 권장.

실행(프로젝트 루트, 서버): python test/test_universe_health.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kis import universe
from kis.client import KISClient


def main() -> int:
    client = KISClient()
    print(f"[env] {client.settings.env}")
    if client.settings.env != "paper":
        print("⚠️ paper 환경이 아닙니다. 헬스체크는 paper 에서만 수행하세요.")
        return 2

    syms = [s.symbol for s in universe.list_all()]
    print(f"[universe] {len(syms)}종목: {syms}\n")

    tradable, not_tradable, errors = [], [], []
    for s in universe.list_all():
        sym, exch = s.symbol, s.exchange
        try:
            price = client.get_last_price(sym, exch)
            ok = price > 0
            (tradable if ok else not_tradable).append((sym, price))
            print(f"  {'[OK ]' if ok else '[ZERO]'} {sym:5s} ({exch})  last=${price}")
        except Exception as e:
            errors.append((sym, f"{type(e).__name__}: {e}"))
            print(f"  [ERR ] {sym:5s} ({exch})  {type(e).__name__}: {e}")

    # 캐시에 박제(get_last_price 재호출 = 헬스체크 후 cache write).
    print("\n[cache] refresh_tradable_cache 로 .state/universe_cache.json 갱신...")
    result = universe.refresh_tradable_cache(client)
    for sym, ok in sorted(result.items()):
        print(f"  {sym:5s} → paper_tradable={ok}")

    print("\n===== 요약 =====")
    print(f"  거래가능: {len(tradable)} {[s for s, _ in tradable]}")
    print(f"  가격0   : {len(not_tradable)} {[s for s, _ in not_tradable]}")
    print(f"  오류    : {len(errors)} {[s for s, _ in errors]}")
    if not_tradable or errors:
        print("\n⚠️ 거래불가/오류 종목은 universe.py 의 paper_tradable=False 로 내리거나,"
              "\n   운영시간 외 일시 오류면 운영시간에 재실행해 확인하세요.")
    # 헬스체크 자체는 '실측 도구'이므로 오류가 있어도 exit 0 (운영 판단은 사람이).
    return 0


if __name__ == "__main__":
    sys.exit(main())
