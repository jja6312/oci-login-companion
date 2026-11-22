param([string]$Origin, [string]$ConfigFile = (Join-Path $PSScriptRoot 'allowed.json'))
$ErrorActionPreference='Stop'
# stdout is exclusively the native-messaging protocol. Never log file contents.
$inputStream=[Console]::OpenStandardInput();$outputStream=[Console]::OpenStandardOutput()
function Read-Exact([int]$Count) {
 $buffer=New-Object byte[] $Count;$offset=0
 while($offset -lt $Count){$n=$inputStream.Read($buffer,$offset,$Count-$offset);if($n -eq 0){throw 'EOF'};$offset+=$n}
 return ,$buffer
}
function Respond($Value) {
 $data=[Text.Encoding]::UTF8.GetBytes((ConvertTo-Json -InputObject $Value -Compress -Depth 8))
 if($data.Length -gt 1048576){$data=[Text.Encoding]::UTF8.GetBytes('{"ok":false,"error":"RESPONSE_TOO_LARGE"}')}
 $prefix=[BitConverter]::GetBytes([uint32]$data.Length);$outputStream.Write($prefix,0,4);$outputStream.Write($data,0,$data.Length);$outputStream.Flush()
}
function Hash-Bytes([byte[]]$Bytes){$h=[Security.Cryptography.SHA256]::Create();try{return ([BitConverter]::ToString($h.ComputeHash($Bytes))).Replace('-','').ToLowerInvariant()}finally{$h.Dispose()}}
function Read-Team([string]$Path) {
 $share=[IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete;$file=[IO.File]::Open($Path,[IO.FileMode]::Open,[IO.FileAccess]::Read,$share)
 try{
  if($file.Length -gt 524288){throw 'TOO_LARGE'};$bytes=New-Object byte[] 524289;$count=0
  while($count -lt $bytes.Length){$n=$file.Read($bytes,$count,$bytes.Length-$count);if($n -eq 0){break};$count+=$n}
  if($count -gt 524288){throw 'TOO_LARGE'};$actual=New-Object byte[] $count;[Array]::Copy($bytes,$actual,$count)
  $utf8=New-Object Text.UTF8Encoding($false,$true)
  return @{text=$utf8.GetString($actual);sha256=(Hash-Bytes $actual)}
 }finally{$file.Dispose()}
}
function Check-Config([string]$Text){
 $v=$Text.TrimStart([char]0xFEFF)|ConvertFrom-Json
 if($v.schemaVersion -ne 1 -or $null -eq $v.profiles -or $v.profiles -isnot [array] -or $v.profiles.Count -gt 300){throw 'INVALID_CONFIG'}
 $seen=New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::Ordinal)
 foreach($p in $v.profiles){
  if($p.id -isnot [string] -or $p.id -cnotmatch '^[a-zA-Z0-9_-]{1,80}$' -or -not $seen.Add($p.id)){throw 'INVALID_CONFIG'}
  foreach($key in @('tenancy','username','password','bypassCode')){if($p.$key -isnot [string] -or [string]::IsNullOrWhiteSpace($p.$key) -or $p.$key.Contains([char]0)){throw 'INVALID_CONFIG'}}
  if($p.tenancy.Length -gt 150 -or $p.username.Length -gt 320 -or $p.password.Length -gt 2000 -or $p.bypassCode.Length -gt 1000){throw 'INVALID_CONFIG'}
 }
}
try{
 $policy=Get-Content -LiteralPath $ConfigFile -Raw -Encoding UTF8|ConvertFrom-Json
 if($Origin -cne $policy.origin){Respond @{ok=$false;error='ORIGIN_DENIED'};exit 0}
 $expected=[IO.Path]::GetFullPath([string]$policy.path);$length=[BitConverter]::ToUInt32((Read-Exact 4),0)
 if($length -eq 0 -or $length -gt 2097152){Respond @{ok=$false;error='REQUEST_TOO_LARGE'};exit 0}
 $request=[Text.Encoding]::UTF8.GetString((Read-Exact $length))|ConvertFrom-Json
 $canWrite=$policy.allowWrite -is [bool] -and $policy.allowWrite
 if($request.action -cne 'read' -and ($request.action -cne 'write' -or -not $canWrite)){Respond @{ok=$false;error='READ_ONLY'};exit 0}
 $requested=[IO.Path]::GetFullPath([string]$request.path)
 if(-not [string]::Equals($requested,$expected,[StringComparison]::OrdinalIgnoreCase)){Respond @{ok=$false;error='PATH_DENIED'};exit 0}
 if([IO.Path]::GetExtension($requested) -ine '.json'){Respond @{ok=$false;error='JSON_ONLY'};exit 0}
 if($request.action -ceq 'read'){$r=Read-Team $requested;Respond @{ok=$true;text=$r.text;sha256=$r.sha256;canWrite=$canWrite;protocolVersion=2};exit 0}
 if($request.text -isnot [string] -or $request.expectedHash -cnotmatch '^[0-9a-f]{64}$'){throw 'INVALID_CONFIG'}
 $utf8=New-Object Text.UTF8Encoding($false,$true);$data=$utf8.GetBytes($request.text)
 if($data.Length -gt 524288){throw 'TOO_LARGE'};Check-Config $request.text
 $mutexName='CloudragonOciTeam-'+(Hash-Bytes ($utf8.GetBytes($requested.ToLowerInvariant())))
 $mutex=New-Object Threading.Mutex($false,$mutexName);$locked=$false;$temp=$null
 try{
  try{$locked=$mutex.WaitOne(5000)}catch [Threading.AbandonedMutexException]{$locked=$true}
  if(-not $locked){throw 'FILE_BUSY'}
  if((Read-Team $requested).sha256 -cne $request.expectedHash){throw 'CONFLICT'}
  $temp=Join-Path ([IO.Path]::GetDirectoryName($requested)) ('.'+[IO.Path]::GetFileName($requested)+'.oci-'+[guid]::NewGuid().ToString('N')+'.tmp')
  $writer=[IO.File]::Open($temp,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
  try{$writer.Write($data,0,$data.Length);$writer.Flush($true)}finally{$writer.Dispose()}
  if((Read-Team $requested).sha256 -cne $request.expectedHash){throw 'CONFLICT'}
  [IO.File]::Replace($temp,$requested,[NullString]::Value);$temp=$null
  $saved=Read-Team $requested;if($saved.sha256 -cne (Hash-Bytes $data)){throw 'CONFLICT'}
  Respond @{ok=$true;sha256=$saved.sha256;protocolVersion=2}
 }finally{
  if($temp -and [IO.File]::Exists($temp)){[IO.File]::Delete($temp)}
  if($locked){$mutex.ReleaseMutex()};$mutex.Dispose()
 }
}catch{try{if($_.Exception.Message -eq 'CONFLICT'){Respond @{ok=$false;error='CONFLICT'}}else{Respond @{ok=$false;error='FILE_UNAVAILABLE'}}}catch{}}
