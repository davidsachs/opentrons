# Test Infrastructure Summary

## Question: Does a test script exist?

**Answer: YES! You have comprehensive testing infrastructure already in place.**

## What Exists

### 1. Core Analyzer Infrastructure ✅

**Location:** `analyzer/`

- **`runner.py`**: Protocol analyzer that can use either local CLI or robot HTTP API
- **`compare.py`**: Protocol comparator that normalizes and compares command sequences

These are production-ready and used by the CLI.

### 2. CLI Testing Commands ✅

**Command:** `opentrans compare`

```bash
opentrans compare original.py translated.py --robot-ip 10.90.158.110
```

Built-in testing via the official CLI tool.

### 3. Unit Test Suite ✅

**Location:** `tests/`

- `test_parser.py` - AST parsing tests
- `test_mapping.py` - Command mapping tests
- `test_generator.py` - Code generation tests
- `test_integration.py` - End-to-end translation tests

Run with: `pytest`

## What Was Added

### 1. End-to-End Test Script ⭐ NEW

**File:** `test_analyzer.py`

Complete automated test that:
- Translates a protocol
- Analyzes both versions (original and translated)
- Compares results
- Generates reports
- Exits with pass/fail code

**Usage:**
```bash
python test_analyzer.py --protocol pickup_and_dip_labware.py --robot-ip 10.90.158.110
```

### 2. Manual HTTP API Test ⭐ NEW

**File:** `test_analyzer_manual.py`

Educational script showing the exact HTTP API workflow from your example:
- Direct curl-like requests
- Raw JSON responses
- Step-by-step output

**Usage:**
```bash
python test_analyzer_manual.py --protocol pickup_and_dip_labware.py --robot-ip 10.90.158.110
```

### 3. Documentation ⭐ NEW

- **`QUICKSTART_TESTING.md`**: Quick start guide with examples
- **`TESTING.md`**: Comprehensive testing documentation
- **`TEST_SUMMARY.md`**: This file

## How to Run Tests

### Method 1: Quick Test (Recommended)

```bash
# One command to test everything
python test_analyzer.py --protocol pickup_and_dip_labware.py --robot-ip 10.90.158.110
```

**Output:**
```
✓ SUCCESS: Protocols produce identical commands!
Test PASSED ✓
```

### Method 2: Using CLI

```bash
# Step 1: Translate
opentrans translate pickup_and_dip_labware.py

# Step 2: Compare
opentrans compare pickup_and_dip_labware.py pickup_and_dip_labware_http.py --robot-ip 10.90.158.110
```

### Method 3: Unit Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=opentrons_translator
```

## Your Workflow (Automated)

Your original curl-based workflow:

```bash
# 1. Upload protocol
curl -X POST "http://10.90.158.110:31950/protocols" -H "Opentrons-Version: 3" -F "files=@pickup_and_dip_labware.py"

# 2. Get protocol and analysis IDs from response

# 3. Fetch analysis
curl -X GET "http://10.90.158.110:31950/protocols/{protocol_id}/analyses/{analysis_id}" -H "Opentrons-Version: 3"

# 4. Repeat for translated version

# 5. Compare JSONs manually
```

**Now automated as:**

```bash
python test_analyzer.py --protocol pickup_and_dip_labware.py --robot-ip 10.90.158.110
```

Or for detailed HTTP output:

```bash
python test_analyzer_manual.py --protocol pickup_and_dip_labware.py --robot-ip 10.90.158.110 --verbose
```

## What Gets Tested

### Translation Pipeline
1. **Parse** Python protocol (AST analysis)
2. **Map** commands (Python API → HTTP API)
3. **Generate** executable HTTP code
4. **Analyze** both protocols via robot/local analyzer
5. **Compare** normalized command sequences

### Normalization (for comparison)
- Removes runtime-specific IDs
- Removes timestamps
- Rounds floats to 6 decimals
- Preserves command types and parameters

### Pass Criteria
✅ Same number of commands
✅ Same command types in same order
✅ Same parameters (normalized)

## Example Test Run

```bash
$ python test_analyzer.py --protocol pickup_and_dip_labware.py --robot-ip 10.90.158.110

╭────────────────────────────────────────────────╮
│ Opentrons Protocol Analyzer Test              │
│                                                │
│ Protocol: pickup_and_dip_labware.py            │
│ Analyzer: Robot at 10.90.158.110              │
│ Output: test_results                           │
╰────────────────────────────────────────────────╯

Step 1: Translating Protocol
  Original: pickup_and_dip_labware.py
  Translated: pickup_and_dip_labware_http.py
  ✓ Translation complete

Step 3: Comparing Analysis Results

╭────────────────────────────────────────────────╮
│ ✓ SUCCESS: Protocols produce identical        │
│ commands!                                      │
╰────────────────────────────────────────────────╯

  Original commands: 2
  Translated commands: 2

Step 4: Saving Report
  ✓ Report saved to: test_results/pickup_and_dip_labware_comparison_report.json

Test PASSED ✓
```

## Files Generated

```
test_results/
├── pickup_and_dip_labware_comparison_report.json
├── pickup_and_dip_labware_original_analysis.json
└── pickup_and_dip_labware_translated_analysis.json
```

## Next Steps

1. **Run first test:**
   ```bash
   python test_analyzer.py --protocol pickup_and_dip_labware.py --robot-ip 10.90.158.110
   ```

2. **Check results** in `test_results/` directory

3. **If tests pass**: Translation is working correctly! ✅

4. **If tests fail**: Review the comparison report to see what differs

5. **Test more protocols**:
   ```bash
   python test_analyzer.py --protocol tests/fixtures/simple_protocol.py --robot-ip 10.90.158.110
   python test_analyzer.py --protocol tests/fixtures/complex_protocol.py --robot-ip 10.90.158.110
   ```

## Important Notes

### Robot Testing
- **Does NOT move the robot** - only analyzes protocols
- Safe to run - no physical operations performed
- Robot must be on and connected to network
- Uses port 31950 (HTTP API)

### Local Testing
- Requires `opentrons` package: `pip install opentrons`
- Good for offline development
- May have slight differences from robot analyzer
- Robot testing is recommended for final validation

### Comparison Logic
- Commands are normalized before comparison
- IDs are replaced with placeholders
- Order matters - commands must match exactly
- Parameters must match (after normalization)

## Documentation Index

- **[QUICKSTART_TESTING.md](QUICKSTART_TESTING.md)**: Quick start guide
- **[TESTING.md](TESTING.md)**: Comprehensive testing documentation
- **[README.md](README.md)**: Main project documentation
- **[TEST_SUMMARY.md](TEST_SUMMARY.md)**: This summary

## Support

Questions? Check:

1. **Quick examples**: [QUICKSTART_TESTING.md](QUICKSTART_TESTING.md)
2. **Detailed docs**: [TESTING.md](TESTING.md)
3. **Troubleshooting**: [TESTING.md#troubleshooting](TESTING.md#troubleshooting)
