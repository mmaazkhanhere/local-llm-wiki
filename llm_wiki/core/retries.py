from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Callable, TypeVar

from llm_wiki.core.errors import TransientError


T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    base_delays_seconds: tuple[float, ...]
    jitter_seconds: float = 0.0


PROVIDER_RETRY_POLICY = RetryPolicy(
    max_attempts=3,
    base_delays_seconds=(1.0, 2.0, 4.0),
    jitter_seconds=0.15,
)

FILE_IO_RETRY_POLICY = RetryPolicy(
    max_attempts=3,
    base_delays_seconds=(0.5, 1.0),
    jitter_seconds=0.0,
)

LOG_RETRY_POLICY = RetryPolicy(
    max_attempts=3,
    base_delays_seconds=(0.2, 0.5),
    jitter_seconds=0.0,
)


def with_retry(operation: Callable[[], T], policy: RetryPolicy) -> T:
    attempt = 0
    while True:
        attempt += 1
        try:
            return operation()
        except TransientError:
            if attempt >= policy.max_attempts:
                raise
            delay = _delay_for_attempt(policy, attempt)
            if delay > 0:
                time.sleep(delay)


def _delay_for_attempt(policy: RetryPolicy, attempt: int) -> float:
    index = min(attempt - 1, len(policy.base_delays_seconds) - 1)
    delay = policy.base_delays_seconds[index]
    if policy.jitter_seconds > 0:
        delay += random.uniform(0.0, policy.jitter_seconds)
    return delay
