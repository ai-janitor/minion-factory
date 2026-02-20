from __future__ import annotations

from collections import deque


class RollingBuffer:
    def __init__(self, max_tokens: int) -> None:
        self.max_chars = max_tokens * 4
        self._chunks: deque[str] = deque()
        self._total_chars = 0

    def append(self, text: str) -> None:
        if not text:
            return
        self._chunks.append(text)
        self._total_chars += len(text)
        while self._total_chars > self.max_chars and self._chunks:
            removed = self._chunks.popleft()
            self._total_chars -= len(removed)

    def snapshot(self) -> str:
        return "".join(self._chunks)

    def __len__(self) -> int:
        return self._total_chars
