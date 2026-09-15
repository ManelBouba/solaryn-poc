"""Replay an exported screening result, checking frozen inputs/code/runtime first.

Usage: python Solaryn_Platform/replay_screening.py path/to/export.json
This never executes source code supplied in an export.
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / '.packages'))
from performance_service import calculate, digest


def replay(saved):
    manifest = saved['manifest']
    if digest(saved['frozen_inputs']) != manifest['inputs_sha256']:
        raise ValueError('Frozen input checksum mismatch')
    if digest(saved['configuration']) != manifest['configuration_sha256']:
        raise ValueError('Configuration checksum mismatch')
    if digest(saved['decision']) != manifest['result_sha256']:
        raise ValueError('Stored decision checksum mismatch')
    # No arbitrary path from the input is read. Compare current adapter's known
    # code manifest to the export after deterministic calculation.
    calculator = calculate
    if saved.get('model_version') == 'screening-1.1.0':
        from performance_v2 import calculate as calculator
        if digest(saved.get('visual_data')) != manifest.get('visual_data_sha256'):
            raise ValueError('Stored visual data checksum mismatch')
    elif saved.get('model_version') != 'screening-1.0.0':
        raise ValueError('Unsupported model release')
    replayed = calculator(saved['frozen_inputs'], saved['configuration'])
    if replayed['manifest']['code_sha256'] != manifest['code_sha256']:
        raise ValueError('Implementation changed; restore the recorded release before replaying')
    if replayed['manifest']['runtime'] != manifest['runtime']:
        raise ValueError('Runtime versions differ from the recorded run')
    if replayed['decision'] != saved['decision']:
        raise ValueError('Replay did not reproduce the stored decision')
    return {'status':'REPRODUCED','analysis_id':saved['id'],'result_sha256':manifest['result_sha256']}


if __name__ == '__main__':
    result = replay(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')))
    print(json.dumps(result, indent=2))
