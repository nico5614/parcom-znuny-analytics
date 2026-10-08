# React / WebView2 migration

Work only on `codex/frontend`, based on immutable `codex/version-1-0` at
`5e993d0`. The PySide entry point (`start.py`) remains the fallback.

## Completed migration — 8 October 2026

- Existing baseline: **213 tests passed** on Python 3.14.8. Final complete suite:
  **242 passed**, plus the subsequently added PDF-worker-failure regression passed.
- Frontend: **14 unit tests passed** and **8 browser tests passed**. Browser
  fixtures use the production Python DTOs with synthetic tickets; no live login.
- Frontend: React 19.3, TypeScript 7, Vite 8, Tailwind 4, Chart.js 4; pnpm lockfile.
- Desktop: pywebview 6.2.1, pythonnet 3.2.0, Windows WebView2 (`edgechromium`).
- Vite production assets load inside the native desktop window.
- JS calls Python; a JSON reply includes a timezone-aware timestamp. Python
  dispatches a frontend event; React acknowledges it only after rendering.
- PyInstaller **onedir** packages the WebView host and a separate PDF worker.
  Node, pnpm and Python executables are not runtime dependencies.
- Reports are local under `.validation/`; no Znuny credentials or customer data
  are used in the spike. No public installer was produced.
- Windows WebView2 Runtime remains a system prerequisite. This machine has it;
  a clean Windows-machine installation test remains a release gate.

## Build and run

```powershell
py -3.14 -m venv .venv314
.\.venv314\Scripts\python.exe -m pip install -r requirements-web.txt
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend build
.\.venv314\Scripts\python.exe start_web.py
.\scripts\build_web.ps1
```

Output: `dist/web/ParCom_Analytics_Web/ParCom_Analytics_Web.exe`, with its adjacent
`_internal` directory and `pdf_worker/ParCom_PDF_Worker.exe` with a separate
`_internal` directory. Distribute the complete folder.
`scripts/check_web_bundle.ps1` verifies startup without invoking PDF generation;
`scripts/check_web_bundle.ps1 -IncludePdf` additionally requests two real PDFs.
Both probes measure Qt Python modules and loaded Qt DLLs in the host before and
after exporting. All must remain empty. The build runs both checks.

Final native EXE results on this Windows machine: **both probes passed**, using
the packaged React assets, real WebView2/native Python bridge and PATH restricted
to Windows/System32 (pywebview adds only its bundled native runtime paths).
Startup report: `.validation/web-bundle-ffd14ebc3fef47aba53390650e859562.json`.
Export report: `.validation/web-bundle-c9827710392244d790751c52e796769b.json`.
The latter confirms both real PDF exports and empty Qt module/DLL lists before
and after export. Generated Service Desk PDF: 485,617 bytes; reaction-time PDF:
264,774 bytes. This resolves the earlier failed packaging attempts.

## Backend boundaries

- `znuny.py`: sole REST client and owner of the in-memory Znuny session.
- `live_data.py` / `live_cache.py`: fetch, normalization, cache, history.
- `analytics.py` / `live_metrics.py` / `reports.py` / `service_desk.py`: existing
  calculations and report semantics; never duplicate them in TypeScript.
- `periods.py`: timezone-aware rolling/custom intervals and comparisons.
- `agents.py`: history-based attribution and agent identities.
- `pdf_export.py`: existing Qt PDF implementation; retain internally during migration.
- `connection.py`, `ui.py`, `timeline.py`, `agents_ui.py`, `service_desk_ui.py`:
  Qt presentation only; do not import these into the visible WebView frontend.

The bridge exposes explicit DTO methods, with all backend fields private.
The loopback HTTP server serves bundled assets only; it is not a Znuny proxy.
WebView uses private mode, no downloads, no remote resources, and a CSP restricting
connections to its own asset origin. `unsafe-eval` supports pywebview's bridge;
there is no remote script source.

New bridge modules under `parcom_analytics/web`: `app` (WebView lifecycle),
`assets` (static-only server and navigation guard), `bridge` (private session,
background operations, narrow IPC methods), `serialization` (strict JSON),
`dto` (presentation adapters), `settings` (Qt-compatible local preferences),
`pdf_export` (Qt-free subprocess launcher), `pdf_worker` (existing PDF renderer),
and `validation` (opt-in synthetic fixtures).

Completed pages: redesigned login, overview, all seven analyses, agent/team
analytics, PDF export, information/settings and logout. Timeline supports all
six presets, exact custom dates, keyboard control and two drag handles. Ticket
details retain the existing fields and open Znuny through Python. Calculations,
REST calls and existing PDF output remain in the original backend modules.

Cached pages appear immediately; completed refreshes replace the data atomically.
Navigation remains usable during network loading and PDF export. Loading uses
CSS spinners, skeleton cards/charts/tables, a subtle refresh caption and the text
“Znuny-Daten werden geladen …”. Reduced motion honors both OS and local settings.
Charts update in place without animation or unnecessary remounting. Connection,
cached/offline, authentication and refresh errors have distinct states.

Visual/browser validation: 1920×1080, 1050×650, 1536×864 at 125% device scale,
1280×720 at 150% device scale; dark/light layouts and reduced motion. Tests cover
login errors/success, navigation, timeline custom/snap behavior, all analyses,
agent/team selection, ticket fields, export and logout, cached refresh and usable
navigation while requests are pending. Device scaling is browser-emulated;
physical multi-monitor DPI transitions remain an integration check.

## Qt startup failure: root cause and fix

The new build had omitted the legacy `build_windows.ps1` PATH sanitizing.
PyInstaller's previous `Analysis-00.toc` recorded `icuuc.dll` and `icudt78.dll`
from the unrelated Codex Poppler runtime on PATH. That ICU exports `ucnv_open_78`;
PySide6's Qt6Core requires `ucnv_open`, which is supplied by Windows System32 ICU.
The Qt6Core/Gui/Widgets files themselves matched the installed PySide6 wheel.
This explains “Die angegebene Prozedur wurde nicht gefunden”.

There was a second startup dependency even after making Python imports lazy:
including Qt PDF code in the host's PyInstaller analysis installed
`pyi_rth_pyside6`. Its embedded-configuration helper imports `PySide6.QtCore`
before `start_web.py` executes. An application-level lazy import alone therefore
cannot guarantee a Qt-free frozen startup.

The fix separates both analyses and both DLL directories:

- `app.py` has no PDF-worker dispatch/import. Export is never part of normal startup.
- `bridge.py` imports only the Qt-free `web/pdf_export.py` when export is requested.
- `pdf_worker.py` imports QApplication and the old renderer only in its `main`.
- `start_pdf_worker.py` and `parcom_pdf_worker.spec` create the private worker EXE.
  The worker explicitly includes `live_cache` because pickle reconstructs its
  `LiveRecord` dynamically. Its console bootloader is launched with
  `CREATE_NO_WINDOW`: failures are captured instead of showing a crash dialog.
- `parcom_web.spec` excludes PySide6, shiboken6 and the PDF worker, so the host has
  no Qt DLLs or Qt runtime hook. The PDF bundle excludes WebView/pythonnet.
- `build_web.ps1` restores the legacy System32/Windows/build-Python PATH for both
  clean PyInstaller analyses, restoring the original PATH in `finally`.
- The launcher requests a fresh PyInstaller child environment and sanitizes only
  the child's PATH. It never changes the host's process-global DLL search path.
- `test_web_startup.py` forbids all Qt imports during normal startup, checks
  separate worker invocation and verifies packaging exclusions/PATH sanitizing.
  Existing source PDF tests now forbid parent Qt imports; worker-failure tests
  confirm the dashboard remains usable after an export error.

The observed DLL failure is explained by the incompatible bundled ICU. A direct
pythonnet/WebView2-versus-Qt conflict was not independently demonstrated; process
and bundle separation prevents sharing their Qt DLLs regardless.

## Visual reference

The [Mosaic Lite repository](https://github.com/cruip/tailwind-dashboard-template)
and [live reference](https://mosaic.cruip.com/) were inspected for composition:
64px header, slim collapsed navigation / wider expanded sidebar, roughly 24–32px
content insets, a dense card grid, restrained borders, 12px card corners, compact
table rows, and different chart/card spans. Implementation is independent: no
Mosaic source, components, CSS, assets or branding are copied.

## Integration handoff

Preserve the old UI until live acceptance is verified. Remaining release gates:
real Znuny login/data acceptance, clean Windows-machine installation with WebView2
Runtime, physical Windows DPI transitions and the integration branch's installer
adaptation for the new distribution. No final release installer is published by
this specialist branch; no main or integration merge is performed here.

The original checkout was switched by concurrent performance work during Phase 0.
Frontend work was moved intact to the managed `frontend-webview` worktree. Do not
modify or stage the original checkout's performance changes.
