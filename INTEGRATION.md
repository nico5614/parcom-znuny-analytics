# Integration continuation

## Phase 1 — completed, 8 October 2026

- Integration branch created from immutable baseline `5e993d0826b389cdccee51e7f6e1d460c5e22838` and pushed.
- Performance HEAD verified locally/remotely: `b393882f97b93e3a464d34abcb7bb90f8b1c3951`.
- Frontend HEAD verified locally/remotely: `0d8083c673acca37f6949d3d9ba18b7e2847e956`.
- Antigravity equals baseline; no unique changes, no merge. Deletion remains Phase 9.
- Checks: clean starting tree, exact branch hashes, unchanged baseline and application files. No application tests needed for branch/document preparation.
- Checkpoint commit: the commit containing this entry (`git log -1 --format=%H -- INTEGRATION.md`).
- Next: Phase 2. Merge performance, run focused tests and complete Python suite, then checkpoint/push before merging frontend.
- No code blocker. Default sandbox process startup fails; reviewed escalated commands work. Previous quota-related approval failure is resolved.
- Real Znuny acceptance remains pending personal interactive login. It does not block unrelated synthetic validation or packaging.

## Phase 2 — completed, 8 October 2026

- Integrated performance HEAD `b393882f97b93e3a464d34abcb7bb90f8b1c3951` without conflicts or implementation changes.
- Focused performance/REST/incremental/connection/agent/live UI tests: 72 passed in 11.18 s.
- Complete Python suite: 248 passed in 34.04 s, matching specialist test count.
- Diff against specialist application/tests is empty; no frontend introduced. Baseline remains `5e993d0`.
- Phase 1 checkpoint: `74fdfb5`. Phase 2 checkpoint is the merge commit containing this entry.
- Next: Phase 3, merge frontend `0d8083c673acca37f6949d3d9ba18b7e2847e956`.
- Required integration adaptations found by read-only review: bridge refresh must stage/commit transactionally after cache persistence; Agenten must request lazy history and distinguish unavailable history from zero. Preserve Qt-free host and separate PDF worker.

## Phase 3 — completed, 8 October 2026

- Integrated frontend HEAD `0d8083c673acca37f6949d3d9ba18b7e2847e956`; no textual merge conflicts.
- Bridge now stages optimized refreshes, persists the complete cache, then commits the synchronization watermark under backend locks. Agent history is demand-loaded through the existing optimized loader; repeated navigation uses cache. Offline history not yet loaded is explicitly unavailable, never zero.
- Four integration regressions verify delta counts, no REST calls on ordinary navigation, disk-failure watermark preservation, lazy/reused history and unavailable offline attribution.
- Python: 282 passed in 66.72 s. Frontend: 14 passed. TypeScript and Vite production build passed. Browser: 8 passed in 34.0 s (1920, 1050, simulated 125%/150%). Existing PDF worker/startup isolation tests passed.
- Phase 2 checkpoint: `dc3b867`. Phase 3 checkpoint is the merge commit containing this entry.
- Next: Phase 4, native integrated source application smoke with real WebView2 and two PDF worker exports. Then document real acceptance as pending if no interactive sign-in, and perform visual acceptance before packaging.
- No live Znuny login or real timing measurements claimed. No packaging/release/Main changes yet.

## Phase 4 — completed, 8 October 2026

- Phase 3 checkpoint: `6580254`.
- Native integrated source smoke passed with actual Windows WebView2 (`edgechromium`), bundled production frontend assets and React acknowledgement of the Python bridge event.
- All seven report adapters and Agenten adapter succeeded; both actual PDF exports (overview and response time) succeeded in subprocesses.
- Qt modules and Qt DLLs in the host were empty before and after PDF export. Report: ignored `.validation/integration-source.json`.
- UI interaction coverage: 8 passing browser checks from Phase 3 cover login/error distinction, navigation, all analyses, timeline custom/snap, agents/team, details, export, logout, cache and navigation during pending requests. Native smoke verifies the actual renderer/bridge; browser checks use controlled synthetic IPC.
- No source fixes required in this phase. Next: Phase 5, record availability of interactive live acceptance, then Phase 6 visual review.

## Phase 5 — live acceptance pending, 8 October 2026

- No interactive personal Znuny login is available in this run. No credentials were searched, stored or requested in chat.
- Real PBX/PBX Intern data validation and all production REST timings remain unverified; no synthetic timing is presented as live measurement.
- Per the integration order, this pending acceptance does not block independent visual/packaging work. Main merge and release remain gated on live acceptance.
- Phase 4 checkpoint: `3c08964`. Next: Phase 6, inspect the integrated React renderings at desktop/compact sizes and available simulated scaling.

## Phase 6 — visual acceptance completed within available environment

- Reviewed actual integrated React screenshots from Phase 3: desktop overview/agents, compact 1050-wide analysis and 150% simulated overview. Sidebar, dense card grid, chart hierarchy, active states and scrollable tables match the new frontend composition; no PySide presentation is used.
- All 8 browser checks passed at 1920x1080, 1050x650 and simulated 125%/150% scaling, including loading navigation and reduced motion. Native WebView2 startup/bridge was independently verified in Phase 4.
- No visual code changes required. A physical monitor DPI transition and fresh Windows installation remain unverified, not represented by browser scaling.
- Phase 5 checkpoint: `c9c2673`. Next: Phase 7, production frontend/frozen bundle; preserve PDF worker isolation and sanitize PATH. Use the final requested EXE name and verify before starting installer work.

## Phase 7 — completed, 8 October 2026 — RESUME HERE

- Phase 6 checkpoint: `e577299`.
- Production frontend built; PyInstaller onedir host and independent PDF worker built successfully with sanitized PATH. Final executable name and version resources added without changing backend/UI behavior.
- Focused packaging/bridge regression tests: 8 passed in 2.31 s. Latest complete suite remains 282 Python / 14 frontend / 8 browser checks, all green (Phase 3).
- Both actual frozen checks passed on this Windows host without Python/Node on PATH: local React assets, rendered bridge acknowledgement, synthetic report adapters and both real PDF exports. Qt modules/DLLs in host empty before and after exports.
- Reports (ignored): `.validation/web-bundle-a52656d38de94a66a7b98eb2be7efaa7.json` and `.validation/web-bundle-7b9bc0dbab574d08a44a1287b307db32.json`. Build log: `.validation/integration-build.log`.
- EXE: `dist/web/ParCom_Analytics_Web/ParCom Znuny Analytics.exe`. Requires adjacent `_internal` and `pdf_worker` directories; not a standalone single-file distribution.
- Metadata verified: ParCom Znuny Analytics, product 1.0.0, file 1.0.0.0, publisher Nico Köchli, correct OriginalFilename. Unsigned.
- EXE SHA256: `b6ed67499240ef61233d971cfa5ee1b0b8b7fa17ae138171ccb0f57fc0f61b6a`.
- Checkpoint commit: commit containing this entry (`git log -1 --format=%H -- INTEGRATION.md`).

### Next exact phase: Phase 8 — installer and uninstaller

1. Read SKILL.md, status/log and this note; check quota. Do not redo phases 1–7 or merge the specialists again.
2. Adapt Inno Setup/build orchestration to the integrated distribution and final EXE name. Current `installer/parcom_znuny_analytics.iss` and `scripts/build_windows.ps1` still target the old PySide distribution. Keep the sanitized WebView build/checks and PDF worker isolation.
3. Verify WebView2 runtime detection/behavior, version/publisher, selectable path, shortcuts, Apps entry and upgrade behavior.
4. Only after frozen checks (already passed), build installer, install, launch/export, uninstall and verify application cleanup plus LocalAppData retention. Inspect existing installation/registry before changing anything: an existing installation was previously observed at `C:\Dev\ParCom Znuny Analytics`; do not delete user data.
5. Checkpoint/push Phase 8 before cleanup (9), final README/screenshots (10), final validation (11) and gated Main/release (12).

### Open gates / preserved state

- Phase 5 real Znuny acceptance/timing remains pending personal interactive login. No live measurements fabricated. Does not block packaging, but blocks final Main/tag/release acceptance.
- Physical DPI transition and fresh Windows machine still unverified. Current installed WebView2 runtime is available on the development host.
- Old PySide fallback retained pending full parity/live acceptance. Do not remove backend or working Qt PDF engine.
- Antigravity equals baseline; remove only during Phase 9 as authorized. Baseline and both specialist branches unchanged. Main still `f25d853550fba6f86ef8bdc7e4bde3da9118fce8`; no tag/release.
- Default sandbox process startup fails; reviewed escalated commands work. No security rejection outstanding.
- Stopped at a coherent Phase 7 checkpoint because remaining current-window usage reached 14%; no Phase 8 implementation begun.

## Phase 8 — completed on development host, 8 October 2026

- Phase 7 checkpoint: `3e1aeca`. Installer now packages the integrated WebView onedir distribution and isolated PDF worker, with version 1.0.0 / publisher Nico Köchli and the final executable name.
- Build entry delegates to the sanitized WebView pipeline. Existing-bundle packaging still requires an actual frozen startup/PDF check. Upgrade replaces only managed runtime directories and removes the obsolete executable; user data remains outside the payload.
- `scripts/check_installer.ps1` compiles the same installer under a separate validation identity to preserve the existing user installation. Actual current-user installation, selected path, desktop/Start Menu shortcuts, Installed Apps metadata, reinstallation/obsolete-file cleanup, installed application startup and both PDF exports passed. Uninstall removed managed files, shortcuts and registration, retained LocalAppData and unrelated files; own retention markers subsequently removed.
- WebView2 detected from Microsoft's documented runtime registry keys. Simulated absent runtime blocks before installation with German guidance; this test override exists only in the validation installer. No machine runtime registry was changed. Reference: https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution
- 13 focused Python startup/bridge tests passed (1.24 s). Native installed PDF/Qt-isolation report: `.validation/web-bundle-1a5ea5491baf4f68a5a00b93dccf3288.json`. Installer result: `.validation/installer-5e5e5c487fd945f2a5bfdf01d5198493/result.json`. Initial cleanup assertion raced the Inno helper; bounded settling added and complete repeat passed.
- Production setup: `dist/release/ParCom_Znuny_Analytics_Setup_1.0.0.exe`; SHA256 `d6b85d960e7888849bc46774bffaa25a15fd9ee82e137871c8b5fd56854157fa`. Unsigned, local artifact, not a published release. No Excel/PDF/cache/settings/fixture data files in the distribution.
- Validation uses an isolated AppId; the existing production installation was not upgraded or uninstalled. Fresh Windows/all-users installation and actual runtime installation on a machine without WebView2 remain unverified. Live acceptance and physical DPI gate remain open.
- Checkpoint: commit containing this entry (`git log -1 --format=%H -- INTEGRATION.md`). Next exact phase: 9, targeted cleanup and authorized obsolete antigravity branch deletion; then final README/screenshots (10), validation (11), gated release (12).

## Phase 9 — completed, 8 October 2026

- Phase 8 checkpoint: `c141b63`.
- Remote antigravity/version-1-0 was exactly baseline `5e993d0826b389cdccee51e7f6e1d460c5e22838`, with no unique code; authorized remote deletion completed. Local branch was already absent. Verified absence after deletion; baseline/specialists/Main unchanged.
- Removed this integration's disposable pytest directories and validation-only installer binaries after checking paths. Retained JSON/log evidence, final EXE/setup artifacts and meaningful source/tests. Removed all own install retention markers; existing user installation retained.
- Tracked-file check found no XLSX/PDF/cache/settings/.env files. Focused credential-pattern scan found no matching hardcoded passwords/session tokens in application, scripts, frontend source or tests. This is a targeted hygiene check, not a claim of a comprehensive security audit.
- No application code changed; Phase 8's 13 passing focused tests and native installer checks remain current. Git status clean before this note; diff checked.
- Checkpoint: commit containing this note. Next exact phase: 10, safe screenshots of the integrated UI and final German README. Live acceptance / fresh machine / physical DPI remain open; no Main merge or release.

## Phase 10 — completed, 8 October 2026

- Phase 9 checkpoint: `11bfd44`.
- Replaced obsolete README with German documentation of the integrated React/WebView/Python application: ten actual-stack badges, architecture diagram, all workflows, transparent score formula, synthetic performance table, source/frozen/installer usage, development/build/tests, storage/security and explicit release limitations.
- Six real frontend captures in `docs/screenshots/` (1600 px wide, total about 1.05 MB): login, overview hero, escalation analysis/ring chart, agents, ticket details and export. All six visually reviewed. These are Edge renders of the production frontend with controlled Python DTO fixtures, explicitly labelled as such, not a claimed live/native production session.
- Screenshot-only fixture process anonymizes all identity seeds and uses supplied synthetic history events; no production code changed. No usernames/passwords/customer content in captures. Identity-string scan and README local-link checks passed.
- Shared the existing browser-test IPC helper with the separate documentation capture. Final repeat: 8 browser checks passed (25.4 s), documentation capture 1 passed (5.3 s). PNGs remain unedited screenshots; no UI mockups or generated artwork.
- Checkpoint: commit containing this note. Next exact phase: 11, full Python/frontend suites, production frontend build check and final validation documentation. Phase 12 remains gated by real Znuny acceptance, clean-machine/DPI acceptance and release/licensing readiness; do not merge/tag automatically.

## Phase 11 — completed; Phase 12 gated, 8 October 2026 — RESUME HERE

- Phase 10 checkpoint: `5f7cd8d`.
- Final Python suite: 282 passed in 47.01 s. Frontend: 14 passed across 5 files. TypeScript/Vite production build passed. Latest browser repeat: 8 passed in 25.4 s; separate documentation capture: 1 passed in 5.3 s.
- Rebuilt frontend assets hash-identical to those in the already validated frozen/installed bundle; no application changes since packaging. Installer metadata, size and SHA256 reconfirmed. No need to rebuild unchanged Python binaries or repeat completed installer phases.
- Replaced obsolete VALIDATION.md with integrated results, exact artifact paths/hashes, test boundaries, synthetic performance, install/uninstall evidence, README/screenshot status and remaining acceptance gates. SKILL.md re-read; status/diff reviewed.
- Remote baseline, performance, frontend and Main SHAs rechecked unchanged. Antigravity absent. Main still `f25d853550fba6f86ef8bdc7e4bde3da9118fce8`; no Main merge/tag/release performed.
- Checkpoint commit: commit containing this entry (`git log -1 --format=%H -- INTEGRATION.md`).

### Next exact action

Automated integration phases 1–11 are complete (Phase 5 explicitly pending live acceptance). Phase 12 cannot proceed until the documented real Znuny and clean-machine/DPI acceptance is supplied/completed. No credentials are available in this run. Do not search for stored credentials or repeat completed phases. Resume with personal interactive acceptance in the application, record real timings, resolve only verified issues and then assess release readiness. Licensing/third-party distribution notices also remain to be settled for public production distribution. Local installer exists and is tested within the documented scope; it has not been published as a GitHub Release.

## Final release polish — phases A/B verified, 9 October 2026 — RESUME HERE

The final release order supersedes the previous Phase 12 continuation. User confirmed real login, PBX/PBX Intern data, tickets/KPIs, installation, shortcuts/icons and the overall frontend. These are user-reported acceptance, not new agent measurements. Installed native Save-dialog PDF failure remains an unresolved release blocker.

- Analytics handoff: `6c0285201206f1e57a5a97eb2d0e671150f8cd64`, codex/analytics-polish; clean, pushed, specialist completed. Full suite reported 324 passing tests. Handoff: ANALYTICS_POLISH.md on that branch.
- Frontend handoff: `de701c967ae674bbd91ea6e7e01bc07b9057a924`, codex/frontend-polish; clean, pushed, specialist completed. Reported 288 Python, 46 frontend and 36 browser checks passing, plus frozen Qt-free host/PDF-worker probes. Handoff: FRONTEND_POLISH.md on that branch.
- Local/remote HEADs agree. Merge-base of both branches, and each against integration, is exactly `118fb47280dacf93f98eb67713338bf451ae0c0d`. Both specialists idle; no work overwritten. Shared checkout returned from the clean frontend-polish branch to codex/integration for this documentation checkpoint only.
- No new tests run: this phase verifies handoffs and ancestry; no application changes or merges made. Status/diff checked before checkpoint. Main/tag/release untouched.
- Frontend tested analytics contract at `9da9eba`; integration must assess final analytics compatibility. Native PDF save dialog was not reproduced/fixed. Installed smoke bypassed dialog; it is not evidence that the reported bug is resolved.
- Current usage reached 96% used. Per user limit, no large phase started. Automatic follow-up remains enabled; wait for sufficient quota before merging.

Next exact phase C: read the final release attachment a5a76b71-4ca8-45ee-97fb-d30181e4b4b8 and both full handoff documents, verify unchanged HEADs/status, merge analytics-polish first into codex/integration, run full Python tests, fix only integration defects, commit/push. Then phase D: merge frontend-polish, resolve conflicts carefully, full Python/frontend/browser/build checks, checkpoint/push. Continue E–P from the final release order; no release until the installed PDF flow is fixed and validated. Fresh Windows/physical DPI unavailable must be stated accurately. No fabricated live timings. Branch deletion only after successful release.

Checkpoint SHA: commit containing this note (`git log -1 --format=%H -- INTEGRATION.md`).

## Release polish phase C — completed, 9 October 2026

- Previous checkpoint: `0d1efbe`. Merged analytics-polish `6c0285201206f1e57a5a97eb2d0e671150f8cd64` without textual conflicts; specialist implementation preserved.
- Full integrated Python suite: 324 passed in 63.56 s. Evidence: ignored `.validation/release-phase-c.log`. Diff/status reviewed; no frontend implementation merged in this phase.
- Checkpoint: merge commit containing this entry. Next phase D: merge frontend-polish `de701c967ae674bbd91ea6e7e01bc07b9057a924`, reconcile only actual conflicts, run full Python/frontend/browser/build checks, commit/push before further acceptance.
- Installed native save-dialog PDF failure remains unresolved. Main/tag/release untouched.

## Release polish phase D — completed, 9 October 2026

- Phase C checkpoint: `8c48146`. Merged frontend-polish `de701c967ae674bbd91ea6e7e01bc07b9057a924`; automatic bridge merge reviewed, no textual conflicts or integration fixes required.
- Combined full Python suite: 330 passed in 77.50 s. Frontend: 46 passed. TypeScript/Vite production build passed. Browser: 36 passed in 58.1 s using freshly generated DTOs from the actual merged backend, not the older exported contract.
- Median-primary metrics, backend contexts/directions, historical missing snapshots, human winners/local overrides, light-first theme, credential-store isolation, confirmations and reduced motion retain specialist tests. No formulas rewritten.
- Diff/status checked. Checkpoint: merge commit containing this entry. Next phase E: native integrated source acceptance; preserve user-confirmed baseline live acceptance and document any unavailable new live checks. Then F performance evidence, G visual review, H unresolved installed native Save-dialog PDF blocker.
- No production EXE/installer yet built from the combined polish. Existing dist artifacts are specialist/older integration builds. Main/tag/release untouched.

## Release polish phase E — source validation completed, 9 October 2026

- Phase D checkpoint: `4d50c44`. Native integrated source WebView2 start succeeded with local production assets and React/Python bridge acknowledgement. All seven report adapters plus agents and both actual PDF-worker flows succeeded; host Qt modules/DLLs empty before/after. Evidence: `.validation/release-source.json`.
- Combined UI behavior is covered by phase D's 36 browser checks; source native probe is synthetic and bypasses the save dialog. It does not resolve the installed PDF blocker.
- User-confirmed real login, PBX/PBX Intern load, ticket/KPI function, installation/icons and general layout acceptance retained. No new personal live session or production measurements available in this run, so detailed post-polish live acceptance is not newly claimed.
- No application fixes needed. Next F: record available performance evidence and live-measurement boundary; G visual/theme/animation review; H reproduce the installed native save flow. Checkpoint: commit containing this note.

## Release polish phase F — available performance evidence recorded, 9 October 2026

- Phase E checkpoint: `1458481`. No new personal live session is available, so no production TicketSearch/Get/History durations or naturally changed-ticket timings are invented. Earlier user-confirmed live functionality remains accepted.
- The combined 330-test suite includes connection reuse, max-concurrency=4, deduplication, delta cache, lazy/versioned history and failed-refresh persistence regressions. Fresh integrated browser fixtures and navigation checks do not add backend REST calls.
- Specialist synthetic counts remain the available benchmark evidence: initial 7 searches/40 gets/0 history; unchanged refresh 8/0/0; four changed tickets 8/4/0; first history demand 1/0/40, then unchanged demand 1/0/0. These are synthetic, not server measurements; full methodology in ANALYTICS_POLISH.md.
- No code changes required. Next G: review merged light/dark UI, responsive charts/agent presentation and motion controls. Then H: native installed PDF-dialog blocker. Checkpoint: commit containing this entry.

## Release polish phase G — partial visual checkpoint, 9 October 2026 — RESUME HERE

- Previous checkpoint: `327917a`. Reviewed merged browser captures: overview desktop, light compact 1050 px, agents desktop and team modal at simulated 150% scale. Light layout, chart peak guides, median/delta presentation, winner ties and team controls are present. Phase D's 36 passing browser checks remain the current behavioral evidence; no application code changed since those checks.
- The dark overview capture caught the initial chart animation frame. Do not treat that single frame as a proven chart defect; inspect a settled frame before final visual acceptance. Physical Windows DPI is not verified by browser scale emulation.
- Interactive native source validation is not complete: the test launched with `Start-Process -WindowStyle Hidden` exposed the React login accessibility tree but rendered a blank dark WebView area after activation; element bounds were outside the window. The cause is not established. Retry an explicitly visible interactive test launch before changing application code. The successful earlier native smoke probe does not prove this visible flow.
- Own synthetic source process at checkpoint: PID 26724, workspace `.venv314/Scripts/pythonw.exe`, launched with `start_web.py --validation --width 1280 --height 800`. Re-identify command line before closing it; do not touch any user application process. Computer-use helper previously selected its window titled `ParCom Analytics`. Native UI must be freshly observed after resume, not driven using old element indexes.
- Next exact action: finish phase G's settled chart/native visual check, then phase H. Reproduce the full native save-dialog path in an isolated installed combined build: overview and individual analysis, paths with spaces, Documents/Desktop, cancel and overwrite. Existing worker smoke exports bypassed the dialog and cannot establish the user's reported PDF error is fixed. The bridge currently collapses export exceptions into a generic error; add narrowly scoped safe diagnostics if needed to establish the actual cause before fixing it.
- Current distribution artifacts are older integration/frontend-only builds, not the combined polish. Do not publish or describe them as final. Production build, installer, licensing, refreshed light README screenshots and final release gates remain pending.
- Usage reached 80% used before this checkpoint; no new large phase started. Keep the authorized follow-up active and resume from this entry with sufficient quota. Status/diff checked; documentation-only checkpoint, existing tests remain applicable. Main/tag/release untouched.

## Latest finalization order acknowledged, 9 October 2026

- New authoritative request: `C:\Users\nicokoechli\.codex\attachments\541a1165-44e4-46a8-82c4-d7b0a9540a69\Eingefügter Text.txt`, read completely. Continue existing integrated work; do not repeat specialist phases. Previous checkpoint `9f6a1e1` was clean and pushed.
- New phase numbering: 1 native visible application acceptance (continue the partial G work above); 2 installed end-to-end PDF acceptance/root-cause fix; 3 final production validation/build/install cycle; 4 accurate README/light screenshots; 5 gated main/tag/release, including complete license verification; 6 authorized branch cleanup after release verification.
- Only 14% primary quota remained on receipt. Per the checkpoint rule, no new large acceptance phase started. Existing 330 Python / 46 frontend / 36 browser results are retained, not newly rerun. No application code changed. Updated the existing authorized 15-minute follow-up to this latest order and exact next action.
- Resume native acceptance with sufficient quota. Earlier blank/offscreen native test and installed PDF failure remain unverified; neither is waived by passing worker/browser tests. Main/tag/release unchanged.

## Finalization phase 1 — native visual acceptance, 9 October 2026

- Resumed from `f028cfe`, clean. Visible source WebView2 launch (`pythonw start_web.py --validation --width 1280 --height 800`, normal window) rendered correctly. The earlier hidden-start blank area did not reproduce; no speculative application fix applied. Isolated synthetic data and validation credentials only; no real Znuny connection or credentials used.
- Inspected real native login in default light and optional dark themes; source window and maximized desktop layout; overview charts after settling, peak guides, median metrics, semantic deltas, neutral stock, analyses including escalation ring and highest-bar emphasis, ticket-detail modal, agents/winner crowns, team-management modal, export and Info. Animation switch changed its state; detailed animation/reduced-motion regressions remain covered by the prior 36 browser checks. Local override persistence retains existing tests; not a newly claimed manual edit in this pass.
- Native synthetic login and logout confirmation worked. A >7-day request displayed confirmation; Escape preserved the previous period. Historical endpoint displayed `Stand am 08.10.2026 15:38` and unavailable stock as a dash; current period previously displayed `Stand jetzt`. Connection tooltip showed the real successful synthetic-request timestamp. After the normal two-minute poll, amber `Neue Daten verfügbar` appeared without replacing the selected period/data.
- 10 focused startup/polish/credential tests passed (1.56 s). No production code changes. This is native Windows testing at the host's existing scaling, not separate physical 100/125/150% or clean-machine acceptance. Earlier browser scale checks remain separately identified.
- Next exact phase 2: build the combined distribution needed for an isolated installed PDF reproduction, then exercise the actual native save dialog end-to-end. Do not substitute worker smoke checks. Source test PID 26416 at this checkpoint; re-identify before cleanup. No final release artifact yet. Main/tag/release unchanged.

## Finalization phase 2 — installed test prepared, interactive check interrupted

- Built combined integration `0126f5a` with `scripts/build_web.ps1 -SkipTests`. TypeScript/Vite and both PyInstaller bundles completed; actual frozen startup/adapters and overview/individual PDF worker exports passed with no Qt modules/DLLs in the host and no Node/Python on PATH. Evidence: `.validation/final-pdf-build.log`, `.validation/web-bundle-2f16792d20e14840b5f83a8a88c94169.json`, `.validation/web-bundle-2f0f44c90f7947bd9cc252e3bdb4de54.json`. These bypass the save dialog. Source test process 26416 was closed.
- Compiled same installer with `/DValidationInstall` and installed under separate validation identity in `.validation/installed-pdf-acceptance/Application With Spaces`. Setup: `.validation/installed-pdf-acceptance/ParCom_Installer_Validation.exe`; compile log `.validation/pdf-installer-compile.log`. Existing production installation preserved. Installed test launched visibly with `--validation --width 1280 --height 800` from the system temporary working directory (PID 16360 at launch). Login renders with the application icon.
- Computer Use initially timed out awaiting app access, then succeeded. Subsequent interaction repeatedly reported `user input was detected in this window; call get_window_state before continuing`; the window also became minimized. Fresh observation/reselection/activation recovery did not resolve this. Stopped input rather than competing with detected interaction. No PDF save dialog has yet been successfully exercised; no root cause or fix is claimed.
- Next exact action: freshly identify the existing isolated installed test window when native input is available; complete overview/individual saves to Desktop/Documents, spaces, cancellation, overwrite and real PDF open/render checks. Actual Windows folders resolved to `C:\Users\nicokoechli\Desktop` and `C:\Users\nicokoechli\Documents`. Do not rebuild unchanged artifacts or repeat phase 1. Inspect the existing validation registration before any installer rerun; keep this test installation until its end-to-end check is done, then uninstall it without touching the production identity.
- No application code changed. Existing test results retained; status/diff checked. Phase 2 remains open, followed by final production validation, licenses, README/light screenshots and release gates. No Main/tag/release changes.

## Finalization phase 2 — PDF root cause fixed in source, 10 October 2026

- Resumed `c16f900`, clean. Native input worked again. In the existing installed validation application, opened the synthetic local cache, selected Export / Service Desk overview and clicked `Als PDF speichern`. Reproduced the user's exact error immediately, before any native file dialog appeared.
- Root cause verified against the actual shipped pywebview parser: `PDF-Dateien (*.pdf)` raises `ValueError: PDF-Dateien (*.pdf) is not a valid file filter`. Its description grammar accepts word characters/spaces, not a hyphen. `window.create_file_dialog` validates this before calling WinForms; neither the chosen path nor the PDF worker is reached. Worker-only smoke probes replaced this callback and therefore missed the defect.
- Surgical fix: use `PDF Dateien (*.pdf)`. Added a regression exercising the application's registered save callback with the real pywebview filter parser, the SAVE type, an intact selected path containing spaces and cancelled result. No score, frontend or renderer change.
- Focused startup/export tests: 14 passed (11.35 s). Full Python: 331 passed (67.55 s), `.validation/pdf-fix-full.log`. Frontend: 46 passed, `.validation/pdf-fix-frontend.log`. Diff and status reviewed.
- Installed end-to-end validation is NOT yet complete. The currently installed test application and dist bundles still contain the pre-fix filter. Next exact action is rebuild the changed host/bundle, upgrade the same isolated validation installation, then test real save dialogs: overview/individual, Desktop/Documents, spaces, cancel, overwrite, output existence and opening/rendering. Retain the separate validation identity and never overwrite production installation. No release until those checks succeed.
- At the checkpoint, weekly quota had only 13% remaining (primary 54% remaining). Per the user's low-quota rule, finish this tested fix checkpoint without beginning a new major rebuild/installed-acceptance run. Follow-up remains active. Main/tag/release unchanged.

## Finalization phase 2 — dialog dispatch and font fixes, 13 October 2026 — RESUME HERE

- Continued from `74d0c09`; quota-review interruptions on 11/12 October prevented the earlier checkpoint. The user explicitly authorized continuing despite low quota. No specialist phases repeated.
- The filter-only build was rebuilt and upgraded in the existing isolated test installation. It hung before showing the save dialog. Dispatching the callback through the native window's STA thread fixed this in both visible source and installed tests. Regression now verifies dispatch, valid filter, selected path and cancellation.
- Actual installed overview saved to `C:\Users\nicokoechli\Desktop\ParCom Validation Overview.pdf`; escalation analysis saved to `C:\Users\nicokoechli\Documents\ParCom Validation Analysis.pdf`. Both paths contain spaces; frontend confirmed success. Installed cancellation displayed `Export abgebrochen.`. Overwrite remains unverified: automatic approval review hit its usage limit before Return submitted the existing analysis path. Never bypassed the review.
- Poppler successfully opened both PDFs (8 and 5 pages), but rendered text as boxes while chart text remained readable. Root cause measured: Qt offscreen plugin exposes 0 font families / no Segoe UI on Windows; native Windows plugin exposes 368 / Segoe UI. Worker and launcher now select `windows` only on Windows, retaining `offscreen` elsewhere. No windows/widgets are displayed by the worker. Source export rerendered with readable text: `.validation/font-overview.pdf` and `.png`.
- Added a subprocess regression verifying the real worker initializes a font with German and numeric glyphs. Full Python: **332 passed in 99.28 s**, `.validation/pdf-final-tests.log`. Latest unchanged frontend: **46 passed**, `.validation/sta-frontend.log`. Earlier sandbox-only test failures were temporary-directory access failures; unrestricted full run passed. Status/diff reviewed.
- Final corrected host AND worker build completed: `.validation/pdf-final-build.log`; TypeScript/Vite passed; frozen probes `.validation/web-bundle-d18c45ea0dfb45b59e14a5d8be63c4ce.json` and `.validation/web-bundle-1616df0e14884364a5634fe3a1e245b3.json` passed without Qt in host, without Node/Python on PATH, including both worker exports.
- IMPORTANT: `dist/web/ParCom_Analytics_Web` contains BOTH fixes, but current isolated installed application / `.validation/installed-pdf-acceptance/ParCom_Installer_Validation.exe` contains ONLY STA + filter fixes, NOT the font fix. Do not rebuild the already completed bundle. Recompile validation installer from it, upgrade the existing `.validation/installed-pdf-acceptance/Application With Spaces` identity (production untouched), then repeat real saves, overwrite and render final PDFs. Existing two named test PDFs are ours and may be overwritten for acceptance; do not touch other user files.
- Native test window last known ID 396338; source test 1510458. Re-identify rather than reuse handles. Installed save dialog may still contain our Documents analysis target; prior Return was not executed. Follow with full final validation/install-upgrade-uninstall, licenses, updated light screenshots/README, then gated release. Main/tag/release unchanged; Phase 2 is NOT complete yet.

### Installed font-fix update, 13 October 2026

- Code checkpoint `cb97135` pushed. Compiled final corrected validation installer successfully (82.25 s), `.validation/pdf-final-installer.log`, and upgraded the existing isolated `Application With Spaces` installation. BOTH fixes are now installed. No additional rebuild is required.
- Installed worker/host probe passed: `.validation/pdf-final-installed-smoke.log`, `.validation/web-bundle-9e5f43de23744453879c2c5f0c6e1ded.json`. Qt absent from host before/after both exports; no Node/Python on PATH. Actual installed output PDFs were opened with Poppler and first pages rendered/visually checked: `.validation/final-installed-overview.png` and `.validation/final-installed-analysis.png`; text, German characters, numbers and charts readable. This probe bypasses the native dialog and does not replace the remaining interactive acceptance.
- Visible test started, window ID 330158 at launch. Computer Use returned `failed to activate captured window`; fresh window inventory/rebinding and one activation retry returned the same error. Stopped native input per tool recovery instructions. No overwrite acceptance claimed. Next: regain normal foreground window access, repeat final installed saves/overwrite and inspect all report pages; retain existing synthetic Desktop/Documents files as own overwrite targets. No production installation touched, no release performed.

### Resume blocked by Windows tooling, 14 October 2026

- User explicitly resumed finalization. Read SKILL.md, full finalization order and latest continuation; HEAD 8e25d35 was clean. No completed phase repeated and no application changes.
- Normal shell and native Computer Use runtime fail before executing with `MXC launcher: enumerate MXC volume P:\: ... (os error 1326)` (invalid username/password). An unrestricted read-only shell worked; native Node runtime initialization and one retry both exited before window inventory. No alternative UI automation used to bypass this failure.
- Native installed PDF acceptance remains pending at exactly the prior point. Corrected bundle/installer already exist; do not rebuild. Windows tool runtime must become available after the P: drive access/environment issue is resolved, then launch the isolated installed application explicitly with --validation before testing final saves/overwrite and all report pages. No production data, Main, tag or release changed.

### C-drive-only continuation, 14 October 2026

- User explicitly restricted all filesystem access to C:. Do not inspect, reconnect, disconnect or otherwise access other drives. Do not retry the sandbox/Node launcher known to enumerate other volumes until a C-only runtime is available. Unrestricted shell operations explicitly targeting C: work.
- Continued phase 2 without GUI automation: rendered every page of the existing corrected installed-worker reports (Service_Desk_2026-10-13.pdf: 7 pages; Reaktionszeit_2026-10-06T09-13-17+02-00_2026-10-13T09-13-17+02-00.pdf: 8 pages) with local Poppler to .validation/pdf-pages-final. Visually inspected all remaining pages after the previously reviewed first pages. German text, charts and repeated table headers are readable; all 24 synthetic analysis tickets continue across pages, including zero values. No missing-glyph boxes or clipped table columns observed. Some continuation pages contain only one or two rows; no data loss observed.
- This completes full-page readability review of these existing installed-worker outputs, not native dialog/overwrite acceptance. No source changes or repeated tests/builds; documentation diff checked. Native save-dialog acceptance remains blocked by the tool launcher environment, not by a demonstrated new application defect. No release or main changes.

### Full-access retry and independent finalization, 14 October 2026

- User granted full tool access and requested another attempt. No login credentials needed: earlier real login/live-data acceptance remains recognized. C-drive-only file constraint retained.
- Shell now starts normally. Computer Use initialization/window inventory times out; retry and explicit kernel reset/reinitialization also timed out. No window inputs issued, no native dialog acceptance claimed. Automation remains paused.
- Final automated suites rerun successfully: 332 Python tests (89.34 s), 46 frontend tests, 36 browser tests. Logs: .validation/tests-final-20261014.log, frontend-final-20261014.log, browser-final-20261014.log. No application source changed.
- Completed independent documentation work while native acceptance is blocked: six actual frontend screenshots refreshed in light mode using anonymous synthetic Python DTOs. Screenshot capture waits for Chart.js canvas animations; screenshot test passed (11.6 s), all six images visually inspected. README corrected for user-confirmed live acceptance, selected-period comparisons/snapshot semantics, median-first presentation, selected-period score prerequisites and opt-in Windows credential storage.
- This is documentation/validation progress, not release approval. Remaining: native installed dialog saves/overwrite; final installer upgrade/uninstall; license verification/distribution notices; final release gates. Existing corrected application bundles need no rebuild for these documentation-only changes. Main/tag/release unchanged.
