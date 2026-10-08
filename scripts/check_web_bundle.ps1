param([switch]$IncludePdf)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$exe = Join-Path $root 'dist\web\ParCom_Analytics_Web\ParCom Znuny Analytics.exe'
$report = Join-Path $root ('.validation\web-bundle-' + [guid]::NewGuid().ToString('N') + '.json')
$originalPath = $env:PATH
try {
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
    $probeArguments = @('--validation', '--smoke-report', ('"' + $report + '"'))
    if ($IncludePdf) { $probeArguments += '--smoke-pdf' }
    $process = Start-Process -FilePath $exe -ArgumentList $probeArguments -PassThru -WindowStyle Hidden
    $timeout = if ($IncludePdf) { 120000 } else { 55000 }
    if (-not $process.WaitForExit($timeout)) {
        Stop-Process -Id $process.Id
        throw 'Desktop smoke test timed out.'
    }
    if (-not (Test-Path -LiteralPath $report)) { throw 'Desktop startup did not produce a report.' }
    $result = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
    if ($process.ExitCode -ne 0 -or -not $result.ok -or -not $result.frozen -or $result.renderer -ne 'edgechromium' -or -not $result.synthetic_reports -or ($IncludePdf -and -not $result.pdf_exports)) {
        throw "Desktop verification failed; inspect $report"
    }
    foreach ($state in @($result.qt_before_export, $result.qt_after_export)) {
        if ($state.modules.Count -or $state.dlls.Count) { throw "Qt loaded in WebView host; inspect $report" }
    }
    Write-Output "WebView2 and report adapters passed with no Qt in the host, without Node/Python on PATH. PDF requested: $IncludePdf. Report: $report"
} finally { $env:PATH = $originalPath }
