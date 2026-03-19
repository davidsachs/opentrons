#!/usr/bin/env python3
"""
Simple test without Unicode characters or Rich formatting.
Tests translation by analyzing original protocol with robot analyzer.
"""

import sys
from pathlib import Path

from src.opentrons_translator.parser import ProtocolParser
from src.opentrons_translator.generator import HTTPGenerator
from analyzer.runner import ProtocolAnalyzer

def main():
    protocol_path = Path("pickup_and_dip_labware.py")
    robot_ip = "10.90.158.110"

    print("\n" + "="*60)
    print("OPENTRONS PROTOCOL TRANSLATION TEST")
    print("="*60)
    print(f"Protocol: {protocol_path}")
    print(f"Robot: {robot_ip}")
    print()

    # Step 1: Analyze original protocol
    print("Step 1: Analyzing original protocol with robot analyzer...")
    analyzer = ProtocolAnalyzer(robot_ip=robot_ip, use_local=False)
    result = analyzer.analyze(protocol_path)

    if result.status != "ok":
        print(f"ERROR: Analysis failed - {result.status}")
        for error in result.errors:
            print(f"  {error}")
        sys.exit(1)

    print(f"SUCCESS: Found {len(result.commands)} commands")
    print()

    # Show first few commands
    print("First 5 commands:")
    for i, cmd in enumerate(result.commands[:5], 1):
        print(f"  {i}. {cmd.get('commandType')}")
    print()

    # Step 2: Parse protocol
    print("Step 2: Parsing protocol to extract command sequence...")
    parser = ProtocolParser()
    parsed = parser.parse_file(protocol_path)

    print(f"SUCCESS: Parsed {len(parsed.commands)} commands")
    print(f"  Labware: {len(parsed.labware)}")
    print(f"  Pipettes: {len(parsed.pipettes)}")
    print(f"  Modules: {len(parsed.modules)}")
    print()

    # Step 3: Generate HTTP code
    print("Step 3: Generating HTTP API code...")
    generator = HTTPGenerator(parsed)
    http_code = generator.generate()

    # Validate it's valid Python
    try:
        compile(http_code, "<string>", "exec")
        print(f"SUCCESS: Generated {len(http_code)} characters of valid Python code")
    except SyntaxError as e:
        print(f"ERROR: Generated code has syntax errors - {e}")
        sys.exit(1)

    # Save it
    http_path = Path("pickup_and_dip_labware_http.py")
    http_path.write_text(http_code)
    print(f"Saved to: {http_path}")
    print()

    # Step 4: Summary
    print("="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Original protocol analysis: {len(result.commands)} commands")
    print(f"Parsed protocol: {len(parsed.commands)} user commands")
    print(f"Generated HTTP script: {len(http_code)} bytes")
    print()
    print("NOTE: The HTTP script cannot be analyzed by the Opentrons")
    print("analyzer because it's an execution script, not a protocol.")
    print("The analyzer only analyzes Python API protocols.")
    print()
    print("VALIDATION: Translation completed successfully!")
    print("  - Original protocol analyzed: OK")
    print("  - HTTP code generated: OK")
    print("  - HTTP code is valid Python: OK")
    print("="*60)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
