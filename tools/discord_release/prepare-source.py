"""Export a clean source snapshot, retaining only the release changes named below."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('repository', type=Path)
parser.add_argument('destination', type=Path)
parser.add_argument('--resume', action='store_true')
args = parser.parse_args()
repo = args.repository.resolve()
dest = args.destination.resolve()
if dest.exists() and not args.resume:
    raise SystemExit(f'Destination already exists: {dest}')
dest.mkdir(parents=True, exist_ok=True)

def git(*cmd, cwd=repo):
    return subprocess.check_output(['git', '-C', str(cwd), *cmd])

def export(directory, target):
    target.mkdir(parents=True, exist_ok=True)
    # A seekable archive lets tarfile materialize Git symlinks on Windows.
    payload = git('archive', 'HEAD', cwd=directory)
    with tarfile.open(fileobj=io.BytesIO(payload), mode='r:') as archive:
        archive.extractall(target, filter='data')

export(repo, dest)
modules = []
for line in git('submodule', 'status', '--recursive').decode().splitlines():
    revision, relative, *_ = line.strip().split()
    relative = relative.replace('\\', '/')
    export(repo / relative, dest / relative)
    modules.append({'path': relative, 'revision': revision.lstrip('+-U')})
    print(f'Exported {relative}', flush=True)

overlays = [
    'src/input_common/sdl/sdl_impl.cpp',
    'src/input_common/sdl/sdl_impl.h',
    'src/citra_qt/configuration/configure_network.cpp',
    'src/citra_qt/discord_impl.cpp',
    'src/citra_qt/discord_artwork.h',
    'src/citra_qt/discord_artwork_catalog.h',
    'misc/discord-artwork-index.json',
    'misc/licenses/3dsdb-artwork.txt',
    'misc/licenses/3dsdb-gpl3.txt',
    'externals/discord-rpc/include/discord_rpc.h',
    'externals/discord-rpc/src/serialization.cpp',
    'tools/uds_diagnostics/build-windows.ps1',
    'tools/uds_diagnostics/verify-bundle.py',
    'externals/dynarmic/src/dynarmic/ir/ir_emitter.h',
]
for relative in overlays:
    shutil.copyfile(repo / relative, dest / relative)
shutil.copytree(repo / 'tools/discord_release', dest / 'tools/discord_release', dirs_exist_ok=True)
revision = git('rev-parse', 'HEAD').decode().strip()
(dest / 'GIT-COMMIT').write_text(revision + '\n')
(dest / 'GIT-TAG').write_text('custom-discord-artwork-20261013\n')
metadata = {
    'repository': 'https://github.com/AzaharPlus/AzaharPlus',
    'local_base_commit': revision,
    'upstream_base_commit': 'cf9068844820f819a6eabbeeeb6a70d546e3e85a',
    'overlays': [{'path': p, 'sha256': hashlib.sha256((dest / p).read_bytes()).hexdigest()} for p in overlays],
    'submodules': modules,
    'excluded_working_tree_changes': 'Unrelated private Badge Lab experiments',
}
(dest / 'SOURCE.json').write_text(json.dumps(metadata, indent=2) + '\n')
print(f'Release source ready: {dest}', flush=True)
