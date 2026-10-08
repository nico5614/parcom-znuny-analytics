param([switch]$SkipTests, [string]$PythonPath = '.venv314\Scripts\python.exe')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$python = (Resolve-Path -LiteralPath $PythonPath).Path
function Assert-Exit([string]$step) { if ($LASTEXITCODE -ne 0) { throw "$step failed ($LASTEXITCODE)" } }
pnpm --dir frontend install --frozen-lockfile
Assert-Exit 'Frontend install'
if (-not $SkipTests) {
    pnpm --dir frontend test
    Assert-Exit 'Frontend tests'
    $env:QT_QPA_PLATFORM = 'offscreen'
    $testTemp = Join-Path $root ('.validation\web-tests-' + [guid]::NewGuid().ToString('N'))
    & $python -m pytest -q --tb=short "--basetemp=$testTemp" -o cache_dir=.validation/web-test-cache
    Assert-Exit 'Python tests'
}
pnpm --dir frontend build
Assert-Exit 'Frontend build'
if (-not $SkipTests) {
    & $python scripts/web_test_data.py
    Assert-Exit 'Browser fixtures'
    pnpm --dir frontend test:e2e
    Assert-Exit 'Browser validation'
}
$originalBuildPath = $env:PATH
try {
    # Match the legacy build: never collect another application's Qt/ICU DLLs.
    $env:PATH = (Join-Path $env:WINDIR 'System32') + ';' + $env:WINDIR + ';' + (Split-Path -Parent $python)
    & $python scripts/prepare_build.py --executable-name 'ParCom Znuny Analytics.exe'
    Assert-Exit 'Windows resources'
    & $python -m PyInstaller --noconfirm --clean --distpath dist/web --workpath build/web packaging/parcom_web.spec
    Assert-Exit 'Desktop bundle'
    & $python -m PyInstaller --noconfirm --clean --distpath dist/web/ParCom_Analytics_Web --workpath build/web packaging/parcom_pdf_worker.spec
    Assert-Exit 'PDF worker bundle'
    & (Join-Path $PSScriptRoot 'check_web_bundle.ps1')
    & (Join-Path $PSScriptRoot 'check_web_bundle.ps1') -IncludePdf
} finally { $env:PATH = $originalBuildPath }
