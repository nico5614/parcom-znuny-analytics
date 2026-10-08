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

## Phase 3 — charts and global controls

Each line series marks its maximum and draws a dashed guide; bar maxima use a
stronger fill. Chart.js animates bars/donuts and progressively draws lines.
Updates reuse charts; changed datasets initialize controllers before reset.
Global motion preference persists beside theme; Windows reduced motion wins.
Delta animation is local to changed values. The Info checkbox is removed.

Longer-than-seven-day requests and logout require confirmation; cancellation
preserves the loaded period/data. New-data detection shows an optional amber
badge beside refresh. Hover/focus connection detail displays the actual backend
successful login/sync timestamp, never frontend clock time. Compact service rows
keep the desktop overview within 1080px. Browser timer simulation starts before
app initialization to exercise the existing two-minute polling interval.

Validation: 42 frontend tests, 15 focused Python tests, TypeScript/Vite build;
32 browser scenarios cover four sizes/DPI profiles, confirmations, hover/focus,
optional refresh, reduced motion and navigation without chart errors.

Next: backend-supplied agent winners/local overrides, secure saved credentials,
then installed PDF reproduction/fix and final packaging. PDF remains a release
blocker until the installed native save-dialog flow is verified.

## Phase 4 — backend winners and local identities

Consumed the agent contract exported from `origin/codex/analytics-polish` without
merging. `isPeriodWinner` controls crown/fill/name accents; frontend never ranks
agents to invent winners. The employee card preserves all backend ties, zero
response minutes, primary median and secondary mean. Detailed ticket navigation
remains available separately. Team management shows source login/ID and current
name/code; edit/save/reset call Python persistence methods and reload on close.
The automatic LRO mapping remains exclusively the backend's responsibility.
Unsupported integration-backend override APIs disable editing with an explanation.

Validation: 44 frontend tests, build, four winner/editor browser checks plus the
existing 32 scenarios at 1920×1080, 1050×650 and 125%/150% simulated DPI. Relevant
Python tests include existing agents and WebView contracts. Fixtures now include
actual scoped agent discovery and tied winners from the exported backend.

Next: secure Windows credentials and PDF release blocker. Native Windows UI
automation currently fails before initialization with `helper_unknown_error:
setup refresh had errors`, including after a kernel reset. Do not describe the
native save dialog as verified from smoke tests that bypass it. The registry's
production path `C:\Dev\ParCom Znuny Analytics\` does not exist on this host;
use the independent validation installer identity instead of replacing user data.

## Phase 5 — opt-in Windows credentials and checkpoint

Login saving defaults off. Python uses `keyring.backends.Windows.WinVaultKeyring`
explicitly, with local-machine persistence, never backend autodetection or a
plaintext fallback. Only availability/support/username cross back to React;
saved-password retrieval stays Python-side. Successful authentication is required
before saving. Replacing an identity first removes its old vault entry to avoid
keyring's compound backup copies. Removal remains available independently of the
save checkbox. A vault failure leaves normal login working and reports a warning.
No password enters settings, cache, browser storage or application logs. Validation
mode uses its own unique vault target and never accesses the production target.

Implementation references: [keyring documentation](https://keyring.readthedocs.io/en/latest/)
and [official Windows backend](https://github.com/jaraco/keyring/blob/main/keyring/backends/Windows.py).
Dependencies are pinned in `requirements-web.txt`.

Validation: 46 frontend tests, 36 browser scenarios, TypeScript/Vite build and
288 full Python tests passed. The native Windows-vault regression creates only a
unique synthetic test entry; save/replace/remove succeeds, old passwords are no
longer accessible and cleanup runs in `finally`. Browser profiles cover
1920×1080, 1050×650 and simulated 125%/150% DPI. Desktop overview fits 1080px;
team popup, light/dark dashboard, analyses and agents retain the approved layout.

PDF investigation: the existing integrated payload passed isolated installer,
upgrade, installed startup, overview PDF, analysis 5 PDF and uninstall at
`.validation/installer-ee04014649474a5895d911ed91408821/result.json`.
Its smoke report `.validation/web-bundle-27c399953b7f40189681632575429aaa.json`
shows no PySide/shiboken modules or Qt6 Core/Gui/Widgets DLLs before/after export.
The test bypasses the native save dialog. Consequently the reported installed
save error is **not reproduced/fixed**, and PDF remains a release blocker.
Native UI automation is unavailable because its helper fails during sandbox
initialization. No unrelated application or real credentials were used.

The final source WebView host and separate worker were rebuilt with sanitized
PATH. The frozen host archive includes Windows keyring and the credentials
module, and excludes PySide/shiboken. Final bundled frontend files match source
build SHA-256 hashes. The complete bundle startup/overview PDF/analysis PDF probe
passed with no Node/Python on PATH and no Qt modules/DLLs in the host:
`.validation/web-bundle-b70f11d1acde427992f03d08111dc1c4.json`.
This final bundle has not yet been validated through the native save dialog or
packaged into a new production installer. Existing `dist/release` setup remains
the previous integrated payload, not the polish release.

Changed files in this phase: `web/credentials.py`, `web/bridge.py`, `web/app.py`,
`requirements-web.txt`, Login/Info/Shell, bridge types, login styles and focused
Python/frontend tests. Earlier phases contain appearance, metric semantics,
Chart.js highlights/animations, confirmations and employee/team components.

Checkpoint stop: account remaining usage reached 15%; finish this phase's build,
test, commit/push only. Do not start another large phase. Do not merge.

Required continuation:
1. Restore Windows UI automation, then reproduce the full React → native save →
   worker flow in a separately registered installation using synthetic data.
   Test spaces, Desktop/Documents, cancel, overwrite and both report types.
2. Capture worker path/cwd/environment/return code/stderr/output existence, identify
   the real cause, implement a focused fix and installed-flow regression. Generic
   error-message changes alone are insufficient. Qt stays exclusively in worker.
3. Confirm packaged secure-login behavior and rebuild a complete installer from
   the final source, retaining the independent validation identity for tests.
4. Integration must combine the analytics DTO/override branch with this frontend;
   this branch does not copy/merge its backend. Tested exported contract was
   `9da9eba2293dee606d43688ff0fbbe38b0abed52`.
