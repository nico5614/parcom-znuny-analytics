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
