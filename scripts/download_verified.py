"""Resumable small HTTPS range requests for unreliable development networks.
TLS verification stays enabled. Final checksum must match package registry metadata.
"""
import hashlib
import base64
import sys
import time
import json
import subprocess
from pathlib import Path
import requests


def download(url, destination, expected):
    session = requests.Session()
    # Ranges must address artifact bytes, not a server's compressed encoding.
    session.headers['Accept-Encoding'] = 'identity'
    probe = session.get(url, headers={'Range': 'bytes=0-0'}, timeout=30)
    probe.raise_for_status()
    size = int(probe.headers['Content-Range'].split('/')[-1])
    url = probe.url  # Resolve official redirects once, preserving HTTPS verification.
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + '.part')
    offset = min(partial.stat().st_size // 131072 * 131072, size) if partial.exists() else 0
    last_progress = time.monotonic()
    with partial.open('r+b' if partial.exists() else 'wb') as file:
        file.truncate(offset)
        file.seek(offset)
        for start in range(offset, size, 131072):
            end = min(size - 1, start + 131071)
            for attempt in range(12):
                try:
                    response = session.get(url, headers={'Range': f'bytes={start}-{end}'}, timeout=30)
                    response.raise_for_status()
                    if (response.status_code != 206 or len(response.content) != end - start + 1
                            or response.headers.get('Content-Range') != f'bytes {start}-{end}/{size}'):
                        raise ValueError('Range unsupported or incomplete')
                    file.write(response.content)
                    if time.monotonic() - last_progress > 20:
                        print(f'Downloaded {end + 1}/{size} bytes ({(end + 1) * 100 // size}%)', flush=True)
                        last_progress = time.monotonic()
                    break
                except Exception:
                    if attempt == 11:
                        raise
                    time.sleep(0.5)
    if expected.startswith('sha512-'):
        actual = 'sha512-' + base64.b64encode(hashlib.sha512(partial.read_bytes()).digest()).decode()
    elif expected.startswith('sha1:'):
        # Maven publishes SHA-1 sidecars for older artifacts. Fetch the sidecar
        # and artifact over verified HTTPS; this checks transfer integrity.
        actual = 'sha1:' + hashlib.sha1(partial.read_bytes()).hexdigest()
    else:
        actual = hashlib.sha256(partial.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError('Package checksum does not match registry')
    partial.replace(target)
    print(f'Verified download: {target.name} ({size} bytes)')


if __name__ == '__main__':
    if sys.argv[1] == 'npm':
        for spec in sys.argv[2:]:
            name, version = spec.rsplit('@', 1)
            meta = requests.get(f'https://registry.npmjs.org/{name}/{version}', timeout=30).json()
            target = Path('mobile') / (name.replace('/', '-') + '-' + meta['version'] + '.tgz')
            download(meta['dist']['tarball'], str(target), meta['dist']['integrity'])
            subprocess.run(['npm.cmd', 'cache', 'add', str(target)], check=True, shell=True)
    elif sys.argv[1] == 'pymupdf':
        meta = requests.get('https://pypi.org/pypi/pymupdf/json', timeout=30).json()
        item = next(i for i in meta['urls'] if i['filename'].endswith('cp310-abi3-win_amd64.whl'))
        download(item['url'], str(Path(sys.argv[2]) / item['filename']), item['digests']['sha256'])
    else:
        download(*sys.argv[1:])
