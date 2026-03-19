#!/usr/bin/env python3
"""Check what commands the gripper protocol generates."""

from analyzer.runner import ProtocolAnalyzer
from pathlib import Path
import json

analyzer = ProtocolAnalyzer(robot_ip='10.90.158.110', use_local=False)
result = analyzer.analyze(Path('test_gripper_movement.py'))

print(f'Total commands: {len(result.commands)}')
print('\nCommands:')
for i, cmd in enumerate(result.commands, 1):
    print(f'\n{i}. {cmd["commandType"]}')
    # Show params for robot/moveTo and labware commands
    if 'robot/moveTo' in cmd['commandType'] or 'labware' in cmd['commandType'].lower():
        print(f'   Params: {json.dumps(cmd["params"], indent=6)}')
