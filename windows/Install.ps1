param([string]$ExtensionId, [string]$ConfigPath, [switch]$AllowWrite)
$ErrorActionPreference = 'Stop'
if (-not $ExtensionId) { $ExtensionId=Read-Host 'Chrome extension ID (chrome://extensions)' }
if ($ExtensionId -cnotmatch '^[a-p]{32}$') { throw 'Invalid Chrome extension ID.' }
if (-not $ConfigPath) { $ConfigPath=Read-Host 'Full path of the team JSON file' }
$ConfigPath=[IO.Path]::GetFullPath($ConfigPath.Trim('"'))
if ([IO.Path]::GetExtension($ConfigPath) -ine '.json' -or -not [IO.File]::Exists($ConfigPath)) { throw 'Select an existing .json file.' }
$target=Join-Path $env:LOCALAPPDATA 'Cloudragon\OCILoginCompanion'
if (Test-Path (Join-Path $target 'allowed.json')) {
    $answer=Read-Host 'Replace this helper installation and its permitted file path? [y/N]'
    if ($answer -ine 'y') { Write-Host 'Cancelled.'; exit 0 }
}
New-Item -ItemType Directory -Path $target -Force | Out-Null
$utf8=New-Object Text.UTF8Encoding($false)
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Host.ps1') -Destination (Join-Path $target 'Host.ps1') -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Uninstall.ps1') -Destination (Join-Path $target 'Uninstall.ps1') -Force
$origin="chrome-extension://$ExtensionId/"
[IO.File]::WriteAllText((Join-Path $target 'allowed.json'),(@{origin=$origin;path=$ConfigPath;allowWrite=[bool]$AllowWrite}|ConvertTo-Json),$utf8)
# Chrome launches this wrapper without a network listener or a background service.
$launch="@echo off`r`n" + '"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -NonInteractive -File "%~dp0Host.ps1" -Origin "%~1"' + "`r`n"
[IO.File]::WriteAllText((Join-Path $target 'host.cmd'),$launch,[Text.Encoding]::ASCII)
$manifest=@{name='cloudragon.oci_login_files';description='OCI Companion team file';path=(Join-Path $target 'host.cmd');type='stdio';allowed_origins=@($origin)}
$manifestPath=Join-Path $target 'manifest.json'
[IO.File]::WriteAllText($manifestPath,($manifest|ConvertTo-Json),$utf8)
$key='HKCU:\Software\Google\Chrome\NativeMessagingHosts\cloudragon.oci_login_files'
New-Item -Path $key -Force | Out-Null
Set-Item -Path $key -Value $manifestPath
Write-Host 'Installed for the current Windows user. No administrator privileges or services were used.'
Write-Host "Permitted file: $ConfigPath"
Write-Host 'In the extension, choose file mode, full path, grant helper permission, and apply.'

if ($AllowWrite) { Write-Host 'Writes are allowed only for the configured file, with a matching previous hash.' } else { Write-Host 'Read-only policy. Use -AllowWrite to permit team edits.' }
