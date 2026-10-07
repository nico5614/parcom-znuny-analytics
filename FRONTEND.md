# React / WebView2 migration

Work only on `codex/frontend`, based on immutable `codex/version-1-0` at
`5e993d0`. The PySide entry point (`start.py`) remains the fallback.

## Phase 0 verification — 8 October 2026

- Existing baseline: **213 tests passed** on Python 3.14.8. An initial run hit
  permissions on a pre-existing system temporary folder; an explicit project
  `--basetemp` resolved it without changing application code.
- Frontend: React 19.3, TypeScript 7, Vite 8, Tailwind 4, Chart.js 4; pnpm lockfile.
- Desktop: pywebview 6.2.1, pythonnet 3.2.0, Windows WebView2 (`edgechromium`).
- Vite production assets load inside the native desktop window.
- JS calls Python; a JSON reply includes a timezone-aware timestamp. Python
  dispatches a frontend event; React acknowledges it only after rendering.
- PyInstaller **onedir** EXE passed the same round trip with PATH restricted to
  Windows/System32. Node, pnpm and Python executables are not runtime dependencies.
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
`_internal` directory. `scripts/check_web_bundle.ps1` rechecks a built bundle.

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

## Visual reference

The [Mosaic Lite repository](https://github.com/cruip/tailwind-dashboard-template)
and [live reference](https://mosaic.cruip.com/) were inspected for composition:
64px header, slim collapsed navigation / wider expanded sidebar, roughly 24–32px
content insets, a dense card grid, restrained borders, 12px card corners, compact
table rows, and different chart/card spans. Implementation is independent: no
Mosaic source, components, CSS, assets or branding are copied.

## Continuation

Phase 0 is complete. Next: the new login page, then overview, analyses, agents,
ticket details, export, info and logout. Each milestone requires focused tests,
relevant backend checks, diff review, commit and push. Preserve the old UI until
feature parity and live acceptance are verified.

The original checkout was switched by concurrent performance work during Phase 0.
Frontend work was moved intact to the managed `frontend-webview` worktree. Do not
modify or stage the original checkout's performance changes.
