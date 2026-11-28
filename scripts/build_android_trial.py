#!/usr/bin/env python3
"""Package committed runtime bytes with Chromium's CRX3 packer.

The reusable signing key must be private and outside this repository. The
result is an Android Nightly trial, not a claim of Android device validation.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def run(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, **kwargs).stdout


def git(*args):
    return run(['git', *args], cwd=ROOT)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fields(data):
    """Read length-delimited fields in Chromium's small CRX3 protobuf header."""
    pos = 0

    def varint():
        nonlocal pos
        value = 0
        for shift in range(0, 70, 7):
            if pos >= len(data):
                raise ValueError('Truncated protobuf')
            byte = data[pos]
            pos += 1
            value |= (byte & 127) << shift
            if byte < 128:
                return value
        raise ValueError('Oversized protobuf integer')

    result = {}
    while pos < len(data):
        tag = varint()
        if tag & 7 != 2:
            raise ValueError('Unexpected CRX3 field encoding')
        size = varint()
        if size > len(data) - pos:
            raise ValueError('Truncated CRX3 field')
        result.setdefault(tag >> 3, []).append(data[pos:pos + size])
        pos += size
    return result


def verify_crx(blob, expected, temp):
    if len(blob) < 12 or blob[:4] != b'Cr24':
        raise ValueError('Not a CRX file')
    version, size = struct.unpack('<II', blob[4:12])
    if version != 3 or not 0 < size <= 65536 or len(blob) <= 12 + size:
        raise ValueError('Invalid CRX3 header')
    header = fields(blob[12:12 + size])
    signed, = header[10000]
    proof_blob, = header[2]
    proof = fields(proof_blob)
    public, = proof[1]
    signature, = proof[2]
    crx_id, = fields(signed)[1]
    if hashlib.sha256(public).digest()[:16] != crx_id:
        raise ValueError('CRX signing identity mismatch')
    payload = blob[12 + size:]
    (temp / 'public.der').write_bytes(public)
    (temp / 'signature').write_bytes(signature)
    (temp / 'signed-data').write_bytes(
        b'CRX3 SignedData\0' + struct.pack('<I', len(signed)) + signed + payload)
    run(['openssl', 'pkey', '-pubin', '-inform', 'DER', '-in', str(temp / 'public.der'),
         '-out', str(temp / 'public.pem')])
    run(['openssl', 'dgst', '-sha256', '-verify', str(temp / 'public.pem'),
         '-signature', str(temp / 'signature'), str(temp / 'signed-data')])
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = [n for n in archive.namelist() if not n.endswith('/')]
        if len(names) != len(set(names)) or set(names) != set(expected):
            raise ValueError('CRX file list differs from committed runtime')
        if archive.testzip() is not None:
            raise ValueError('CRX ZIP checksum failure')
        for name, original in expected.items():
            if archive.read(name) != original:
                raise ValueError('CRX runtime differs from source: ' + name)
    extension_id = ''.join(chr(ord('a') + int(digit, 16)) for digit in crx_id.hex())
    return payload, extension_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chromium', required=True, type=Path)
    parser.add_argument('--key', required=True, type=Path)
    parser.add_argument('--out', type=Path, default=ROOT / 'dist/android-nightly-test1')
    args = parser.parse_args()
    key = args.key.resolve(strict=True)
    if key.is_relative_to(ROOT) or not key.is_file():
        raise ValueError('The signing key must be outside the repository')
    if os.name == 'posix' and (key.stat().st_mode & 0o077 or key.stat().st_uid != os.getuid()):
        raise ValueError('The signing key must be owned by this user and private (0600)')
    source = git('rev-parse', 'HEAD').decode().strip()
    expected = {}
    for record in git('ls-tree', '-rz', source, '--', 'extension/').split(b'\0'):
        if not record:
            continue
        meta, path = record.split(b'\t', 1)
        mode, kind, object_id = meta.split()
        name = path.decode().removeprefix('extension/')
        if mode not in (b'100644', b'100755') or kind != b'blob':
            raise ValueError('Only committed regular runtime files may be packaged')
        expected[name] = git('cat-file', 'blob', object_id.decode())
    manifest = json.loads(expected['manifest.json'])
    version = manifest['version']
    prefix = f'OCI-Companion-{version}-Android-Nightly-test1'
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='android-pack-', dir=out.parent) as folder:
        temp = Path(folder)
        extension = temp / 'extension'
        for name, data in expected.items():
            target = extension / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            os.utime(target, (1795824000, 1795824000))
        run([str(args.chromium.resolve()), '--headless=new', '--no-sandbox',
             '--disable-gpu', '--no-first-run', '--no-default-browser-check',
             '--user-data-dir=' + str(temp / 'packer-profile'),
             '--pack-extension=' + str(extension), '--pack-extension-key=' + str(key)], timeout=60)
        crx = (temp / 'extension.crx').read_bytes()
        payload, extension_id = verify_crx(crx, expected, temp)
    guide = git('show', source + ':docs/ANDROID-NIGHTLY.md').decode().replace(
        '{{EXTENSION_ID}}', extension_id).encode()
    files = {prefix + '.crx': crx, prefix + '.zip': payload, 'ANDROID-NIGHTLY.txt': guide}
    receipt = {
        'version': version, 'trial': 1, 'sourceCommit': source,
        'runtimeCommit': git('log', '-1', '--format=%H', source, '--', 'extension/').decode().strip(),
        'extensionId': extension_id, 'crxFormat': 3,
        'chromiumPackerAndIndependentOpenSSLSignatureVerified': True,
        'zipIsExactCrxPayload': True, 'allRuntimeBytesMatchCommittedSource': True,
        'runtimeFileCount': len(expected), 'privateKeyIncluded': False,
        'androidDeviceInstallVerified': False, 'androidOCILoginVerified': False,
        'androidOneDriveSyncVerified': False, 'windowsRuntimeChanged': False,
        'files': [{'path': n, 'bytes': len(b), 'sha256': sha(b)} for n, b in files.items()],
        'runtime': [{'path': n, 'bytes': len(b), 'sha256': sha(b)} for n, b in sorted(expected.items())],
    }
    files['android-package-manifest.json'] = (json.dumps(receipt, ensure_ascii=False, indent=2) + '\n').encode()
    files['SHA256SUMS.txt'] = ''.join(sha(b) + '  ' + n + '\n' for n, b in files.items()).encode()
    for name, data in files.items():
        target = out / name
        if target.exists():
            if target.read_bytes() != data:
                raise ValueError('Preserving a different existing output: ' + name)
        else:
            with target.open('xb') as stream:
                stream.write(data)
    print(json.dumps({'version': version, 'extensionId': extension_id,
                      'runtimeFiles': len(expected), 'crxBytes': len(crx), 'output': str(out)}))


if __name__ == '__main__':
    main()
