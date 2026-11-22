#!/usr/bin/env python3
"""Package only reviewed extension assets, helper scripts and release documents."""
import hashlib,json,pathlib,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'dist'
VERSION=json.loads((ROOT/'extension/manifest.json').read_text())['version']
def write_zip(path,entries):
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for source,name in sorted(entries,key=lambda x:x[1]):
            if source.is_symlink() or not source.is_file():raise ValueError('Regular release files only')
            info=zipfile.ZipInfo(name,(2026,11,22,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16
            z.writestr(info,source.read_bytes())
def main():
    OUT.mkdir(exist_ok=True)
    prefix=f'OCI-Login-Companion-v{VERSION}'
    files=[]
    for folder in ['extension','windows','examples']:
        for p in (ROOT/folder).rglob('*'):
            if p.is_file():files.append((p,prefix+'/'+p.relative_to(ROOT).as_posix()))
    for p in (ROOT/'docs').glob('*.txt'):files.append((p,prefix+'/'+p.name))
    write_zip(OUT/(prefix+'.zip'),files)
    write_zip(OUT/(prefix+'-webstore.zip'),[(p,p.relative_to(ROOT/'extension').as_posix()) for p in (ROOT/'extension').rglob('*') if p.is_file()])
    source=[(p,'source/'+p.relative_to(ROOT).as_posix()) for folder in ['extension','windows','examples','tests','scripts','docs'] for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    source.extend([(ROOT/n,'source/'+n) for n in ['README.md','PRODUCT.md','DESIGN.md','package.json'] if (ROOT/n).is_file()])
    write_zip(OUT/(prefix+'-source.zip'),source)
    for file in sorted(OUT.glob('*.zip')):print(file.name,file.stat().st_size,hashlib.sha256(file.read_bytes()).hexdigest())
if __name__=='__main__':main()
