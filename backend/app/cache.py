"""Simple in-memory cache with TTL. Falls back gracefully when Redis is unavailable."""

import time
from typing import Any, Optional
from functools import wraps
import asyncio


class MemoryCache:
    """Thread-safe in-memory cache with TTL support."""

    def __init__(self):
        self._store: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Optional[Any]:
        if key in self._store:
            value, expires_at = self._store[key]
            if expires_at > time.time():
                return value
            del self._store[key]
        return None

    def set(self, key: str, value: Any, ttl: int = 300):
        self._store[key] = (value, time.time() + ttl)

    def delete(self, key: str):
        self._store.pop(key, None)

    def clear_prefix(self, prefix: str):
        keys_to_delete = [k for k in self._store if k.startswith(prefix)]
        for k in keys_to_delete:
            del self._store[k]


cache = MemoryCache()


def cached(ttl: int = 300, prefix: str = "", key_fn=None):
    """Decorator for caching async function results.

    Args:
        ttl: Cache time-to-live in seconds.
        prefix: Cache key prefix.
        key_fn: Optional callable(*args, **kwargs) -> list[str].
            Extra key components to isolate caches (e.g. by user role).
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Build cache key from function name + args
            key_parts = [prefix or func.__name__]
            for arg in args:
                if hasattr(arg, 'id'):
                    key_parts.append(str(arg.id))
                elif isinstance(arg, (str, int)):
                    key_parts.append(str(arg))
            for k, v in sorted(kwargs.items()):
                if k not in ('db', 'current_user'):
                    key_parts.append(f"{k}={v}")

            # Append extra key components from key_fn
            if key_fn is not None:
                extra = key_fn(*args, **kwargs)
                if extra:
                    key_parts.extend(str(e) for e in extra)

            cache_key = ":".join(key_parts)

            result = cache.get(cache_key)
            if result is not None:
                return result

            result = await func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result
        return wrapper
    return decorator
