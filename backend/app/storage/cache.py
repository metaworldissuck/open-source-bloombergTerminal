from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass
class _CacheEntry:
    value: Any
    expires_at: float


class TTLCache:
    """Lightweight L1 in-memory TTL cache for hot quotes and resolved metadata."""

    def __init__(self, max_items: int = 4096):
        self._store: dict[str, _CacheEntry] = {}
        self._max_items = max_items

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.monotonic() > entry.expires_at:
            self._store.pop(key, None)
            return None
        return entry.value

    def set(self, key: str, value: Any, ttl_sec: float = 30.0) -> None:
        if len(self._store) >= self._max_items:
            now = time.monotonic()
            expired = [k for k, v in self._store.items() if now > v.expires_at]
            for k in expired:
                self._store.pop(k, None)
            if len(self._store) >= self._max_items:
                # Evict oldest inserted key
                self._store.pop(next(iter(self._store)), None)
        self._store[key] = _CacheEntry(value=value, expires_at=time.monotonic() + ttl_sec)

    def invalidate(self, prefix: str | None = None) -> None:
        if prefix is None:
            self._store.clear()
        else:
            for k in [k for k in self._store if k.startswith(prefix)]:
                self._store.pop(k, None)


hot_cache = TTLCache()
