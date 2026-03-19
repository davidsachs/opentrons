#!/usr/bin/env python3
"""Quick script to inspect analyzer output."""

from analyzer.runner import ProtocolAnalyzer
from pathlib import Path
import json

analyzer = ProtocolAnalyzer(robot_ip='10.90.158.110', use_local=False)
result = analyzer.analyze(Path('test_protocol_simple.py'))

print('Commands from analyzer:')
for i, cmd in enumerate(result.commands, 1):
    print(f'\n{i}. {cmd["commandType"]}')
    if cmd['commandType'] in ['pickUpTip', 'aspirate', 'dispense', 'dropTipInPlace', 'moveToAddressableAreaForDropTip']:
        print(f'   Params: {json.dumps(cmd["params"], indent=6)}')
