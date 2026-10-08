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
