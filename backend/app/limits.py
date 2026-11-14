"""Request limits for a public demo (kept in memory, so they apply per server process).

Settings come from environment variables; 0 means "no limit", which is the default for local use:
    RATE_LIMIT_ANALYZE_PER_HOUR   questions one visitor may ask per hour
    RATE_LIMIT_UPLOAD_PER_HOUR    files one visitor may upload per hour
    GLOBAL_ANALYZE_PER_DAY        questions allowed across ALL visitors per day (protects your AI quota)
    TRUST_PROXY                   1 when running behind a hosting proxy, so the visitor's address is read
                                  from the X-Forwarded-For header
"""
from __future__ import annotations
import math
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass

HOUR = 3600
DAY = 86400


def _int(name: str) -> int:
    try:
        return max(0, int(os.getenv(name, "0")))
    except ValueError:
        return 0


@dataclass
class Limits:
    analyze_per_hour: int = 0
    upload_per_hour: int = 0
    analyze_per_day_total: int = 0
    trust_proxy: bool = False

    @classmethod
    def from_env(cls) -> "Limits":
        return cls(
            analyze_per_hour=_int("RATE_LIMIT_ANALYZE_PER_HOUR"),
            upload_per_hour=_int("RATE_LIMIT_UPLOAD_PER_HOUR"),
            analyze_per_day_total=_int("GLOBAL_ANALYZE_PER_DAY"),
            trust_proxy=os.getenv("TRUST_PROXY", "").lower() in ("1", "true", "yes"),
        )


def visitor_address(request, trust_proxy: bool) -> str:
    """The visitor's IP. Behind a proxy it is the first X-Forwarded-For entry. A determined visitor could
    fake that header, which is why the daily total above exists as a backstop for the AI key."""
    if trust_proxy:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimiter:
    def __init__(self, limits: Limits, clock=time.monotonic):
        self.limits = limits
        self.clock = clock
        self._per_visitor: dict[tuple[str, str], deque] = defaultdict(deque)
        self._all_analyses: deque = deque()

    @staticmethod
    def _prune(q: deque, now: float, window: int) -> None:
        while q and now - q[0] >= window:
            q.popleft()

    def check(self, kind: str, visitor: str) -> tuple[bool, int, str]:
        """Record one request if allowed. Returns (allowed, seconds_to_wait, reason)."""
        now = self.clock()
        limit = self.limits.analyze_per_hour if kind == "analyze" else self.limits.upload_per_hour
        key = (kind, visitor)
        mine = self._per_visitor[key]
        self._prune(mine, now, HOUR)

        if limit and len(mine) >= limit:
            wait = math.ceil(HOUR - (now - mine[0]))
            what = "questions" if kind == "analyze" else "uploads"
            return False, wait, f"You have reached the limit of {limit} {what} per hour. Please try again in about {max(1, wait // 60)} minutes."

        if kind == "analyze" and self.limits.analyze_per_day_total:
            self._prune(self._all_analyses, now, DAY)
            if len(self._all_analyses) >= self.limits.analyze_per_day_total:
                wait = math.ceil(DAY - (now - self._all_analyses[0]))
                return False, wait, "This demo has reached its daily question limit. Please try again tomorrow."

        mine.append(now)
        if kind == "analyze":
            self._all_analyses.append(now)
        if not mine:                      # keep memory small
            self._per_visitor.pop(key, None)
        return True, 0, ""
