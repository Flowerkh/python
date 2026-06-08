"""초당 호출 제한 관리.

KIS는 초당 호출 수 제한이 있습니다(계정/환경별로 상이).
보수적으로 초당 호출 수를 제한하는 간단한 슬라이딩 윈도우입니다.
sync(acquire) 외에 async(acquire_async)도 제공 — 이벤트 루프를 블록하지 않습니다.
"""
import asyncio
import threading
import time
from collections import deque


class RateLimiter:
    def __init__(self, max_calls_per_sec: int = 2):
        # 모의투자는 한도가 낮으므로 기본 2회/초로 보수적 설정
        self.max_calls = max_calls_per_sec
        self._calls: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            # 1초보다 오래된 기록 제거
            while self._calls and now - self._calls[0] >= 1.0:
                self._calls.popleft()
            if len(self._calls) >= self.max_calls:
                sleep_for = 1.0 - (now - self._calls[0])
                if sleep_for > 0:
                    time.sleep(sleep_for)
                # 대기 후 갱신
                now = time.monotonic()
                while self._calls and now - self._calls[0] >= 1.0:
                    self._calls.popleft()
            self._calls.append(time.monotonic())

    async def acquire_async(self) -> None:
        """async 버전. time.sleep 대신 asyncio.sleep으로 이벤트 루프를 비운다."""
        while True:
            sleep_for = 0.0
            with self._lock:
                now = time.monotonic()
                while self._calls and now - self._calls[0] >= 1.0:
                    self._calls.popleft()
                if len(self._calls) < self.max_calls:
                    self._calls.append(now)
                    return
                sleep_for = 1.0 - (now - self._calls[0])
            # 락 해제 상태에서 await — 다른 코루틴이 진행 가능
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)
