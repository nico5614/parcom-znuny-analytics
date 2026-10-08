param(
    [string]$PythonPath = '.venv314\Scripts\python.exe',
    [string]$IsccPath = '',
    [string]$OutputDirectory = 'dist\release',
    [switch]$SkipBuild
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$originalBuildPath = $env:PATH
Push-Location $projectRoot
try {
    if (-not (Test-Path -LiteralPath $PythonPath)) { throw 'Python-3.14-Buildumgebung fehlt. Siehe README.' }
    $PythonPath = (Resolve-Path -LiteralPath $PythonPath).Path
    & $PythonPath -c 'import sys; assert sys.version_info[:2] == (3, 14) and sys.version_info.releaselevel == "final", "Python 3.14 stable required"'
    if ($LASTEXITCODE -ne 0) { throw 'Falsche Python-Version.' }
    if (-not $IsccPath) {
        $candidates = @((Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 7\ISCC.exe'),
                        (Join-Path $env:ProgramFiles 'Inno Setup 7\ISCC.exe'),
                        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'))
        $IsccPath = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    }
    if (-not $IsccPath) { throw 'Inno Setup fehlt. ISCC-Pfad mit -IsccPath angeben.' }
    if (-not $SkipBuild) {
        & (Join-Path $PSScriptRoot 'build_web.ps1') -PythonPath $PythonPath
    } else {
        # An existing bundle still has to pass startup and PDF checks before packaging.
        & (Join-Path $PSScriptRoot 'check_web_bundle.ps1') -IncludePdf
    }
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
