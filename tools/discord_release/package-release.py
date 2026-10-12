"""Package the clean Windows release, matching source, notices, and validation evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import zipfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('source', type=Path)
parser.add_argument('msys', type=Path)
parser.add_argument('validation', type=Path)
parser.add_argument('output', type=Path)
parser.add_argument('--name', default='azaharplus-discord-20261013-win64')
args = parser.parse_args()
source, msys, output = (p.resolve() for p in (args.source, args.msys, args.output))
name = args.name
if not name.endswith('-win64') or Path(name).name != name:
    raise SystemExit('Release name must be a single directory name ending in -win64.')
package = output / name
if package.exists():
    raise SystemExit(f'Package already exists: {package}')
validation = json.loads(args.validation.read_text(encoding='utf-8'))
if not validation.get('release_ready'):
    raise SystemExit('Validation has not marked the build ready for packaging.')
bundle = source / 'build-uds/bundle'
if not (bundle / 'azahar.exe').is_file() or (bundle / 'user').exists():
    raise SystemExit('Bundle missing or contains a private user directory.')
shutil.copytree(bundle, package)
helpers = source / 'tools/discord_release'
shutil.copyfile(helpers / 'README-ja.txt', package / 'README-ja.txt')
shutil.copyfile(source / 'LICENSE.txt', package / 'LICENSE.txt')
shutil.copytree(source / 'misc/licenses', package / 'licenses/project')
shutil.copytree(msys / 'clang64/share/licenses', package / 'licenses/runtime')
runtime_names = {p.name.lower() for p in bundle.rglob('*.dll')}
runtime_packages = []
for database in sorted((msys / 'var/lib/pacman/local').iterdir()):
    file_list = database / 'files'
    if not file_list.is_file():
        continue
    owned = [p for p in file_list.read_text(encoding='utf-8', errors='replace').splitlines()
             if Path(p).name.lower() in runtime_names]
    if not owned:
        continue
    fields = {}
    key = None
    for line in (database / 'desc').read_text(encoding='utf-8', errors='replace').splitlines():
        if line.startswith('%') and line.endswith('%'):
            key = line.strip('%')
            fields[key] = []
        elif line and key:
            fields[key].append(line)
    runtime_packages.append({
        'name': fields.get('NAME', [''])[0], 'version': fields.get('VERSION', [''])[0],
        'project_url': fields.get('URL', [''])[0], 'licenses': fields.get('LICENSE', []),
        'msys2_build_recipe': 'https://github.com/msys2/MINGW-packages/tree/master/' + fields.get('BASE', [''])[0],
        'runtime_files': owned,
    })
(package / 'licenses/runtime-packages.json').write_text(json.dumps(runtime_packages, indent=2) + '\n', encoding='utf-8')
shutil.copyfile(args.validation, package / 'validation.json')
source_dir = package / 'source'
source_dir.mkdir()
shutil.copyfile(helpers / 'BUILD-ja.txt', source_dir / 'BUILD-ja.txt')
archive_path = output / (name.removesuffix('-win64') + '-source.tar.gz')

def source_filter(member):
    parts = Path(member.name).parts[1:]
    if any(p in ('.git', '__pycache__') for p in parts) or (parts and parts[0].startswith('build-')):
        return None
    if parts and parts[0] == 'user':
        raise RuntimeError(f'Private user directory in source: {member.name}')
    return member

with tarfile.open(archive_path, 'w:gz', compresslevel=6) as archive:
    archive.add(source, arcname=name.removesuffix('-win64') + '-source', filter=source_filter)
shutil.copyfile(archive_path, source_dir / archive_path.name)

def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest().upper()

files = sorted(p for p in package.rglob('*') if p.is_file())
manifest = {
    'kind': 'discord-presence',
    'uds_kind': 'pull-result-fix',
    'source': json.loads((source / 'SOURCE.json').read_text()),
    'build_options': {'USE_DISCORD_PRESENCE': True, 'ENABLE_FFMPEG': False, 'ENABLE_LTO': False},
    'files': [{'path': p.relative_to(package).as_posix(), 'bytes': p.stat().st_size, 'sha256': digest(p)} for p in files],
}
(package / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
zip_path = output / (name + '.zip')
with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for path in sorted(p for p in package.rglob('*') if p.is_file()):
        method = zipfile.ZIP_STORED if path.suffix == '.gz' else zipfile.ZIP_DEFLATED
        archive.write(path, path.relative_to(output).as_posix(), compress_type=method)
for path in (zip_path, archive_path):
    path.with_name(path.name + '.sha256').write_text(f'{digest(path)}  {path.name}\n', encoding='ascii')
print(json.dumps({'zip': str(zip_path), 'bytes': zip_path.stat().st_size, 'sha256': digest(zip_path),
                  'source': str(archive_path), 'files': len(files)}, indent=2))
