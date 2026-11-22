param([string]$Origin, [string]$ConfigFile = (Join-Path $PSScriptRoot 'allowed.json'))
$ErrorActionPreference = 'Stop'
# stdout is exclusively the Chrome native-messaging protocol. Never log file contents.
$inputStream = [Console]::OpenStandardInput()
$outputStream = [Console]::OpenStandardOutput()
function Read-Exact([int]$Count) {
    $buffer = New-Object byte[] $Count
    $offset = 0
    while ($offset -lt $Count) {
        $read = $inputStream.Read($buffer, $offset, $Count - $offset)
        if ($read -eq 0) { throw 'EOF' }
        $offset += $read
    }
    return ,$buffer
}
function Respond($Value) {
    $json = ConvertTo-Json -InputObject $Value -Compress -Depth 8
    $data = [Text.Encoding]::UTF8.GetBytes($json)
    if ($data.Length -gt 1048576) { $data=[Text.Encoding]::UTF8.GetBytes('{"ok":false,"error":"RESPONSE_TOO_LARGE"}') }
    $prefix = [BitConverter]::GetBytes([uint32]$data.Length)
    $outputStream.Write($prefix,0,4)
    $outputStream.Write($data,0,$data.Length)
    $outputStream.Flush()
}
try {
    $policy = Get-Content -LiteralPath $ConfigFile -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($Origin -cne $policy.origin) { Respond @{ok=$false;error='ORIGIN_DENIED'}; exit 0 }
    $expected = [IO.Path]::GetFullPath([string]$policy.path)
    $length = [BitConverter]::ToUInt32((Read-Exact 4),0)
    if ($length -eq 0 -or $length -gt 32768) { Respond @{ok=$false;error='REQUEST_TOO_LARGE'}; exit 0 }
    $request = [Text.Encoding]::UTF8.GetString((Read-Exact $length)) | ConvertFrom-Json
    if ($request.action -cne 'read') { Respond @{ok=$false;error='READ_ONLY'}; exit 0 }
    $requested = [IO.Path]::GetFullPath([string]$request.path)
    if (-not [string]::Equals($requested,$expected,[StringComparison]::OrdinalIgnoreCase)) { Respond @{ok=$false;error='PATH_DENIED'}; exit 0 }
    if ([IO.Path]::GetExtension($requested) -ine '.json') { Respond @{ok=$false;error='JSON_ONLY'}; exit 0 }
    $share = [IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete
    $file = [IO.File]::Open($requested,[IO.FileMode]::Open,[IO.FileAccess]::Read,$share)
    try {
        if ($file.Length -gt 524288) { throw 'TOO_LARGE' }
        # Bounded reads remain bounded even if a different process grows the file.
        $bytes = New-Object byte[] 524289
        $count=0
        while ($count -lt $bytes.Length) {
            $read=$file.Read($bytes,$count,$bytes.Length-$count)
            if ($read -eq 0) { break }
            $count += $read
        }
        if ($count -gt 524288) { throw 'TOO_LARGE' }
        $utf8 = New-Object Text.UTF8Encoding($false,$true)
        $text = $utf8.GetString($bytes,0,$count)
    } finally { $file.Dispose() }
    Respond @{ok=$true;text=$text}
} catch {
    try { Respond @{ok=$false;error='FILE_UNAVAILABLE'} } catch {}
}
