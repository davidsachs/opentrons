#!/usr/bin/env python3
"""
Test Parser Accuracy

Validates that the parser correctly extracts the same commands
that the Opentrons analyzer finds in the original protocol.

This is a partial validation - it confirms the parser works correctly,
but doesn't validate that the HTTP generator produces equivalent code.
"""

import sys
from pathlib import Path
from collections import Counter

from src.opentrons_translator.parser import ProtocolParser
from analyzer.runner import ProtocolAnalyzer

def normalize_command_type(cmd_type):
    """Normalize command type for comparison."""
    # The parser uses internal names, analyzer uses HTTP API names
    # Map them to common names
    mapping = {
        'LOAD_LABWARE': 'loadLabware',
        'LOAD_PIPETTE': 'loadPipette',
        'PICK_UP_TIP': 'pickUpTip',
        'ASPIRATE': 'aspirate',
        'DISPENSE': 'dispense',
        'DROP_TIP': 'dropTip',
        'HOME': 'home',
        'MOVE_TO': 'moveToWell',
        'ROBOT_MOVE_TO': 'robot/moveTo',
    }

    cmd_str = str(cmd_type).upper().replace('COMMANDTYPE.', '')
    return mapping.get(cmd_str, cmd_str.lower())

def main():
    protocol_path = Path("tests/fixtures/simple_protocol.py")
    robot_ip = "10.90.158.110"

    print("\n" + "="*70)
    print("PARSER ACCURACY TEST")
    print("="*70)
    print(f"Protocol: {protocol_path}")
    print(f"Robot: {robot_ip}")
    print()

    # Step 1: Analyze with robot
    print("Step 1: Analyzing protocol with robot analyzer...")
    analyzer = ProtocolAnalyzer(robot_ip=robot_ip, use_local=False)
    result = analyzer.analyze(protocol_path)

    if result.status != "ok":
        print(f"ERROR: Analysis failed - {result.status}")
        sys.exit(1)

    analyzer_commands = [cmd.get('commandType') for cmd in result.commands]
    print(f"SUCCESS: Robot analyzer found {len(analyzer_commands)} commands")

    # Count command types
    analyzer_counts = Counter(analyzer_commands)
    print("\nCommand breakdown:")
    for cmd_type, count in analyzer_counts.most_common():
        print(f"  {cmd_type}: {count}")
    print()

    # Step 2: Parse protocol
    print("Step 2: Parsing protocol to extract commands...")
    parser = ProtocolParser()
    parsed = parser.parse_file(protocol_path)

    parser_commands = []
    for cmd in parsed.commands:
        cmd_type = normalize_command_type(cmd.command_type)
        parser_commands.append(cmd_type)

    print(f"SUCCESS: Parser found {len(parser_commands)} commands")

    parser_counts = Counter(parser_commands)
    print("\nCommand breakdown:")
    for cmd_type, count in parser_counts.most_common():
        print(f"  {cmd_type}: {count}")
    print()

    # Step 3: Compare
    print("="*70)
    print("COMPARISON")
    print("="*70)

    # The analyzer may include setup commands like 'home' that the parser doesn't
    # So we check if parser commands are a subset of analyzer commands

    # Remove setup commands from analyzer list for comparison
    setup_commands = ['home']
    analyzer_user_commands = [c for c in analyzer_commands if c not in setup_commands]

    print(f"Analyzer commands (excluding setup): {len(analyzer_user_commands)}")
    print(f"Parser commands: {len(parser_commands)}")
    print()

    if len(parser_commands) == 0 and len(analyzer_user_commands) > 0:
        print("WARNING: Parser found no commands but analyzer did!")
        print("This could mean:")
        print("  1. The protocol has no executable commands")
        print("  2. The parser failed to extract commands")
        print("  3. All commands are commented out")
        print()
        sys.exit(1)

    # Compare command type distributions
    differences = []
    all_types = set(analyzer_counts.keys()) | set(parser_counts.keys())

    for cmd_type in sorted(all_types):
        if cmd_type in setup_commands:
            continue

        analyzer_count = analyzer_counts.get(cmd_type, 0)
        parser_count = parser_counts.get(cmd_type, 0)

        if analyzer_count != parser_count:
            differences.append((cmd_type, analyzer_count, parser_count))

    if differences:
        print("DIFFERENCES FOUND:")
        print()
        print(f"{'Command Type':<25} {'Analyzer':<12} {'Parser':<12} {'Diff':<12}")
        print("-" * 70)
        for cmd_type, analyzer_count, parser_count in differences:
            diff = parser_count - analyzer_count
            diff_str = f"{diff:+d}"
            print(f"{cmd_type:<25} {analyzer_count:<12} {parser_count:<12} {diff_str:<12}")
        print()
        print("RESULT: Parser does NOT match analyzer")
        sys.exit(1)
    else:
        print("SUCCESS: Parser command counts match analyzer!")
        print()
        print("="*70)
        print("WHAT THIS MEANS:")
        print("="*70)
        print("✓ The parser correctly extracts commands from Python protocols")
        print("✓ The command mapping layer should work correctly")
        print()
        print("LIMITATIONS:")
        print("✗ This does NOT validate the HTTP generator output")
        print("✗ This does NOT confirm the HTTP script will execute identically")
        print()
        print("To fully validate, you would need to:")
        print("  1. Run the HTTP script on an actual robot")
        print("  2. Compare physical results with original protocol")
        print("="*70)
        sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
