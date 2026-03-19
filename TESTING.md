# Testing the Protocol Translator

This document explains how to test the Python-to-HTTP API translation to ensure it produces identical low-level commands.

## Overview

The translation testing workflow:

1. **Original Protocol** → Upload to analyzer → Get low-level commands
2. **Translate** Python protocol to HTTP version
3. **Translated Protocol** → Upload to analyzer → Get low-level commands
4. **Compare** the two command sequences to verify they're identical

## Test Scripts

Two test scripts are available:

### 1. `test_analyzer.py` (Recommended)

High-level test script using the built-in analyzer and comparison infrastructure.

**Features:**
- Uses existing `ProtocolAnalyzer` and `ProtocolComparator` classes
- Automatic normalization of commands for comparison
- Detailed comparison reports
- Clean, structured output

**Usage:**

```bash
# Test with robot analyzer (recommended)
python test_analyzer.py --protocol pickup_and_dip_labware.py --robot-ip 10.90.158.110

# Test with local analyzer (requires opentrons package)
python test_analyzer.py --protocol pickup_and_dip_labware.py --local

# Verbose output with custom output directory
python test_analyzer.py --protocol pickup_and_dip_labware.py --robot-ip 10.90.158.110 --output reports/ --verbose

# Keep the translated file for inspection
python test_analyzer.py --protocol pickup_and_dip_labware.py --robot-ip 10.90.158.110 --keep-translated
```

**Output:**
- Comparison report: `test_results/{protocol_name}_comparison_report.json`
- Exit code 0 if identical, 1 if differences found

### 2. `test_analyzer_manual.py` (Educational)

Low-level test script that demonstrates the raw HTTP API workflow.

**Features:**
- Shows exact HTTP API calls (like your curl examples)
- Direct `requests` library usage
- Detailed step-by-step output
- Good for understanding the API

**Usage:**

```bash
# Test with robot analyzer
python test_analyzer_manual.py --protocol pickup_and_dip_labware.py --robot-ip 10.90.158.110

# Verbose output
python test_analyzer_manual.py --protocol pickup_and_dip_labware.py --robot-ip 10.90.158.110 --verbose
```

**Output:**
- Original analysis: `test_results/{protocol_name}_original_analysis.json`
- Translated analysis: `test_results/{protocol_name}_translated_analysis.json`
- Comparison: `test_results/{protocol_name}_comparison.json`

## Example Workflow

### Using the Robot Analyzer

```bash
# 1. Run the test
python test_analyzer.py --protocol pickup_and_dip_labware.py --robot-ip 10.90.158.110

# 2. Check the output
# ✓ SUCCESS: Protocols produce identical commands!

# 3. Review the detailed report
cat test_results/pickup_and_dip_labware_comparison_report.json
```

### Using the Local Analyzer

**Note:** Requires `opentrons` package to be installed.

```bash
# 1. Install opentrons package (if not already installed)
pip install opentrons

# 2. Run the test
python test_analyzer.py --protocol pickup_and_dip_labware.py --local

# 3. Check results
cat test_results/pickup_and_dip_labware_comparison_report.json
```

## What Gets Tested

### Protocol Translation
- Metadata preservation
- Labware loading
- Pipette loading
- Module loading
- All command types (aspirate, dispense, move, etc.)
- Complex commands (transfer, distribute, consolidate)
- Module-specific commands (temperature, thermocycler, etc.)

### Command Normalization

The comparison automatically normalizes:
- **IDs**: Removed (they're different each run)
- **Timestamps**: Removed (runtime-specific)
- **Floats**: Rounded to 6 decimal places
- **Order**: Commands must be in exact order

### Expected Identical Commands

The following should be identical between original and translated:
- Command type (e.g., `aspirate`, `dispense`)
- Command parameters (volume, position, etc.)
- Command sequence order
- Number of commands

## Interpreting Results

### Success (Exit Code 0)

```
✓ SUCCESS: Protocols produce identical commands!

  Original commands: 42
  Translated commands: 42
```

The translation is working correctly!

### Failure (Exit Code 1)

```
✗ FAILURE: Found 3 differences

Differences by Category
┏━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━┓
┃ Category              ┃ Count ┃
┡━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━┩
│ Different parameters  │     2 │
│ Missing command       │     1 │
└───────────────────────┴───────┘
```

The translation has issues. Check the comparison report for details:

```bash
cat test_results/pickup_and_dip_labware_comparison_report.json
```

### Common Difference Categories

- **Different number of commands**: Translation may have missed or added commands
- **Different command types**: Wrong command mapped
- **Different parameters**: Parameters not correctly translated
- **Extra/missing commands**: Command sequence mismatch

## Troubleshooting

### Robot Connection Issues

**Error:** `Connection refused` or timeout

**Solution:**
- Check robot IP address is correct
- Ensure robot is on and connected to network
- Try pinging the robot: `ping 10.90.158.110`
- Verify port 31950 is accessible

### Analysis Timeout

**Error:** `Analysis timed out`

**Solution:**
- Complex protocols may take longer
- Check robot isn't running another protocol
- Try with a simpler protocol first

### opentrons Package Not Found

**Error:** `opentrons CLI not found`

**Solution:**
```bash
pip install opentrons
```

### Translation Errors

**Error:** `Translation failed: ...`

**Solution:**
- Check the protocol is valid Python
- Verify it uses supported API features
- Try with one of the example protocols first:
  - `tests/fixtures/simple_protocol.py`
  - `tests/fixtures/complex_protocol.py`

## Testing Multiple Protocols

To test multiple protocols:

```bash
# Test all fixture protocols
for protocol in tests/fixtures/*.py; do
    echo "Testing $protocol..."
    python test_analyzer.py --protocol "$protocol" --robot-ip 10.90.158.110
done
```

Or create a batch test script:

```python
import subprocess
from pathlib import Path

protocols = [
    "pickup_and_dip_labware.py",
    "tests/fixtures/simple_protocol.py",
    "tests/fixtures/complex_protocol.py",
]

for protocol in protocols:
    print(f"\n{'='*60}")
    print(f"Testing: {protocol}")
    print('='*60)

    result = subprocess.run([
        "python", "test_analyzer.py",
        "--protocol", protocol,
        "--robot-ip", "10.90.158.110"
    ])

    if result.returncode != 0:
        print(f"FAILED: {protocol}")
    else:
        print(f"PASSED: {protocol}")
```

## Continuous Integration

To integrate into CI/CD:

```yaml
# .github/workflows/test.yml
name: Test Protocol Translation

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v2

    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.10'

    - name: Install dependencies
      run: |
        pip install -e ".[dev]"
        pip install opentrons

    - name: Test translation with local analyzer
      run: |
        python test_analyzer.py --protocol tests/fixtures/simple_protocol.py --local
        python test_analyzer.py --protocol tests/fixtures/complex_protocol.py --local
```

## Next Steps

1. **Start Simple**: Test with `tests/fixtures/simple_protocol.py` first
2. **Test Your Protocol**: Run your actual protocol through the test
3. **Review Differences**: If there are differences, inspect the comparison report
4. **Fix Issues**: Update the translator to handle any edge cases
5. **Iterate**: Re-test until protocols produce identical commands

## Additional Resources

- [README.md](README.md) - Main project documentation
- [analyzer/runner.py](analyzer/runner.py) - Protocol analyzer implementation
- [analyzer/compare.py](analyzer/compare.py) - Comparison logic
- [src/opentrons_translator/](src/opentrons_translator/) - Translation implementation

## Support

If you encounter issues:

1. Run with `--verbose` flag for detailed output
2. Check the comparison report JSON for specifics
3. Verify the protocol works with standard Opentrons tools
4. Try simplifying the protocol to isolate the issue
