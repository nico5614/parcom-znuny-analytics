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
New-Item -ItemType Directory -Path .validation -Force | Out-Null
.\.venv314\Scripts\python.exe -m pytest -q -o cache_dir=.validation/cache --basetemp .validation/perf-tests
```

These are controlled offline measurements, not live server measurements. No live
credentials were supplied or extracted. Live TLS reuse and representative server
latency/load must still be checked with a personal sign-in in the application.

## Final verification (8 October 2026)

Branch: `codex/performance`. Implementation commit:
`bbcb18b254d41cc87e28dd7709805082750bb9bf`; the subsequent documentation/benchmark
commit is the final branch HEAD. No merge to `main` or `codex/integration`.

Full Python suite: **248 passed in 34.92 s**. Focused REST, performance, incremental,
agent, connection and live UI tests: **72 passed in 10.33 s**. All original tests
remain; the route mock now supports nondeterministic HTTP completion while still
checking deterministic returned ticket order.

The immutable base can also be measured after optimization:

```powershell
.\.venv314\Scripts\python.exe tests/performance_benchmark.py --baseline --output .validation/performance-before-final.json
.\.venv314\Scripts\python.exe tests/performance_benchmark.py --output .validation/performance-after-final.json
```

`--baseline` loads the original client and loader directly from Git commit
`5e993d0`, without checking out or modifying that branch. The after run additionally
measures first history demand and cached history demand. Output contains only
synthetic aggregate metrics, timings and counts. JSON uses UTF-8 explicitly.

Final measured runs (40 synthetic tickets, nominal 20 ms REST latency):

| Operation | Before Search / Get / History | After Search / Get / History | Before usable | After usable | After peak concurrency |
| --- | --- | --- | --- | --- | --- |
| Initial dashboard | 8 / 40 / 40 | 7 / 40 / 0 | 1.870 s | 0.469 s | 4 |
| Unchanged refresh | 8 / 40 / 40 | 8 / 0 / 0 | 1.853 s | 0.207 s | 1 |
| Four changed tickets | 8 / 40 / 40 | 8 / 4 / 0 | 1.856 s | 0.230 s | 4 |

The initial dashboard is approximately four times faster in this controlled run.
An unchanged refresh uses 91% fewer requests. Metrics, chart values and row counts
for every KPI match the original loader in all three scenarios.

| Initial-load component | Before | After |
| --- | --- | --- |
| Search, summed request time | 0.163 s | 0.202 s |
| TicketGet, summed request time | 0.817 s | 0.817 s |
| Average TicketGet time | 0.0204 s | 0.0204 s |
| History, summed request time | 0.817 s | 0 s |
| Load and normalization wall time | 1.831 s | 0.414 s |
| Analytics wall time | 0.039 s | 0.055 s |

Sleep/scheduling and processor load cause some variation between runs; summed
overlapping request times are not wall-clock wait time. The benchmark excludes
real TLS setup, disk persistence and UI rendering, and makes no claim about live
Znuny speed or server load.

On-demand history after the dashboard is available:

| Case | Search / Get / History | Measured time | Peak concurrency |
| --- | --- | --- | --- |
| First demand | 1 / 0 / 40 | 0.231 s | 4 |
| After unchanged refresh | 1 / 0 / 0 | 0.029 s | 1 |
| After four changes | 1 / 0 / 4 | 0.047 s | 4 |

## Implementation and integration contract

- `znuny.py`: exclusive leasing of persistent HTTP sessions, a shared four-slot
  limit across consumers and operations, bounded scheduling, deterministic ticket
  order, in-flight deduplication and history version caching. Each default slot
  owns one reusable session/connection pool, preventing concurrent mutation of
  `requests.Session` cookies. An explicitly injected real Session is leased through
  one slot. TLS verification, native truststore and the existing read-only route
  whitelist remain enforced. Default and maximum concurrency are **4**; 6 is not
  enabled without a live server measurement.
- `live_data.py`: the active `TimeRange` dashboard pipeline stages raw allowlisted
  ticket fields in memory. First load performs seven filtered searches. Subsequent
  refreshes perform those membership searches plus a delta search using
  `TicketLastChangeTimeNewerDate`, fetching only changed or missing selected IDs.
  Membership searches detect queue removals and rolling-period changes; escalation
  membership and relative age/pending timers may change with time without a new
  ticket `Changed` value, so they are not skipped. The watermark uses the successful
  load's start time with a one-second overlap, protecting changes during loading.
- `live_cache.py` and `connection.py`: prepare analyses and reports before atomic
  file replacement, check cancellation before replacement, then publish the memory
  cache/watermark. Search, ticket, analytics and disk failures leave the last
  successful snapshot and sync watermark intact. Session generations reject late
  results from a previous account. Login/logout/explicit clear discard memory
  caches; the existing offline snapshot remains available immediately.
- History is requested through `ConnectionController.load_history()` or the lower
  level `load_history(client, batch, cancel)`. The native Agenten view requests it
  on entry. Startup does not request all histories or the broad agent-only changed
  ticket selection. **Exception:** a missing pending timer still uses that ticket's
  history to preserve the existing verified timer fallback. This is a selective
  dashboard dependency, not an unconditional history scan.
- History cache keys include the ticket's `Changed` version and an invalidation
  revision. Delta hits invalidate history conservatively even if the change
  timestamp is the same second. Invalidated in-flight responses cannot repopulate
  the cache. Without a usable `Changed` value, completed history is not reused.
  Cached histories remain in memory only. Existing close-event/first-response
  attribution and SYSTEM exclusion are unchanged; no owner-based inference was
  added.
- `performance.py`: `client.timings.snapshot()` returns operation count, total,
  average and failure count. Native workers also measure `DashboardLoad`,
  `AnalyticsAndCache` and `UsableData`. Only operation names and numeric aggregates
  are retained; no URLs, request arguments, credentials, session IDs or payloads.
- `ui.py`, `agents_ui.py`, `service_desk_ui.py`: only the explicitly authorized
  demand-loading connection and unavailable-history messages were added. No React,
  WebView, layout or visual redesign. Until `batch.history_loaded` is true, consumers
  must show history-derived metrics as unavailable rather than inventing zeros.

For another UI integration, use the existing controller or keep the transaction
order: hold `client._refresh_lock`, call `fetch_live(..., commit=False)`, successfully
prepare/persist through `LiveCache.update`, then `commit_live`. Direct low-level
`fetch_live` defaults to committing its successfully fetched data. Demand-load
history on the background worker, publish the returned new batch, and preserve
the `history_loaded` flag on disk. Clearing the disk cache must also call
`client.clear_cache()`. The legacy `DateRange` loader remains compatible and uses
bounded TicketGet, but its original full-refresh path is unchanged; incremental
refresh is implemented for the current application's `TimeRange` path.

## Limits and remaining live checks

No live credentials were provided and no personal Znuny sign-in was performed.
Consequently there is no real before/after baseline, live connection-reuse trace,
production throughput figure or justification for six concurrent requests.
Verify a representative PBX/PBX Intern load, pending timers, agent attribution and
server load with the real account before production release. REST supplies no
transactional snapshot; tickets can change during a read and the next overlapping
delta refresh reconciles them. Cancellation prevents new work/publication but
already-running HTTP calls finish or hit their existing timeout before shutdown.

One full test run encountered the native Qt access violation already described
in `VALIDATION.md`. Synchronous test workers now have explicit GUI ownership and
disposal. The subsequent full runs passed (247 and finally 248 tests); this does
not replace a native application smoke test with a real connection.

Commits in this branch's performance work: baseline `ecd45b4`, bounded transport
and deduplication `2e73b32`, transactional cache/history `bbcb18b`, followed by the
final measurement and handoff documentation commit. Significant added tests are
`test_performance.py` and `test_incremental.py`; the synthetic benchmark is confined
to `tests/performance_benchmark.py` and is not an application fixture or build asset.
