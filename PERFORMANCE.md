# Backend performance validation

Base: `5e993d0` (`codex/version-1-0`). Work branch: `codex/performance`.

## Reproducible baseline

Run `.\.venv314\Scripts\python.exe tests/performance_benchmark.py` from the root.
The harness injects 20 ms latency per REST call over 40 synthetic tickets. It never
connects to Znuny. Fixtures exist only in tests and are not application data.
It measures request counts, summed request durations, average request durations,
peak concurrency, normalization/load, analytics and time to usable dashboard data.
Summed request durations differ from wall time once requests overlap.

Before behavior changes: 8 searches (0.163 s), 40 TicketGet (0.816 s total,
0.0204 s average), 40 histories (0.821 s total), analytics 0.069 s,
usable dashboard 1.923 s. Maximum concurrency: 1. An unchanged refresh repeats
all 88 requests. HTTP already uses a reusable `requests.Session`, but ticket and
history retrieval are serial and history is loaded unconditionally.

Baseline suite: 213 passed (46.64 s), Python 3.14 environment. Use a local pytest
temporary directory because the machine's default pytest temp directory is not
accessible:

```powershell
.\.venv314\Scripts\python.exe -m pytest -q -o cache_dir=.validation/cache --basetemp .validation/perf-tests
```

These are controlled offline measurements, not live server measurements. No live
credentials were supplied or extracted. Live TLS reuse and representative server
latency/load must still be checked with a personal sign-in in the application.
