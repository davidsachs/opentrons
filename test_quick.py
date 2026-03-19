#!/usr/bin/env python3
from analyzer.runner import ProtocolAnalyzer

analyzer = ProtocolAnalyzer()
result = analyzer.analyze('opentrons_spheroid_media_change.py')

print(f'Status: {result.status}')
print(f'Commands: {len(result.commands)}')
print(f'Labware: {len(result.labware)}')
print(f'Pipettes: {len(result.pipettes)}')

if result.errors:
    print('Errors:')
    for e in result.errors:
        print(f'  {e}')

print('Labware positions:')
for lw in result.labware:
    slot = lw.get('location', {}).get('slotName', 'N/A')
    name = lw.get('displayName', lw.get('loadName', 'Unknown'))
    print(f'  {slot}: {name}')

print('Pipettes:')
for pip in result.pipettes:
    mount = pip.get('mount', 'N/A')
    name = pip.get('pipetteName', 'Unknown')
    print(f'  {mount}: {name}')
