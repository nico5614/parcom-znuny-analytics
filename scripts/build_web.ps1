param([switch]$SkipTests)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$python = Join-Path $root '.venv314\Scripts\python.exe'
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
& $python -m PyInstaller --noconfirm --distpath dist/web --workpath build/web packaging/parcom_web.spec
Assert-Exit 'Desktop bundle'
& (Join-Path $PSScriptRoot 'check_web_bundle.ps1')
