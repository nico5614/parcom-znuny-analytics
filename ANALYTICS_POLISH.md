# Analytics polish handoff

Branch: `codex/analytics-polish`, based exactly on integration
`118fb47280dacf93f98eb67713338bf451ae0c0d`. No merge is authorized.

## Phase 1 — interval comparisons and snapshot semantics

- Selected rolling/custom bounds stay exact. The previous flow interval ends at
  the selected start and has the same elapsed duration, including across DST.
- Numeric comparison data includes `value`, `previous`, signed `delta`,
  `deltaPercent` (null for a zero baseline), semantic `trend`, `metricType`,
  `contextLabel`, and `deltaAvailable`. The accepted UI's string `value` stays
  compatible; cards add `numericValue`. DTO `comparisons` carry numeric values.
- New tickets: fewer is better. Closed tickets/closure rate: more is better.
  Durations, escalations, waiting/backlog: fewer is better. No change or unavailable
  comparison is neutral; use availability flags to distinguish those cases.
- Snapshots refer to the selected end, classified once at load time. Rolling/current
  endpoints say `Stand jetzt`; historical endpoints say `Stand am DD.MM.YYYY HH:MM`.
  Cached replay preserves the endpoint instead of reclassifying it against today.
- Historical values require an exact observed snapshot. The allowed REST searches
  return today's stock, not a historical state. Missing historic endpoints therefore
  produce null numeric values / `–`, never today's stock under a historical label.
  Start-to-end stock deltas require an exact saved start observation. No extra
  searches/history requests are performed. Saved snapshots contain aggregates,
  so historical ticket details and type-specific stock are unavailable.
- Service durations retain median as primary and arithmetic mean as secondary;
  zero minutes count, missing/negative/nonfinite values do not. Time deltas are
  signed numeric minutes, with no HTML.

Validation: 55 focused Python tests passed (comparisons plus existing WebView,
agent/export, live semantics and cache contracts). Phase 2 continues with selected
interval score behavior; phase 3 adds agent discovery, winner and persistent overrides.

## Phase 2 — selected interval score

`LiveCache.selected_performance()` supplies the WebView's selected interval score.
The existing formula (`service_desk.score_period`) is called unchanged: each raw
component is 100 when current <= previous, otherwise `100 * previous / current`.
The seven components form five equally weighted areas (Backlog, Escalations,
Response, Solution, Waiting); the two-component areas average their components.
The final five-area average is rounded to one decimal. New/closed ticket counts
remain context without score weight. This is a relative trend index, not an SLA
or absolute quality rating.

Current service durations use selected flow data; previous durations use the
immediately preceding equal interval. Stock components use end/start observations.
A score is unavailable if any required input is missing/invalid; components are
never dropped or reweighted. A previous score additionally requires the preceding
interval's flow aggregates and its earlier endpoint snapshot. The DTO includes
selected/comparison bounds, current/previous score, signed delta, trend, components
and areas. Aggregate interval inputs persist transactionally without ticket details.
Legacy monthly Excel scoring and its export report remain compatible.

Validation: 76 focused Python tests passed, including unchanged score weighting,
current/previous interval scores, restart persistence, zeros and invalid values.
Continue with human-agent discovery, ranking, abbreviations and local overrides.

## Phase 3 — agent analytics and persistent local overrides

- Discovery uses observed PBX/PBX Intern owners and history actors plus previously
  saved PBX observations. Seed/identity mappings provide names, not membership;
  unrelated users and SYSTEM do not enter the human registry. Unknown login-only
  identities retain an explicit unknown abbreviation instead of an invented name.
- Ranking/winner use actual history-derived `ClosedByID`, never Owner. Rankings
  are global among observed humans, independent of the team filter. All positive
  ties are winners (`periodWinners`); `periodWinner` is present only for a unique
  winner. No closes or unloaded history yield no winner. The overview does not
  trigger history loading merely to produce a winner.
- Agent rows add `displayName`, `abbreviation`, `rank`, `isPeriodWinner`,
  `medianResponseMinutes`, `meanResponseMinutes`, `responseComparison` and
  `meanResponseComparison` for the previous equal interval. Median remains primary.
- Known manual seed codes stay authoritative, including Lewin Roos = LRO.
  Otherwise automatic codes use first initial + first two surname letters after
  diacritic transliteration. Local manual overrides take priority.
- Bridge methods: `getAgentOverride`, `setAgentDisplayName`,
  `setAgentAbbreviation`, `resetAgentOverride`. Accept a discovered AgentID or a
  uniquely mapped login; persist `name`/`code` under the stable ID in local
  `settings.ini`. Reset removes local overrides and restores known/automatic values.
  No Znuny user writes or credentials are stored. Overrides survive restart and
  are never baked back into the base discovery registry.

Validation: 74 focused Python tests passed, including human/SYSTEM attribution,
global ranking/ties, discovery scope, Unicode abbreviations, override persistence
and the existing incremental/lazy-history suite. Continue with final cross-contract
review, full Python suite and performance request-count verification.

## Phase 4 — shared report and endpoint validation

- Live `TimeRange` reports and PDF score output now use the same selected interval
  score as the DTO. Legacy `DateRange`/Excel month scores keep their original path.
  Stored endpoint aggregates also replace today's stock in historical reports;
  missing endpoints remain unavailable in report metrics and charts.
- Selected flow endpoints are inclusive. The preceding interval excludes its
  shared end/start boundary so a boundary event is counted only in the selected
  interval. REST upper search bounds include one extra second, with exact local
  filtering; chart buckets and history attribution use the same rule.
- Rankings count unique TicketIDs. Duplicate activity rows cannot inflate closes
  or first responses. Open and waiting old-stock values have separate DTO names.
- A supported previous score in the same calendar month cannot masquerade as an
  unavailable current score. Score history labels and PDFs show actual intervals.

Validation: 141 Python tests passed across new analytics/agent cases, live cache,
snapshot semantics, shared reports, original score tests and WebView/PDF exports.
Remaining: final performance/compatibility review, complete Python suite, clean
branch/remote verification. No React layout or packaging changes were made.

## Phase 5 — final verification and handoff

Complete Python suite: **324 passed in 86.27 seconds**. Command, from this checkout:

```powershell
& 'C:\Users\nicokoechli\Documents\ChatGPT\PARCOM\.venv314\Scripts\python.exe' -m pytest -q -o cache_dir=.validation/cache --basetemp .validation/full-final-324
```

Final compatibility fixes keep numeric compatibility counts for legacy Qt sorting
while WebView DTOs explicitly mask unloaded history with null / `–`, no winner,
and availability flags. Legacy DateRange caches remain readable offline. Comparison
and score code reuse prepared cached analyses; discovery reads only distinct
identity columns rather than copying all ticket fields repeatedly.

Synthetic performance comparison against the exact integration commit
`118fb47280dacf93f98eb67713338bf451ae0c0d` (40 tickets, 20 ms/request) confirms
identical request counts, rows, existing KPI metrics and charts:

| Operation | TicketSearch | TicketGet | TicketHistory | Peak concurrent requests |
| --- | ---: | ---: | ---: | ---: |
| Initial load | 7 | 40 | 0 | 4 |
| Unchanged refresh | 8 | 0 | 0 | 1 |
| Refresh, 4 changed tickets | 8 | 4 | 0 | 4 |
| First history demand | 1 | 0 | 40 | 4 |
| History after unchanged refresh | 1 | 0 | 0 | 1 |
| History after 4 changed tickets | 1 | 0 | 4 | 4 |

Existing persistence, HTTP connection reuse, request deduplication, ticket/delta
cache and lazy/versioned history cache are retained. Comparisons and winner DTOs
do not initiate network calls. The original missing-pending-timer history fallback
is retained. Timing files are local ignored validation artifacts; these are not
measurements of the real Znuny server.

Final integration notes / limitations:

- The DTO deliberately retains formatted card `value` strings; consume
  `numericValue` or numeric `comparisons` for arithmetic. Trends come from Python.
- Snapshot context is classified at load time. Offline replay retains that
  recorded endpoint and classification; `capturedAt` still identifies cache age.
- The REST routes provide current stock. Without an exact saved historical
  endpoint, historical stock is unavailable, never inferred from current tickets.
  Without an exact start snapshot, stock deltas and the unchanged full-formula
  score are unavailable. A previous score needs the earlier interval as well.
- Historical aggregate snapshots cannot supply per-type/per-agent stock or
  historical ticket-detail tables. These fields are explicitly unavailable.
- Login-only unknown identities cannot supply a verified full name automatically;
  local overrides provide that name and an automatic/manual abbreviation.
- Existing history-derived actor/event selection and current PBX queue scope are
  preserved. No user-directory enumeration or new Znuny write routes were added.
- Backend fields and local edit methods are ready for the frontend specialist;
  this branch does not change React source/assets or rebuild installer/packaging.

All phases are committed and pushed to `codex/analytics-polish`. The integration
branch remains at the requested baseline; no merge was performed. The final exact
HEAD is recorded in the chat handoff and can be read with `git rev-parse HEAD`.
