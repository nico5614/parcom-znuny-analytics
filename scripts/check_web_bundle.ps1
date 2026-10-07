$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$exe = Join-Path $root 'dist\web\ParCom_Analytics_Web\ParCom_Analytics_Web.exe'
$report = Join-Path $root ('.validation\web-bundle-' + [guid]::NewGuid().ToString('N') + '.json')
$originalPath = $env:PATH
try {
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
    $process = Start-Process -FilePath $exe -ArgumentList '--smoke-report', ('"' + $report + '"') -PassThru -WindowStyle Hidden
    if (-not $process.WaitForExit(55000)) {
        Stop-Process -Id $process.Id
        throw 'Desktop smoke test timed out.'
    }
    if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $report)) { throw 'Desktop startup failed.' }
    $result = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
    if (-not $result.ok -or -not $result.frozen -or $result.renderer -ne 'edgechromium') {
        throw 'Desktop bridge verification failed.'
    }
    Write-Output "WebView2 packaged round trip passed without Node/Python on PATH. Report: $report"
} finally { $env:PATH = $originalPath }
