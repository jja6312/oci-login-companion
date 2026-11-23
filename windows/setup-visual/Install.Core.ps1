function Install-OrUpdateOciCompanion {
    param([byte[]]$Payload,[string]$ExpectedHash,[string]$LocalData=$env:LOCALAPPDATA,[switch]$NoLaunch)
    $ErrorActionPreference='Stop'
    if((Get-OciSetupHash $Payload) -cne $ExpectedHash){throw 'Package checksum mismatch.'}
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $memory=[IO.MemoryStream]::new($Payload,$false)
    $zip=[IO.Compression.ZipArchive]::new($memory,[IO.Compression.ZipArchiveMode]::Read)
    $entries=@{};$size=0
    try{
        foreach($entry in $zip.Entries){
            $name=$entry.FullName
            if(-not $name.StartsWith('payload/') -or $name.Contains('\') -or $name.Contains(':') -or ($name.Split('/') -contains '..') -or ($name.Split('/') -contains '.') -or (($entry.ExternalAttributes -shr 16) -band 0xF000) -eq 0xA000){throw 'Unsafe package entry.'}
            $size+=$entry.Length
            if($size -gt 8388608 -or $entries.Count -gt 512 -or $entries.ContainsKey($name)){throw 'Invalid package size or duplicate entry.'}
            $entries[$name]=$true
        }
    }finally{$zip.Dispose();$memory.Dispose()}
    foreach($name in @('payload/extension/manifest.json','payload/Update-Guide.template.html','payload/baseline.json')){if(-not $entries.ContainsKey($name)){throw 'Incomplete package.'}}
    $parent=Join-Path ([IO.Path]::GetFullPath($LocalData)) 'Cloudragon'
    $target=Join-Path $parent 'OCICompanion'
    foreach($dir in @($parent,$target)){
        if(Test-Path -LiteralPath $dir){$item=Get-Item -LiteralPath $dir -Force;if(-not $item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Linked installation folder preserved.'}}
    }
    if(Test-Path -LiteralPath $target){return Update-OciCompanion -Payload $Payload -ExpectedHash $ExpectedHash -LocalData $LocalData -NoLaunch:$NoLaunch}
    [IO.Directory]::CreateDirectory($parent)|Out-Null
    $stage=Join-Path $parent ('.oci-visual-setup-'+[Guid]::NewGuid().ToString('N'))
    [IO.Directory]::CreateDirectory($stage)|Out-Null
    try{
        $archive=Join-Path $stage 'payload.zip';[IO.File]::WriteAllBytes($archive,$Payload)
        [IO.Compression.ZipFile]::ExtractToDirectory($archive,(Join-Path $stage 'unpack'))
        $source=Join-Path $stage 'unpack\payload'
        $manifest=[IO.File]::ReadAllText((Join-Path $source 'extension\manifest.json')) | ConvertFrom-Json
        if($manifest.name -cne 'OCI Login Companion' -or $manifest.version -cne '1.3.5' -or $manifest.manifest_version -ne 3){throw 'Unexpected extension manifest.'}
        $extension=Join-Path $target 'extension';$guide=Join-Path $target 'Install-Guide.html'
        $html=[IO.File]::ReadAllText((Join-Path $source 'Update-Guide.template.html')).Replace('{{EXTENSION_PATH}}',[Net.WebUtility]::HtmlEncode($extension)).Replace('{{INSTALL_MODE}}','new')
        [IO.File]::WriteAllText((Join-Path $source 'Install-Guide.html'),$html,[Text.UTF8Encoding]::new($false))
        $marker=@{version='1.3.5';setupVersion=14;payloadSha256=$ExpectedHash;chromeRegistration='USER_ACTION_REQUIRED'}
        $receipt=@{version='1.3.5';payloadSha256=$ExpectedHash;backupPath=$null}
        [IO.File]::WriteAllText((Join-Path $source '.oci-companion-setup.json'),($marker|ConvertTo-Json),[Text.UTF8Encoding]::new($false))
        [IO.File]::WriteAllText((Join-Path $source '.oci-companion-update.json'),($receipt|ConvertTo-Json),[Text.UTF8Encoding]::new($false))
        [IO.Directory]::Move($source,$target)
    }finally{
        if([IO.Directory]::Exists($stage)){
            $checked=[IO.Path]::GetFullPath($stage)
            if($checked.StartsWith($parent+'\.oci-visual-setup-',[StringComparison]::OrdinalIgnoreCase)){Remove-Item -LiteralPath $checked -Recurse -Force}
        }
    }
    $opened=$false
    if(-not $NoLaunch){try{Start-Process -FilePath $guide|Out-Null;$opened=$true}catch{Write-Warning 'Open Install-Guide.html from the installation folder.'}}
    Write-Host 'Files installed. Follow the red boxes in the guide.'
    return [pscustomobject]@{state='FILES_READY_USER_REGISTRATION_REQUIRED';extensionPath=$extension;guidePath=$guide;guideLaunchRequested=$opened;explorerLaunchRequested=$false}
}
