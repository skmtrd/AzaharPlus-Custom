"""Check real release presence code, with an optional brief local Discord IPC check."""
import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import struct
import subprocess
import time
import urllib.request
import urllib.error

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('source', type=Path)
parser.add_argument('msys', type=Path)
parser.add_argument('evidence', type=Path)
parser.add_argument('--live', action='store_true', help='Briefly show a test activity, then clear it')
args = parser.parse_args()
source, msys, evidence = (p.resolve() for p in (args.source, args.msys, args.evidence))
evidence.mkdir(parents=True, exist_ok=True)
stubs = evidence / 'title-stubs'
headers = {
    'common/common_types.h': '#pragma once\n#include <cstdint>\nusing s64 = std::int64_t;\nusing u64 = std::uint64_t;\n',
    'citra_qt/uisettings.h': '#pragma once\n',
    'core/core.h': '''#pragma once
#include <cstdint>
#include <string>
namespace Loader { enum class ResultStatus { Success, Error };
class AppLoader { public: std::string title; std::uint64_t program_id{}; bool program_available{true};
void ReadTitle(std::string& out) { out = title; }
ResultStatus ReadProgramId(std::uint64_t& out) { out = program_id;
return program_available ? ResultStatus::Success : ResultStatus::Error; } }; }
namespace Core { class System { public: mutable Loader::AppLoader loader;
Loader::AppLoader& GetAppLoader() const { return loader; } }; }
''',
    'core/loader/loader.h': '#pragma once\n#include "core/core.h"\n',
}
for relative, contents in headers.items():
    path = stubs / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents)
env = os.environ.copy()
env['PATH'] = str(msys / 'clang64/bin') + os.pathsep + env['PATH']
rpc = source / 'externals/discord-rpc'
rapidjson = next((rpc / 'thirdparty').glob('rapidjson-*/include'))
library = source / 'build-uds/externals/discord-rpc/src/libdiscord-rpc.a'
exe = evidence / 'verify-title.exe'
command = [str(msys / 'clang64/bin/clang++.exe'), '-std=c++20',
           '-I' + str(stubs), '-I' + str(source / 'src'),
           '-I' + str(rpc / 'include'), '-I' + str(rpc / 'src'), '-I' + str(rapidjson),
           str(Path(__file__).with_name('verify-title.cpp')),
           str(source / 'src/citra_qt/discord_impl.cpp'), str(library), '-o', str(exe)]
subprocess.run(command, env=env, check=True)
run = subprocess.run([str(exe)], env=env, capture_output=True, text=True, encoding='utf-8', check=True)
payloads = [json.loads(line) for line in run.stdout.splitlines()]
result = {'formatter_and_serialization': 'passed', 'cases': len(payloads),
          'covered': ['game switch', 'Japanese title and escaping', 'UTF-8 truncation',
                      'empty-title fallback', 'idle reset', 'pause clearing', 'member status uses name',
                      'regional artwork URLs', 'virtual-console artwork', 'unknown-title logo fallback',
                      'unavailable-title-ID fallback', 'all artwork index entries resolve']}

if args.live:
    import msvcrt
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    peek = kernel32.PeekNamedPipe
    peek.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                     ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    peek.restype = wintypes.BOOL
    pipe = None
    for index in range(10):
        try:
            pipe = open(r'\\?\pipe\discord-ipc-' + str(index), 'r+b', buffering=0)
            break
        except OSError:
            pass
    if pipe is None:
        raise SystemExit('Discord desktop IPC is unavailable')
    handle = msvcrt.get_osfhandle(pipe.fileno())
    pending = bytearray()

    def send(opcode, message):
        data = json.dumps(message, ensure_ascii=False).encode('utf-8')
        pipe.write(struct.pack('<II', opcode, len(data)) + data)

    def receive(timeout=8):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if len(pending) >= 8:
                opcode, size = struct.unpack('<II', pending[:8])
                if len(pending) >= size + 8:
                    message = json.loads(pending[8:size + 8])
                    del pending[:size + 8]
                    if opcode == 3:
                        send(4, message)
                        continue
                    return opcode, message
            available = wintypes.DWORD()
            if not peek(handle, None, 0, None, ctypes.byref(available), None):
                raise ctypes.WinError(ctypes.get_last_error())
            if available.value:
                pending.extend(pipe.read(available.value))
            else:
                time.sleep(0.02)
        raise TimeoutError('Discord IPC response timed out')

    def request(payload):
        send(1, payload)
        while True:
            opcode, reply = receive()
            if opcode == 2 or reply.get('evt') == 'ERROR':
                raise RuntimeError('Discord rejected activity: ' + str(reply.get('data', {})))
            if reply.get('nonce') == payload['nonce']:
                return reply.get('data')

    try:
        send(0, {'v': 1, 'client_id': '1345366770436800533'})
        opcode, ready = receive()
        if opcode != 1 or ready.get('evt') != 'READY':
            raise RuntimeError('Discord IPC handshake failed')
        payload = payloads[0]
        payload['args']['pid'] = os.getpid()
        payload['nonce'] = 'title-test'
        activity = request(payload)
        observed = {key: activity.get(key) for key in ('name', 'status_display_type', 'details')}
        if observed['name'] != 'AzaharPlus display test' or observed['status_display_type'] != 0:
            raise RuntimeError('Discord changed the requested title: ' + str(observed))
        result['discord_ipc'] = {'accepted': True, 'returned_activity': observed}
        image = activity.get('assets', {}).get('large_image', '')
        if not image.startswith('mp:external/'):
            raise RuntimeError('Discord did not resolve the external game image: ' + image)
        proxy_url = 'https://media.discordapp.net/' + image.removeprefix('mp:')
        result['discord_ipc']['artwork_proxy_url'] = proxy_url
        request_image = urllib.request.Request(proxy_url + '?width=128&height=128', headers={'User-Agent': 'Mozilla/5.0'})
        try:
            response = urllib.request.urlopen(request_image, timeout=12)
        except urllib.error.HTTPError as error:
            result['discord_ipc']['artwork_proxy_error'] = {'status': error.code, 'body': error.read(256).decode('utf-8', errors='replace')}
            raise
        with response:
            content_type = response.headers.get('Content-Type', '')
            image_data = response.read()
            if not content_type.startswith('image/') or len(image_data) < 100:
                raise RuntimeError('Discord image proxy returned invalid artwork')
            result['discord_ipc']['artwork_proxy'] = {
                'http_status': response.status, 'content_type': content_type, 'bytes': len(image_data)}
    finally:
        try:
            request({'cmd': 'SET_ACTIVITY', 'args': {'pid': os.getpid(), 'activity': None}, 'nonce': 'title-clear'})
        finally:
            pipe.close()
            (evidence / 'title-test.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

(evidence / 'title-test.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
