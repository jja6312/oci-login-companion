#!/usr/bin/env python3
"""Build the reviewed, offline updater for the fixed-path r1/r2 installation."""
import base64,hashlib,json,pathlib,re,zipfile,io
ROOT=pathlib.Path(__file__).resolve().parents[1];OUT=ROOT/'dist/windows-update-r3';OUT.mkdir(exist_ok=True)
VERSION='1.1.1';NEW=ROOT/'dist/OCI-Login-Companion-v1.1.1-webstore.zip';OLD=ROOT/'dist/windows-setup-r2/setup-payload.zip'
NEW_SHA='c545dc4139b2dcff0eac30aea897459519dc572bd27fcd8adc73c2ed95cc4b17';OLD_SHA='6382b30e06e691e2fde40cc6ddc084c7e13073b7fe66610af01cad9d0c7101ed'
def sha(b):return hashlib.sha256(b).hexdigest()
def minify(source):
 text=' '.join(x.strip() for x in source.splitlines() if x.strip() and not x.lstrip().startswith('#'));parts=re.split("('(?:[^']|'')*')",text)
 for i in range(0,len(parts),2):parts[i]=re.sub(r'\s*([=;{},()|])\s*',r'\1',parts[i])
 return ''.join(parts)
def save(p,data):
 if p.exists() and p.read_bytes()!=data:raise RuntimeError('Preserve differing existing output: '+str(p))
 p.write_bytes(data)
def main():
 old=OLD.read_bytes();new=NEW.read_bytes();assert sha(old)==OLD_SHA and sha(new)==NEW_SHA
 with zipfile.ZipFile(io.BytesIO(old)) as z:baseline={'payloadSha256':OLD_SHA,'files':{n[8:]:sha(z.read(n)) for n in z.namelist() if n.startswith('payload/extension/')}}
 with zipfile.ZipFile(io.BytesIO(new)) as z:entries={'payload/extension/'+n:z.read(n) for n in z.namelist()};assert z.testzip() is None
 entries['payload/baseline.json']=(json.dumps(baseline,sort_keys=True,separators=(',',':'))+'\n').encode();entries['payload/Update-Guide.template.html']=(ROOT/'windows/update/Update-Guide.template.html').read_bytes()
 data=io.BytesIO()
 with zipfile.ZipFile(data,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for name,body in sorted(entries.items()):
   info=zipfile.ZipInfo(name,(2026,11,22,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16;z.writestr(info,body)
 payload=data.getvalue();digest=sha(payload);core=minify((ROOT/'windows/update/Update.Core.ps1').read_text())
 load="$ErrorActionPreference='Stop';try{$s=[IO.File]::ReadAllText($env:OCI_COMPANION_UPDATE_SELF);$t='::OCI_UPDATE_PAYLOAD';$i=$s.LastIndexOf($t,[StringComparison]::Ordinal);if($i-lt 0-or $s.Length-gt 2097152){throw 'Invalid update file';};$b=[Convert]::FromBase64String($s.Substring($i+$t.Length));"
 end="Update-OciCompanion -Payload $b -ExpectedHash '"+digest+"'|Format-List;}catch{Write-Host ('UPDATE FAILED: '+$_.Exception.Message);exit 1;};"
 command=load+core+end;assert '"' not in command and '%' not in command
 invocation=r'"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -Command "'+command+'"';assert len(invocation)<7900, len(invocation)
 lines=['@echo off','setlocal EnableExtensions DisableDelayedExpansion','set "OCI_COMPANION_UPDATE_SELF=%~f0"','echo OCI Companion 1.1.1 Update r3 - keep existing browser accounts',invocation,'set "OCI_UPDATE_EXIT=%ERRORLEVEL%"','if not "%OCI_UPDATE_EXIT%"=="0" (','echo Update did not complete. Existing files were preserved or a backup was retained.',') else (','echo Use the same browser and profile. Click Reload on the existing extension card.',')','pause','exit /b %OCI_UPDATE_EXIT%','::OCI_UPDATE_PAYLOAD']
 encoded=base64.b64encode(payload).decode();cmd=('\r\n'.join(lines)+'\r\n'+'\r\n'.join(encoded[i:i+76] for i in range(0,len(encoded),76))+'\r\n').encode('ascii')
 save(OUT/'OCI-Companion-v1.1.1-Windows-Update-r3.cmd',cmd);save(OUT/'update-payload.zip',payload)
 report={'version':VERSION,'revision':3,'cmdBytes':len(cmd),'cmdSha256':sha(cmd),'commandLineCharacters':len(invocation),'payloadSha256':digest,'oldPayloadSha256':OLD_SHA,'newExtensionZipSha256':NEW_SHA,'files':{n:sha(b) for n,b in sorted(entries.items())},'policyChanges':False,'profileStorageEdits':False,'registration':'Reload existing card; do not remove extension'}
 (OUT/'build-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['cmdBytes','cmdSha256','commandLineCharacters']}))
if __name__=='__main__':main()
