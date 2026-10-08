from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from threading import Lock
from time import perf_counter


class Metrics:
    """Process-local metrics abstraction; deliberately no monitoring platform dependency."""

    def __init__(self) -> None:
        self._counters: defaultdict[tuple[str, tuple[tuple[str, str], ...]], int] = defaultdict(int)
        self._observations: defaultdict[tuple[str, tuple[tuple[str, str], ...]], list[float]] = defaultdict(list)
        self._lock = Lock()

    def increment(self, name: str, value: int = 1, **labels: str | int | bool) -> None:
        key = (name, tuple(sorted((key, str(value)) for key, value in labels.items())))
        with self._lock:
            self._counters[key] += value

    def observe(self, name: str, value: float, **labels: str | int | bool) -> None:
        key = (name, tuple(sorted((key, str(value)) for key, value in labels.items())))
        with self._lock:
            self._observations[key].append(value)

    @contextmanager
    def timing(self, name: str, **labels: str | int | bool) -> Iterator[None]:
        started = perf_counter()
        try:
            yield
        finally:
            self.observe(name, (perf_counter() - started) * 1000, **labels)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "counters": {name: count for (name, _), count in self._counters.items()},
                "observations": {name: list(values) for (name, _), values in self._observations.items()},
            }


metrics = Metrics()
