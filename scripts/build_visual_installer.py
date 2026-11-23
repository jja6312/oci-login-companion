"""Single offline CMD; all supporting files go below _support."""
import base64
import hashlib
import io
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'dist/windows-visual-r16'


def main():
    support=OUT/'_support';support.mkdir(parents=True,exist_ok=True)
    entries={}
    for file in (ROOT/'extension').rglob('*'):
        if file.is_file():entries['payload/extension/'+file.relative_to(ROOT/'extension').as_posix()]=file.read_bytes()
    entries['payload/baseline.json']=(ROOT/'windows/setup-visual/baseline.json').read_bytes()
    entries['payload/Update-Guide.template.html']=(ROOT/'windows/setup-visual/Guide.template.html').read_bytes()
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w',zipfile.ZIP_DEFLATED) as z:
        for name,body in sorted(entries.items()):
            info=zipfile.ZipInfo(name,(2026,11,23,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16;z.writestr(info,body)
    payload=data.getvalue();digest=hashlib.sha256(payload).hexdigest()
    (support/'payload.zip').write_bytes(payload)
    core=(ROOT/'windows/setup-visual/Update.Core.ps1').read_text()+'\n'+(ROOT/'windows/setup-visual/Install.Core.ps1').read_text()
    entry=core+f"""
$args=@{{Payload=$Payload;ExpectedHash='{digest}'}}
if($env:CLOUDRAGON_SETUP_LOCAL_DATA){{$args.LocalData=$env:CLOUDRAGON_SETUP_LOCAL_DATA}}
if($env:CLOUDRAGON_SETUP_NO_LAUNCH){{$args.NoLaunch=$true}}
Install-OrUpdateOciCompanion @args | Format-List
"""
    script='param([byte[]]$Payload)\n'+entry
    boot="$ErrorActionPreference='Stop';try{$s=[IO.File]::ReadAllText($env:CLOUDRAGON_SETUP_SELF);$a='::CLOUDRAGON_SCRIPT';$b='::CLOUDRAGON_PAYLOAD';$i=$s.LastIndexOf($a,[StringComparison]::Ordinal);$j=$s.LastIndexOf($b,[StringComparison]::Ordinal);$code=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($s.Substring($i+$a.Length,$j-$i-$a.Length)));$bytes=[Convert]::FromBase64String($s.Substring($j+$b.Length));&([scriptblock]::Create($code)) -Payload $bytes}catch{Write-Host ('INSTALL FAILED: '+$_.Exception.Message);exit 1}"
    lines=['@echo off','setlocal EnableExtensions DisableDelayedExpansion','set "CLOUDRAGON_SETUP_SELF=%~f0"','echo OCI Companion 1.3.7 - Install or Update r16',r'"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -Command "'+boot+'"','set "SETUP_RESULT=%ERRORLEVEL%"','if not defined CLOUDRAGON_SETUP_NO_PAUSE pause','exit /b %SETUP_RESULT%','::CLOUDRAGON_SCRIPT']
    wrap=lambda b:'\r\n'.join(b[i:i+76] for i in range(0,len(b),76))
    cmd=('\r\n'.join(lines)+'\r\n'+wrap(base64.b64encode(script.encode()).decode())+'\r\n::CLOUDRAGON_PAYLOAD\r\n'+wrap(base64.b64encode(payload).decode())+'\r\n').encode('ascii')
    (OUT/'Install.cmd').write_bytes(cmd)
    (support/'Guide-Preview.html').write_text(entries['payload/Update-Guide.template.html'].decode().replace('{{EXTENSION_PATH}}',r'%LOCALAPPDATA%\Cloudragon\OCICompanion\extension').replace('{{INSTALL_MODE}}','new'),encoding='utf-8')
    report={'version':'1.3.7','installerRevision':16,'cmdSha256':hashlib.sha256(cmd).hexdigest(),'payloadSha256':digest,'cmdBytes':len(cmd),'runtimeChanged':True,'explorerLaunchRequested':False,'screenshots':5,'appFiles':{n[8:]:hashlib.sha256(b).hexdigest() for n,b in entries.items() if n.startswith('payload/extension/')}}
    (support/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['version','installerRevision','cmdBytes','cmdSha256','payloadSha256']}))


if __name__=='__main__':main()
