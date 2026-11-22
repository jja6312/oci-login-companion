# PowerShell 5.1-compatible. No policy, registry, Chrome-profile or service edits.
function Get-OciSetupHash([byte[]]$Bytes) {
    $sha = [Security.Cryptography.SHA256]::Create();
    try { return [BitConverter]::ToString($sha.ComputeHash($Bytes)).Replace('-', '').ToLowerInvariant(); } finally { $sha.Dispose(); };
};
function Update-OciCompanion {
    param([byte[]]$Payload, [string]$ExpectedHash, [string]$LocalData = $env:LOCALAPPDATA, [switch]$NoLaunch);
    $ErrorActionPreference = 'Stop';
    if ($PSVersionTable.PSVersion -lt [version]'5.1') { throw 'Windows PowerShell 5.1 or later is required.'; };
    if (-not $NoLaunch -and $env:OS -ne 'Windows_NT') { throw 'Run this update on Windows.'; };
    if (-not $LocalData) { throw 'LOCALAPPDATA is unavailable.'; };
    if ((Get-OciSetupHash $Payload) -cne $ExpectedHash) { throw 'Package checksum mismatch. No files were installed.'; };
    Write-Host '[1/4] Package checksum verified.';
    Add-Type -AssemblyName System.IO.Compression;
    Add-Type -AssemblyName System.IO.Compression.FileSystem;
    $memory = [IO.MemoryStream]::new($Payload, $false);
    $zip = [System.IO.Compression.ZipArchive]::new($memory, [System.IO.Compression.ZipArchiveMode]::Read);
    $hashes = @{}; $total = 0;
    try {
        if ($zip.Entries.Count -gt 512) { throw 'Too many package entries.'; };
        foreach ($entry in $zip.Entries) {
            $name = $entry.FullName;
            if (-not $name.StartsWith('payload/', [StringComparison]::Ordinal) -or $name.Contains('\') -or $name.Contains(':') -or ($name.Split('/') -contains '..') -or ($name.Split('/') -contains '.') -or (($entry.ExternalAttributes -shr 16) -band 0xF000) -eq 0xA000) { throw 'Unsafe package entry.'; };
            $total += $entry.Length;
            if ($total -gt 8388608) { throw 'Package is too large.'; };
            if ($name.EndsWith('/')) { continue; };
            $relative = $name.Substring(8);
            if (-not $relative -or $hashes.ContainsKey($relative)) { throw 'Duplicate package entry.'; };
            $stream = $entry.Open(); $buffer = [IO.MemoryStream]::new();
            try { $stream.CopyTo($buffer); $hashes[$relative] = Get-OciSetupHash $buffer.ToArray(); } finally { $stream.Dispose(); $buffer.Dispose(); };
        };
    } finally { $zip.Dispose(); $memory.Dispose(); };
    if (-not $hashes.ContainsKey('extension/manifest.json') -or -not $hashes.ContainsKey('baseline.json')) { throw 'Incomplete update package.'; };
    $parent = Join-Path ([IO.Path]::GetFullPath($LocalData)) 'Cloudragon'; $target = Join-Path $parent 'OCICompanion'; $extension = Join-Path $target 'extension';
    foreach ($dir in @($parent,$target,$extension)) { if (-not [IO.Directory]::Exists($dir) -or ((Get-Item -LiteralPath $dir -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Supported installation not found. Update the extension ZIP in its existing folder.'; }; };
    $marker = Join-Path $target '.oci-companion-setup.json'; $receiptPath = Join-Path $target '.oci-companion-update.json';
    if (-not [IO.File]::Exists($marker)) { throw 'Unowned installation preserved.'; };
    $stage = Join-Path $parent ('.oci-update-' + [Guid]::NewGuid().ToString('N')); [IO.Directory]::CreateDirectory($stage) | Out-Null; $cleanup = $true; $backup = $null;
    try {
        $archive = Join-Path $stage 'payload.zip'; [IO.File]::WriteAllBytes($archive,$Payload); $unpack = Join-Path $stage 'unpack'; [IO.Compression.ZipFile]::ExtractToDirectory($archive,$unpack); $source = Join-Path $unpack 'payload';
        $baseline = [IO.File]::ReadAllText((Join-Path $source 'baseline.json')) | ConvertFrom-Json; $state = [IO.File]::ReadAllText($marker) | ConvertFrom-Json;
        $current = [IO.File]::ReadAllText((Join-Path $extension 'manifest.json')) | ConvertFrom-Json; $next = [IO.File]::ReadAllText((Join-Path $source 'extension/manifest.json')) | ConvertFrom-Json;
        if ($current.name -cne 'OCI Login Companion' -or $next.name -cne $current.name -or $next.version -cne '1.1.1') { throw 'Unexpected extension manifest.'; };
        $expected = @{}; $reuse = $current.version -ceq '1.1.1';
        if ($reuse) {
            if (-not [IO.File]::Exists($receiptPath) -or (([IO.File]::ReadAllText($receiptPath) | ConvertFrom-Json).payloadSha256) -cne $ExpectedHash) { throw 'Unknown current update preserved.'; };
            foreach ($key in $hashes.Keys) { if ($key.StartsWith('extension/')) { $expected[$key] = $hashes[$key]; }; };
        } else {
            if ($current.version -cne '1.1.0' -or $state.payloadSha256 -cne $baseline.payloadSha256 -or [IO.File]::Exists($receiptPath)) { throw 'Unsupported existing version preserved.'; };
            foreach ($property in $baseline.files.PSObject.Properties) { $expected[$property.Name] = $property.Value; };
        };
        foreach ($key in $expected.Keys) { $file = Join-Path $target $key; if (-not [IO.File]::Exists($file) -or (Get-OciSetupHash ([IO.File]::ReadAllBytes($file))) -cne $expected[$key]) { throw 'Modified extension preserved. No update applied.'; }; };
        $queue = [Collections.Generic.Queue[string]]::new(); $queue.Enqueue($extension); $files = [Collections.Generic.List[object]]::new();
        while ($queue.Count) { foreach ($item in (Get-ChildItem -LiteralPath $queue.Dequeue() -Force)) { if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked extension entries preserved.'; }; if ($item.PSIsContainer) { $queue.Enqueue($item.FullName); } else { $files.Add($item); }; }; };
        if (-not $reuse) {
            foreach ($file in $files) { $relative = $file.FullName.Substring($extension.Length+1).Replace([IO.Path]::DirectorySeparatorChar,'/'); $key = 'extension/' + $relative; if (-not $expected.ContainsKey($key)) { $extra = Join-Path $source $key; if ([IO.File]::Exists($extra)) { throw 'Extra file conflicts with update. Existing files preserved.'; }; [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($extra)) | Out-Null; [IO.File]::Copy($file.FullName,$extra,$false); }; };
            $backup = Join-Path $target ('extension-backup-1.1.0-' + [Guid]::NewGuid().ToString('N')); $receipt = Join-Path $stage 'receipt.json';
            [IO.File]::WriteAllText($receipt,(@{version='1.1.1';payloadSha256=$ExpectedHash;backupPath=$backup} | ConvertTo-Json),[Text.UTF8Encoding]::new($false));
            $oldMoved=$false; $newMoved=$false;
            try { [IO.Directory]::Move($extension,$backup); $oldMoved=$true; [IO.Directory]::Move((Join-Path $source 'extension'),$extension); $newMoved=$true; [IO.File]::Move($receipt,$receiptPath); } catch { try { if($newMoved){[IO.Directory]::Move($extension,(Join-Path $stage 'failed-new'));}; if($oldMoved){[IO.Directory]::Move($backup,$extension);}; } catch { $cleanup=$false; throw 'Rollback incomplete; preserve the backup and staging folder.'; }; throw; };
            Write-Host '[2/4] Updated in the same folder. Previous extension backed up.';
        } else { Write-Host '[2/4] Current update already installed; files verified.'; };
        $guide = Join-Path $target ('Update-Guide-'+[Guid]::NewGuid().ToString('N')+'.html'); $html = [IO.File]::ReadAllText((Join-Path $source 'Update-Guide.template.html')).Replace('{{EXTENSION_PATH}}',[Net.WebUtility]::HtmlEncode($extension)); [IO.File]::WriteAllText($guide,$html,[Text.UTF8Encoding]::new($false));
    } finally { if ($cleanup -and [IO.Directory]::Exists($stage)) { Remove-Item -LiteralPath $stage -Recurse -Force; }; };
    $guideOpened=$false; $folderOpened=$false;
    if(-not $NoLaunch){
        try{Start-Process -FilePath $guide | Out-Null;$guideOpened=$true;}catch{Write-Warning 'Open the update guide in the installation folder.';};
        try{Start-Process -FilePath (Join-Path $env:WINDIR 'explorer.exe') -ArgumentList ([char]34+$extension+[char]34) | Out-Null;$folderOpened=$true;}catch{Write-Warning 'Could not open File Explorer.';};
    };
    Write-Host '[3/4] Update guide opened when available.';
    Write-Host '[4/4] SAME browser/profile: Reload the existing card. Do not remove it.';
    return [PSCustomObject]@{state='UPDATED_RELOAD_EXISTING_EXTENSION';extensionPath=$extension;guidePath=$guide;backupPath=$backup;guideLaunchRequested=$guideOpened;explorerLaunchRequested=$folderOpened};
};
