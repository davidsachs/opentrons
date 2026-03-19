# Quick Start: Testing Protocol Translation

## TL;DR

**Fastest way to test your protocol translation:**

```bash
# With robot analyzer (most accurate)
python test_analyzer.py --protocol pickup_and_dip_labware.py --robot-ip 10.90.158.110

# With local analyzer (for development)
python test_analyzer.py --protocol pickup_and_dip_labware.py --local
```

## Available Testing Methods

You have **3 ways** to test the translation:

### 1. 🚀 Standalone Test Script (Recommended)

**File:** `test_analyzer.py`

**What it does:** Complete end-to-end test in one command

```bash
python test_analyzer.py --protocol pickup_and_dip_labware.py --robot-ip 10.90.158.110
```

**Pros:**
- One command does everything
- Clear pass/fail result
- Detailed comparison report
- Automatic cleanup

**Use when:** You want a quick, comprehensive test

---

### 2. 🛠️ CLI Commands (Built-in)

**Command:** `opentrans compare`

**What it does:** Uses the built-in CLI to compare protocols

```bash
# Step 1: Translate the protocol
opentrans translate pickup_and_dip_labware.py -o pickup_and_dip_labware_http.py

# Step 2: Compare using robot analyzer
opentrans compare pickup_and_dip_labware.py pickup_and_dip_labware_http.py --robot-ip 10.90.158.110

# Or using local analyzer
opentrans compare pickup_and_dip_labware.py pickup_and_dip_labware_http.py --local

# Save comparison report
opentrans compare pickup_and_dip_labware.py pickup_and_dip_labware_http.py --robot-ip 10.90.158.110 -o report.json
```

**Pros:**
- Uses official CLI
- Flexible workflow
- Can inspect translated file
- Multiple commands available

**Use when:** You want fine-grained control over each step

---

### 3. 🔬 Manual HTTP API Script (Educational)

**File:** `test_analyzer_manual.py`

**What it does:** Shows exactly what's happening at the HTTP API level

```bash
python test_analyzer_manual.py --protocol pickup_and_dip_labware.py --robot-ip 10.90.158.110 --verbose
```

**Pros:**
- See raw HTTP requests/responses
- Understand the analyzer API
- Good for debugging
- Educational

**Use when:** You want to understand how the analyzer API works

---

## Quick Comparison

| Method | Commands | Speed | Detail | Best For |
|--------|----------|-------|--------|----------|
| `test_analyzer.py` | 1 | ⚡⚡⚡ | ⭐⭐⭐ | Quick validation |
| CLI commands | 2+ | ⚡⚡ | ⭐⭐ | Manual workflow |
| `test_analyzer_manual.py` | 1 | ⚡ | ⭐⭐⭐⭐ | Learning/debugging |

## Your Example Workflow

Based on your original request, here's how to replicate your curl-based workflow:

### Original (Your curl commands):

```bash
# 1. Upload original protocol
curl -X POST "http://10.90.158.110:31950/protocols" \
  -H "Opentrons-Version: 3" \
  -F "files=@pickup_and_dip_labware.py"

# Returns: {"data":{"id":"7ca041be-...", "analysisSummaries":[{"id":"1368c0e0-..."}]}}

# 2. Get analysis
curl -X GET "http://10.90.158.110:31950/protocols/7ca041be-.../analyses/1368c0e0-..." \
  -H "Opentrons-Version: 3"

# 3. Repeat for translated version...
# 4. Compare manually
```

### Automated (Using our scripts):

```bash
# Single command replaces all of the above!
python test_analyzer_manual.py --protocol pickup_and_dip_labware.py --robot-ip 10.90.158.110
```

This will:
1. ✓ Upload original protocol
2. ✓ Get analysis ID and fetch results
3. ✓ Translate protocol
4. ✓ Upload translated protocol
5. ✓ Get analysis and fetch results
6. ✓ Compare and normalize commands
7. ✓ Save all results to JSON files
8. ✓ Clean up uploaded protocols

## Expected Output

### ✅ Success

```
╭─────────────────────────────────────────────────╮
│ ✓ SUCCESS: Protocols produce identical         │
│ commands!                                       │
╰─────────────────────────────────────────────────╯

  Original commands: 2
  Translated commands: 2

Test PASSED ✓
```

### ❌ Failure

```
╭─────────────────────────────────────────────────╮
│ ✗ FAILURE: Found 3 differences                 │
╰─────────────────────────────────────────────────╯

Differences by Category
┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━┓
┃ Category             ┃ Count ┃
┡━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━┩
│ Different parameters │     3 │
└──────────────────────┴───────┘

Test FAILED ✗
See report at: test_results/pickup_and_dip_labware_comparison_report.json
```

## Output Files

All test methods create these files in `test_results/`:

```
test_results/
├── pickup_and_dip_labware_comparison_report.json  # Detailed comparison
├── pickup_and_dip_labware_original_analysis.json  # Original protocol analysis
└── pickup_and_dip_labware_translated_analysis.json # Translated protocol analysis
```

## Common Commands

```bash
# Test a simple protocol first
python test_analyzer.py --protocol tests/fixtures/simple_protocol.py --robot-ip 10.90.158.110

# Test with verbose output
python test_analyzer.py --protocol pickup_and_dip_labware.py --robot-ip 10.90.158.110 --verbose

# Keep the translated file for inspection
python test_analyzer.py --protocol pickup_and_dip_labware.py --robot-ip 10.90.158.110 --keep-translated

# Use local analyzer (offline testing)
python test_analyzer.py --protocol pickup_and_dip_labware.py --local

# Test multiple protocols
for protocol in tests/fixtures/*.py; do
    python test_analyzer.py --protocol "$protocol" --robot-ip 10.90.158.110
done
```

## Troubleshooting

### Can't connect to robot

```bash
# Check robot is reachable
ping 10.90.158.110

# Check port is open
curl http://10.90.158.110:31950/health
```

### Want to see what's being sent

```bash
# Use manual script with verbose flag
python test_analyzer_manual.py --protocol pickup_and_dip_labware.py --robot-ip 10.90.158.110 --verbose
```

### opentrans command not found

```bash
# Install the package
pip install -e .

# Or use Python module syntax
python -m opentrons_translator.cli translate ...
```

## Next Steps

1. ✅ **Run your first test** with `pickup_and_dip_labware.py`
2. 📊 **Check the results** in `test_results/`
3. 🔧 **Fix any differences** found
4. ♻️ **Re-test** until protocols match
5. 🎉 **Test on real robot** (when ready)

For more details, see [TESTING.md](TESTING.md).
