# PowerShell 5.1-compatible. No policy, registry, Chrome-profile or service edits.
function Get-OciSetupHash([byte[]]$Bytes) {
    $sha = [Security.Cryptography.SHA256]::Create();
    try { return [BitConverter]::ToString($sha.ComputeHash($Bytes)).Replace('-', '').ToLowerInvariant(); } finally { $sha.Dispose(); };
};
function Install-OciCompanion {
    param([byte[]]$Payload, [string]$ExpectedHash, [string]$LocalData = $env:LOCALAPPDATA, [switch]$NoLaunch);
    $ErrorActionPreference = 'Stop';
    if ($PSVersionTable.PSVersion -lt [version]'5.1') { throw 'Windows PowerShell 5.1 or later is required.'; };
    if (-not $NoLaunch -and $env:OS -ne 'Windows_NT') { throw 'Run this setup on Windows.'; };
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
    if (-not $hashes.ContainsKey('extension/manifest.json') -or -not $hashes.ContainsKey('Install-Guide.template.html')) { throw 'Incomplete setup package.'; };
    $parent = Join-Path ([IO.Path]::GetFullPath($LocalData)) 'Cloudragon';
    $target = Join-Path $parent 'OCICompanion';
    if (Test-Path -LiteralPath $parent) {
        $item = Get-Item -LiteralPath $parent -Force;
        if (-not $item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Installation parent must be an ordinary directory.'; };
    };
    [IO.Directory]::CreateDirectory($parent) | Out-Null;
    $stage = Join-Path $parent ('.oci-setup-' + [Guid]::NewGuid().ToString('N'));
    [IO.Directory]::CreateDirectory($stage) | Out-Null;
    try {
        $archive = Join-Path $stage 'payload.zip'; [IO.File]::WriteAllBytes($archive, $Payload);
        $unpack = Join-Path $stage 'unpack'; [System.IO.Compression.ZipFile]::ExtractToDirectory($archive, $unpack);
        $source = Join-Path $unpack 'payload';
        $manifest = [IO.File]::ReadAllText((Join-Path $source 'extension/manifest.json')) | ConvertFrom-Json;
        if ($manifest.manifest_version -ne 3 -or $manifest.name -cne 'OCI Login Companion' -or $manifest.version -cne '1.1.0') { throw 'Unexpected extension manifest.'; };
        $extension = Join-Path $target 'extension'; $guide = Join-Path $target 'Install-Guide.html';
        $template = [IO.File]::ReadAllText((Join-Path $source 'Install-Guide.template.html'));
        $html = $template.Replace('{{EXTENSION_PATH}}', [Net.WebUtility]::HtmlEncode($extension));
        $marker = Join-Path $target '.oci-companion-setup.json';
        if (Test-Path -LiteralPath $target) {
            $item = Get-Item -LiteralPath $target -Force;
            if (-not $item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or -not [IO.File]::Exists($marker)) { throw 'Existing folder was preserved. It is not owned by this setup.'; };
            $state = [IO.File]::ReadAllText($marker) | ConvertFrom-Json;
            if ($state.payloadSha256 -cne $ExpectedHash) { throw 'Different installation preserved. Back up the extension accounts before updating.'; };
            foreach ($relative in $hashes.Keys) {
                $file = Join-Path $target $relative;
                if (-not [IO.File]::Exists($file) -or (Get-OciSetupHash ([IO.File]::ReadAllBytes($file))) -cne $hashes[$relative]) { throw 'Modified installation preserved. No files were overwritten.'; };
            };
            if (-not [IO.File]::Exists($guide) -or [IO.File]::ReadAllText($guide) -cne $html) { throw 'Modified installation guide preserved.'; };
            Write-Host '[2/4] Identical installation reused.';
        } else {
            $utf8 = [Text.UTF8Encoding]::new($false);
            [IO.File]::WriteAllText((Join-Path $source 'Install-Guide.html'), $html, $utf8);
            $state = @{version = '1.1.0'; setupVersion = 2; payloadSha256 = $ExpectedHash; chromeRegistration = 'USER_ACTION_REQUIRED'};
            [IO.File]::WriteAllText((Join-Path $source '.oci-companion-setup.json'), ($state | ConvertTo-Json), $utf8);
            [IO.Directory]::Move($source, $target);
            Write-Host '[2/4] Extension extracted to the permanent user folder.';
        };
    } finally { if ([IO.Directory]::Exists($stage)) { Remove-Item -LiteralPath $stage -Recurse -Force; }; };
    $copied = $false; $chromeOpened = $false; $folderOpened = $false;
    if (-not $NoLaunch) {
        try { Set-Clipboard -Value $extension; $copied = $true; } catch { Write-Warning 'Copy the extension folder path from the guide.'; };
        $explorer = Join-Path $env:WINDIR 'explorer.exe';
        if ([IO.File]::Exists($explorer)) { try { Start-Process -FilePath $explorer -ArgumentList ([char]34 + $extension + [char]34) | Out-Null; $folderOpened = $true; } catch { Write-Warning 'Could not open File Explorer.'; }; };
        $chrome = $null;
        foreach ($base in @($LocalData, $env:ProgramFiles, ${env:ProgramFiles(x86)})) {
            if ($base) { $candidate = Join-Path $base 'Google/Chrome/Application/chrome.exe'; if ([IO.File]::Exists($candidate)) { $chrome = $candidate; break; }; };
        };
        if ($chrome) { try { Start-Process -FilePath $chrome -ArgumentList @(([Uri]::new($guide)).AbsoluteUri, 'chrome://extensions/') | Out-Null; $chromeOpened = $true; } catch { Write-Warning 'Open Chrome and chrome://extensions manually.'; }; } else { Write-Warning 'Chrome was not found. Open the installed guide after installing Chrome.'; };
    };
    Write-Host '[3/4] Folder is ready. Chrome and Explorer were requested when available.';
    Write-Host '[4/4] In Chrome: enable Developer mode, click Load unpacked, select the folder below.';
    Write-Host $extension;
    return [PSCustomObject]@{state = 'FILES_READY_USER_REGISTRATION_REQUIRED'; extensionPath = $extension; guidePath = $guide; clipboardCopied = $copied; chromeLaunchRequested = $chromeOpened; explorerLaunchRequested = $folderOpened};
};
