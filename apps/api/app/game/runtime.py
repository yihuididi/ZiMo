"""Platform-neutral clock and randomness ports with deterministic fixtures."""

from __future__ import annotations

import random
import secrets
import time
from dataclasses import dataclass, field
from typing import Protocol, TypeVar


T = TypeVar("T")


class Clock(Protocol):
    def now_ms(self) -> int:
        """Return Unix time in whole milliseconds."""


class RandomSource(Protocol):
    def randbelow(self, upper_bound: int) -> int:
        """Return an integer in ``[0, upper_bound)``."""

    def shuffled(self, values: tuple[T, ...]) -> tuple[T, ...]:
        """Return a shuffled copy without mutating the caller's values."""


class SystemClock:
    def now_ms(self) -> int:
        return time.time_ns() // 1_000_000


@dataclass(frozen=True, slots=True)
class FixedClock:
    timestamp_ms: int

    def __post_init__(self) -> None:
        if self.timestamp_ms < 0:
            raise ValueError("timestamp_ms cannot be negative")

    def now_ms(self) -> int:
        return self.timestamp_ms


class SystemRandomSource:
    """Cryptographically strong runtime randomness."""

    def __init__(self) -> None:
        self._random = secrets.SystemRandom()

    def randbelow(self, upper_bound: int) -> int:
        if upper_bound <= 0:
            raise ValueError("upper_bound must be positive")
        return self._random.randrange(upper_bound)

    def shuffled(self, values: tuple[T, ...]) -> tuple[T, ...]:
        copy = list(values)
        self._random.shuffle(copy)
        return tuple(copy)


@dataclass(slots=True)
class DeterministicRandomSource:
    """Seeded deterministic RNG intended for tests and replay fixtures only."""

    seed: int | str | bytes
    _random: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._random = random.Random(self.seed)

    def randbelow(self, upper_bound: int) -> int:
        if upper_bound <= 0:
            raise ValueError("upper_bound must be positive")
        return self._random.randrange(upper_bound)

    def shuffled(self, values: tuple[T, ...]) -> tuple[T, ...]:
        copy = list(values)
        self._random.shuffle(copy)
        return tuple(copy)
