# Frontend polish continuation

Branch `codex/frontend-polish`, based on user-accepted integration
`118fb47280dacf93f98eb67713338bf451ae0c0d`. Preserve the current layout, optimized
backend and Qt-free WebView host. Do not merge other branches.

## Phase 1 — theme and login

Default light mode; persisted preference is loaded before authentication and
shared by login/dashboard. Login has a theme toggle and readable light colors.
Preference storage stays in Python, never browser storage.

Corporate tokens are exact dominant RGB samples from `assets/app_logo.png`'s
three bars: red `#BF0C1B`, green `#037C35`, blue `#0054B1`. The asset uses gradients;
these are representative source pixel colors, not asserted Pantone specifications.
Sampling: RGBA crop `(190,350,605,750)`, alpha >240, dominant channel >100 and >45
above both others; most frequent matching color, ties sorted lexicographically.
Counts: red 115, green 142, blue 145. Orange decoration is not used as red.

Validation: 18 frontend tests, 10 focused Python tests, TypeScript/Vite build,
four browser theme/contrast checks (1920×1080, 1050×650, simulated 125%/150%) passed.
The phase checkpoint is the commit containing this entry.

Next: Python DTO contexts/trends; chart peaks/animations and agent/team UI;
global toggles/confirmations; secure saved credentials; installed PDF root cause;
visual/package checks. Record a tested/pushed checkpoint after each phase.

## Phase 2 — DTO-driven context and deltas

Consumed the numeric/context contract from `origin/codex/analytics-polish` at
`9c3cbeb` without merging/copying backend implementation into this branch.
Cards display supplied `contextLabel` verbatim and use `deltaAvailable`, signed
`delta`, `unit` and semantic `trend`. Main snapshot values remain neutral; missing
deltas are omitted. Duration formatting is presentation-only (minutes / h+min).
Service medians stay primary; supplied means are expandable secondary details.

Validation: 29 frontend tests, TypeScript/Vite build and eight focused browser
checks passed using actual backend-produced current/historical DTOs. Backend
archive exists only under ignored `.validation/analytics-contract`; fixture
generator accepts `--backend-root` to verify this contract without a branch merge.
When run against the integration backend, unsupported fields are absent and no
fake trends are invented. Final integration must bring in the analytics branch.

Next: chart peaks/maxima, animations/global controls and confirmation dialogs;
agent winner/override consumer once the analytics contract is available, then
credentials and installed PDF flow. Phase checkpoint is this entry's commit.
