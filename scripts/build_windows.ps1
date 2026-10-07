param(
    [string]$PythonPath = '.venv314\Scripts\python.exe',
    [string]$IsccPath = '',
    [string]$OutputDirectory = 'dist\release'
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$originalBuildPath = $env:PATH
Push-Location $projectRoot
try {
    if (-not (Test-Path -LiteralPath $PythonPath)) { throw 'Python-3.14-Buildumgebung fehlt. Siehe README.' }
    $PythonPath = (Resolve-Path -LiteralPath $PythonPath).Path
    # Prevent dependency scanning from collecting unrelated Qt/ICU DLLs from other applications.
    $env:PATH = (Join-Path $env:WINDIR 'System32') + ';' + $env:WINDIR + ';' + (Split-Path -Parent $PythonPath)
    & $PythonPath -c 'import sys; assert sys.version_info[:2] == (3, 14) and sys.version_info.releaselevel == "final", "Python 3.14 stable required"'
    if ($LASTEXITCODE -ne 0) { throw 'Falsche Python-Version.' }
    if (-not $IsccPath) {
        $candidates = @((Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 7\ISCC.exe'),
                        (Join-Path $env:ProgramFiles 'Inno Setup 7\ISCC.exe'),
                        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'))
        $IsccPath = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    }
    if (-not $IsccPath) { throw 'Inno Setup fehlt. ISCC-Pfad mit -IsccPath angeben.' }
    New-Item -ItemType Directory -Path '.validation' -Force | Out-Null
    & $PythonPath -m pytest -q -o cache_dir=.validation/cache --basetemp .validation/build-tests
    if ($LASTEXITCODE -ne 0) { throw 'Tests fehlgeschlagen; Build abgebrochen.' }
    & $PythonPath scripts/prepare_build.py
    if ($LASTEXITCODE -ne 0) { throw 'Windows-Ressourcen konnten nicht erzeugt werden.' }
    & $PythonPath -m PyInstaller --noconfirm --clean packaging/parcom_znuny_analytics.spec
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller-Build fehlgeschlagen.' }
    & $PythonPath scripts/check_bundle.py
    if ($LASTEXITCODE -ne 0) { throw 'Die gebaute Anwendung startet nicht; Installer-Build abgebrochen.' }
    $releasePath = [System.IO.Path]::GetFullPath((Join-Path $projectRoot $OutputDirectory))
    & $IsccPath "/O$releasePath" installer/parcom_znuny_analytics.iss
    if ($LASTEXITCODE -ne 0) { throw 'Installer-Build fehlgeschlagen.' }
    $setupFiles = Get-ChildItem -LiteralPath $releasePath -Filter 'ParCom_Znuny_Analytics_Setup_*.exe'
    $hashLines = $setupFiles | ForEach-Object { (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() + '  ' + $_.Name }
    $hashLines | Set-Content -LiteralPath (Join-Path $releasePath 'SHA256SUMS.txt') -Encoding utf8
    Write-Output "Build abgeschlossen. Installer liegt unter $releasePath."
} finally {
    $env:PATH = $originalBuildPath
    Pop-Location
}
