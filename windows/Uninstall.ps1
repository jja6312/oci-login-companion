$ErrorActionPreference = 'Stop'
$target=Join-Path $env:LOCALAPPDATA 'Cloudragon\OCILoginCompanion'
$key='HKCU:\Software\Google\Chrome\NativeMessagingHosts\cloudragon.oci_login_files'
$expected=Join-Path $target 'manifest.json'
if (Test-Path $key) {
    if ((Get-Item $key).GetValue('') -ne $expected) { throw 'A different installation is registered. Left unchanged.' }
    Remove-Item -Path $key
}
foreach ($name in @('Host.ps1','host.cmd','manifest.json','allowed.json')) {
    $path=Join-Path $target $name
    if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path }
}
Write-Host 'Helper registration removed. The team JSON file was not changed.'
