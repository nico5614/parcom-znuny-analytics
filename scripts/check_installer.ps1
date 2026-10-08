param([string]$IsccPath = (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 7\ISCC.exe'))
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$validationRoot = Join-Path $root '.validation'
$run = Join-Path $validationRoot ('installer-' + [guid]::NewGuid().ToString('N'))
$install = Join-Path $run 'app'
$registry = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\'
$productionKey = $registry + 'ParCom.ZnunyAnalytics_is1'
$testKey = $registry + 'ParCom.ZnunyAnalytics.Validation_is1'
$testName = 'ParCom Znuny Analytics Installationstest'
$programs = Join-Path ([Environment]::GetFolderPath('Programs')) $testName
$desktopLink = Join-Path ([Environment]::GetFolderPath('Desktop')) ($testName + '.lnk')
$marker = Join-Path $env:LOCALAPPDATA ('ParCom\ZnunyAnalytics\installer-check-' + [guid]::NewGuid().ToString('N') + '.txt')
if ((Test-Path $testKey) -or (Test-Path $programs) -or (Test-Path $desktopLink)) {
    throw 'An earlier validation installation exists; inspect it before continuing.'
}
$productionBefore = if (Test-Path $productionKey) { Get-ItemProperty $productionKey | Select-Object DisplayName, DisplayVersion, Publisher, InstallLocation, UninstallString | ConvertTo-Json -Compress } else { '' }
New-Item -ItemType Directory -Path $run -Force | Out-Null

function Run-Setup([string]$Path, [string[]]$Arguments, [int]$ExpectedExit = 0) {
    $process = Start-Process -FilePath $Path -ArgumentList $Arguments -PassThru -WindowStyle Hidden
    if (-not $process.WaitForExit(180000)) { throw "Installer timed out: $Path" }
    if ($process.ExitCode -ne $ExpectedExit) { throw "Installer exit code: $($process.ExitCode). Inspect $run" }
}

# Same payload and installer logic, separate identity: never uninstall the user's application.
& $IsccPath /DValidationInstall "/O$run" /FParCom_Installer_Validation (Join-Path $root 'installer\parcom_znuny_analytics.iss') *> (Join-Path $run 'compile.log')
if ($LASTEXITCODE -ne 0) { throw "Validation installer compilation failed: $run" }
$setup = Join-Path $run 'ParCom_Installer_Validation.exe'
$arguments = @('/CURRENTUSER', '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', ('/DIR="' + $install + '"'), '/TASKS=desktopicon')
Run-Setup $setup ($arguments + '/ValidateMissingWebView=1' + ('/LOG="' + (Join-Path $run 'missing-runtime.log') + '"')) 7
if ((Test-Path $testKey) -or (Test-Path $install)) { throw 'Missing runtime did not block installation.' }
Run-Setup $setup ($arguments + ('/LOG="' + (Join-Path $run 'install.log') + '"'))
$entry = Get-ItemProperty $testKey
if ($entry.DisplayVersion -ne '1.0.0' -or $entry.Publisher -ne 'Nico Köchli') { throw 'Installed Apps metadata incorrect.' }
$exe = Join-Path $install 'ParCom Znuny Analytics.exe'
$shell = New-Object -ComObject WScript.Shell
foreach ($link in @($desktopLink, (Join-Path $programs ($testName + '.lnk')))) {
    if (-not (Test-Path $link) -or $shell.CreateShortcut($link).TargetPath -ne $exe) { throw "Invalid shortcut: $link" }
}

# Upgrade must remove obsolete managed files, preserve unrelated files and user data.
New-Item -ItemType Directory -Path (Split-Path $marker) -Force | Out-Null
Set-Content -LiteralPath $marker -Value 'installer retention check'
$preserved = Join-Path $install 'user-retention-check.txt'
Set-Content -LiteralPath $preserved -Value 'unmanaged file'
$stale = @((Join-Path $install '_internal\obsolete-validation.dll'),
           (Join-Path $install 'pdf_worker\obsolete-validation.dll'),
           (Join-Path $install 'ParCom_Znuny_Analytics.exe'))
foreach ($file in $stale) { Set-Content -LiteralPath $file -Value 'obsolete managed file' }
Run-Setup $setup ($arguments + ('/LOG="' + (Join-Path $run 'upgrade.log') + '"'))
foreach ($file in $stale) { if (Test-Path $file) { throw "Stale upgrade file remains: $file" } }
if (-not (Test-Path $marker) -or -not (Test-Path $preserved)) { throw 'Upgrade removed retained data.' }
& (Join-Path $PSScriptRoot 'check_web_bundle.ps1') -ExecutablePath $exe -IncludePdf
Run-Setup (Join-Path $install 'unins000.exe') @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', ('/LOG="' + (Join-Path $run 'uninstall.log') + '"'))
if ((Test-Path $testKey) -or (Test-Path $programs) -or (Test-Path $desktopLink)) { throw 'Uninstall left registration or shortcuts.' }
# Inno's temporary helper removes the uninstaller after the parent has exited.
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    $remaining = @(Get-ChildItem -LiteralPath $install -Force)
    if ($remaining.Count -eq 1 -and $remaining[0].FullName -eq $preserved) { break }
    Start-Sleep -Milliseconds 250
}
if ($remaining.Count -ne 1 -or $remaining[0].FullName -ne $preserved) { throw 'Uninstall left managed files.' }
if (-not (Test-Path $marker)) { throw 'Uninstall removed LocalAppData.' }
$productionAfter = if (Test-Path $productionKey) { Get-ItemProperty $productionKey | Select-Object DisplayName, DisplayVersion, Publisher, InstallLocation, UninstallString | ConvertTo-Json -Compress } else { '' }
if ($productionAfter -ne $productionBefore) { throw 'Production installation registration changed.' }

# Remove only files created by this check; keep reports for the continuation note.
Remove-Item -LiteralPath $marker
Remove-Item -LiteralPath $preserved
Remove-Item -LiteralPath $install
@{ ok = $true; identity = 'ParCom.ZnunyAnalytics.Validation'; version = $entry.DisplayVersion;
   install = $true; upgrade = $true; installed_startup_and_pdf = $true; uninstall = $true;
   local_data_preserved = $true; production_registration_unchanged = $true; missing_runtime_blocks_install = $true } |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $run 'result.json') -Encoding utf8
Write-Output "Installer, upgrade, installed startup/PDF and uninstall passed: $run"
