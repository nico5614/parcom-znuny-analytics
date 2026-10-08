"""Thread-safe aggregate timings; never retain URLs, arguments or payloads."""

from contextlib import contextmanager
from threading import Lock
from time import perf_counter


class Timings:
    def __init__(self):
        self._lock = Lock()
        self._values = {}

    @contextmanager
    def measure(self, operation):
        started, failed = perf_counter(), False
        try:
            yield
        except BaseException:
            failed = True
            raise
        finally:
            with self._lock:
                item = self._values.setdefault(operation, {"count": 0, "seconds": 0.0, "failures": 0})
                item["count"] += 1
                item["seconds"] += perf_counter() - started
                item["failures"] += int(failed)

    def snapshot(self):
        with self._lock:
            return {name: {**item, "average_seconds": item["seconds"]/item["count"]}
                    for name, item in self._values.items()}
