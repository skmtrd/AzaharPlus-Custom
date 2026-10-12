"""Link a settings regression harness against the exact libraries used in the release."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('source', type=Path)
parser.add_argument('msys', type=Path)
parser.add_argument('evidence', type=Path)
args = parser.parse_args()
source, msys, evidence = (p.resolve() for p in (args.source, args.msys, args.evidence))
build = source / 'build-uds'
env = os.environ.copy()
env['PATH'] = str(msys / 'clang64/bin') + os.pathsep + str(msys / 'usr/bin') + os.pathsep + env['PATH']
commands = json.loads(subprocess.check_output([str(msys / 'clang64/bin/ninja.exe'), '-t', 'compdb', '-x'], cwd=build, env=env))
entry = next(p for p in commands if p['file'].replace('\\', '/').endswith('/configuration/configure_network.cpp'))
cpp = Path(__file__).with_name('verify-settings.cpp')
obj = evidence / 'verify-settings.obj'
command = entry['command']
command = re.sub(r'-o\s+\S+', lambda _: '-o ' + obj.as_posix(), command)
command = command.rsplit(' -c ', 1)[0] + ' -c ' + cpp.as_posix()
subprocess.run(command, cwd=build, env=env, check=True)
link = next(p['command'] for p in commands if p.get('output', '').replace('\\', '/') == 'bin/Release/azahar.exe')
link = next(part for part in link.split(' && ') if 'clang++.exe' in part)
exe = evidence / 'verify-settings.exe'
link = link.replace('-mwindows', '')
link = re.sub(r'-o\s+\S+', lambda _: '-o ' + exe.as_posix(), link)
link = re.sub(r'-Wl,--out-implib,\S+', '', link)
link = re.sub(r'src[/\\]citra_meta[/\\]CMakeFiles[/\\]citra_meta.dir[/\\][^ ]+\.obj', '', link)
link = re.sub(r'src[/\\]citra_meta[/\\]libcitra_meta\.a', '', link)
link = link.replace(' -O3', ' ' + obj.as_posix() + ' -O3', 1)
subprocess.run(link, cwd=build, env=env, check=True)
test_user = evidence / 'settings-test-user'
(test_user / 'config').mkdir(parents=True, exist_ok=True)
(test_user / 'config/qt-config.ini').write_text('[UI]\nenable_discord_presence=false\nenable_discord_presence\\default=false\n')
env['QT_PLUGIN_PATH'] = str(build / 'bundle/plugins')
env['PATH'] = str(build / 'bundle') + os.pathsep + env['PATH']
results = []
for mode in ('write-on', 'read-on', 'write-off', 'read-off'):
    result = subprocess.run([str(exe), str(test_user), mode], env=env, capture_output=True, text=True)
    results.append({'mode': mode, 'exit_code': result.returncode, 'output': result.stdout.strip(), 'stderr': result.stderr.strip()})
    if result.returncode:
        print(json.dumps(results, indent=2))
        raise SystemExit(result.returncode)
(evidence / 'settings-test.json').write_text(json.dumps(results, indent=2) + '\n')
print(json.dumps(results, indent=2))
