#!/usr/bin/env python3
"""Build a single offline CMD with a reviewed ZIP payload and literal PowerShell.
The PowerShell code is inline and inspectable: no IEX/EncodedCommand/policy changes.
Existing extension release ZIPs are inputs and are never rewritten by this builder.
"""
import base64,hashlib,json,pathlib,zipfile,io
ROOT=pathlib.Path(__file__).resolve().parents[1]
VERSION='1.1.0';REVISION=2;SETUP=ROOT/'windows/setup';OUT=ROOT/f'dist/windows-setup-r{REVISION}';OUT.mkdir(exist_ok=True)
RELEASE=ROOT/'dist'/f'OCI-Login-Companion-v{VERSION}.zip'
RELEASE_SHA='8df2dbaf7202cc3a925356572553d927f1d52acef2ab9576a49801239bfc09fc'
def sha(b):return hashlib.sha256(b).hexdigest()
def zip_bytes(entries):
 data=io.BytesIO()
 with zipfile.ZipFile(data,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for name,body in sorted(entries.items()):
   info=zipfile.ZipInfo(name,(2026,11,21,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16;z.writestr(info,body)
 return data.getvalue()
def write_if_identical(path,data):
 if path.exists() and path.read_bytes()!=data:raise RuntimeError('Preserve different existing build: '+str(path))
 path.write_bytes(data)
def main():
 release=RELEASE.read_bytes();assert sha(release)==RELEASE_SHA
 entries={};prefix=f'OCI-Login-Companion-v{VERSION}/'
 with zipfile.ZipFile(io.BytesIO(release)) as z:
  assert z.testzip() is None
  for n in z.namelist():
   assert n.startswith(prefix) and '..' not in pathlib.PurePosixPath(n).parts
   entries['payload/'+n[len(prefix):]]=z.read(n)
 entries['payload/Install-Guide.template.html']=(SETUP/'Install-Guide.template.html').read_bytes()
 payload=zip_bytes(entries);digest=sha(payload)
 core=' '.join(line.strip() for line in (SETUP/'Setup.Core.ps1').read_text().splitlines() if line.strip() and not line.lstrip().startswith('#'))
 load="$ErrorActionPreference='Stop'; try { $self=[IO.File]::ReadAllText($env:OCI_COMPANION_SETUP_SELF); if($self.Length -gt 2097152){throw 'Setup file is too large.';}; $tag='::OCI_PAYLOAD_BEGIN'; $pos=$self.LastIndexOf($tag,[StringComparison]::Ordinal); if($pos -lt 0){throw 'Setup payload missing.';}; $bytes=[Convert]::FromBase64String($self.Substring($pos+$tag.Length)); "
 end=" Install-OciCompanion -Payload $bytes -ExpectedHash '"+digest+"' | Format-List; } catch { Write-Host ('SETUP FAILED: '+$_.Exception.Message); exit 1; };"
 command=load+core+end
 assert '"' not in command and '%' not in command and '\n' not in command and '\r' not in command
 invocation=r'"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -Command "'+command+'"'
 assert len(invocation)<7900,('CMD command line too long',len(invocation))
 header='\r\n'.join(['@echo off','setlocal EnableExtensions DisableDelayedExpansion','set "OCI_COMPANION_SETUP_SELF=%~f0"',f'echo OCI Companion Windows Setup r{REVISION} - offline, current user',invocation,'set "OCI_COMPANION_SETUP_EXIT=%ERRORLEVEL%"','echo.','if not "%OCI_COMPANION_SETUP_EXIT%"=="0" (','echo Setup did not complete. No Chrome registration was performed.',') else (','echo Files ready. Finish Chrome registration in the browser.',')','pause','exit /b %OCI_COMPANION_SETUP_EXIT%','::OCI_PAYLOAD_BEGIN'])+'\r\n'
 encoded=base64.b64encode(payload).decode();cmd=header+'\r\n'.join(encoded[i:i+76] for i in range(0,len(encoded),76))+'\r\n'
 target=OUT/f'OCI-Companion-v{VERSION}-Windows-Setup-r{REVISION}.cmd';write_if_identical(target,cmd.encode('ascii'))
 write_if_identical(OUT/'setup-payload.zip',payload)
 report={'extensionVersion':VERSION,'setupRevision':REVISION,'releaseInputSha256':RELEASE_SHA,'payloadSha256':digest,'cmdSha256':sha(cmd.encode('ascii')),'cmdBytes':len(cmd.encode('ascii')),'commandLineCharacters':len(invocation),'payloadFiles':len(entries),'registryChanges':False,'executionPolicyChanges':False,'chromeProfileEdits':False,'chromeRegistration':'Manual Chrome developer mode / Load unpacked approval','entryFilesSha256':{k:sha(v) for k,v in sorted(entries.items())}}
 (OUT/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['cmdBytes','commandLineCharacters','payloadFiles','cmdSha256']},ensure_ascii=False))
if __name__=='__main__':main()
