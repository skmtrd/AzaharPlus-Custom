"""Summarize UDS diagnostics; keep each PC's relative clock separate."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--host', type=Path, required=True)
parser.add_argument('--client', type=Path, required=True)
parser.add_argument('--out', type=Path)
args = parser.parse_args()
report = {}
for role in ('host', 'client'):
    path = getattr(args, role)
    text = path.read_bytes().replace(b'\0', b'').decode('utf-8', errors='replace')
    lines = text.splitlines()
    uds = [line for line in lines if 'Service.NWM' in line]
    diag = [line for line in uds if 'UDS_DIAG' in line]
    report[role] = {
        'file': str(path),
        'diagnostic_lines': len(diag),
        'build_markers': [line for line in diag if 'UDS_DIAG version=' in line],
        'received_payload_sizes': dict(Counter(re.findall(r'result=dequeued .*?bytes=(\d+)', '\n'.join(diag)))),
        'drops': dict(Counter(re.findall(r'result=(drop-[\w-]+)', '\n'.join(diag)))),
        'success_misclassified_as_error': [line for line in diag if re.search(r'reply=(not-connected|bad-bind|too-large) has_value=true', line)],
        'disconnects': [line for line in diag if 'disconnect ' in line or 'deauth ' in line],
        'last_states': [line for line in diag if 'UDS_DIAG state ' in line][-12:],
        'uds_errors': [line for line in uds if '<Error>' in line][-30:],
        'note': 'Timestamps are relative to this PC process. Match frame_hash/payload_hash with node/channel/length and order; repeated hashes are not unique packet IDs.',
    }
    if not diag:
        report[role]['note'] += ' No UDS_DIAG lines: this is an original build or Service.NWM:Debug is disabled.'
output = json.dumps(report, ensure_ascii=False, indent=2)
if args.out:
    args.out.write_text(output + '\n', encoding='utf-8')
else:
    print(output)
