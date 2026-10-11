"""Verify the packaged file hashes and Windows PE import dependencies."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('bundle', type=Path)
parser.add_argument('--objdump', default='llvm-objdump')
args = parser.parse_args()
bundle = args.bundle.resolve()
manifest = json.loads((bundle / 'manifest.json').read_text(encoding='utf-8-sig'))
failures = []
for entry in manifest['files']:
    file = bundle / entry['path']
    if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest().upper() != entry['sha256']:
        failures.append(f"hash mismatch: {entry['path']}")
marker = f"UDS_DIAG version=1 base=cf9068844 build={manifest['kind']}".encode()
if marker not in (bundle / 'azahar.exe').read_bytes():
    failures.append('diagnostic build marker missing or wrong')
if not (bundle / 'plugins/platforms/qwindows.dll').is_file():
    failures.append('Qt Windows platform plugin missing')
files = [file for file in bundle.rglob('*') if file.suffix.lower() in ('.exe', '.dll')]
root_names = {file.name.lower() for file in bundle.iterdir() if file.is_file()}
system = Path(os.environ['SystemRoot']) / 'System32'
for file in files:
    dump = subprocess.check_output([args.objdump, '-p', str(file)], text=True, errors='replace')
    for dependency in re.findall(r'DLL Name:\s*(\S+)', dump):
        name = dependency.lower()
        if name.startswith(('api-ms-', 'ext-ms-')):
            continue  # Windows API-set contracts are resolved by the loader.
        if name in root_names or (file.parent / dependency).is_file() or (system / dependency).is_file():
            continue
        failures.append(f"{file.relative_to(bundle)}: missing import {dependency}")
print(json.dumps({'kind': manifest['kind'], 'hashed_files': len(manifest['files']),
                  'pe_files': len(files), 'failures': failures}, indent=2))
raise SystemExit(bool(failures))
