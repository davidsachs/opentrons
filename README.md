# Opentrons Protocol Translator

Translates Opentrons Python API protocols to HTTP API scripts for the Flex (OT-3) robot.

## Overview

This tool parses Python protocols written using the Opentrons Protocol API v2 and generates equivalent Python scripts that use the HTTP API to achieve the same results. Both can be analyzed to verify they produce identical low-level commands.

## Project Structure

```
opentrons_api/
├── src/
│   └── opentrons_translator/
│       ├── __init__.py
│       ├── parser/              # Python API protocol parser
│       │   ├── __init__.py
│       │   ├── ast_parser.py    # AST-based protocol parsing
│       │   └── protocol_model.py # Internal representation
│       ├── mapping/             # API mapping layer
│       │   ├── __init__.py
│       │   ├── commands.py      # Command mappings
│       │   ├── labware.py       # Labware mappings
│       │   ├── modules.py       # Module mappings
│       │   └── pipettes.py      # Pipette mappings
│       ├── generator/           # HTTP API code generator
│       │   ├── __init__.py
│       │   ├── http_generator.py
│       │   └── templates.py
│       └── cli.py               # Command-line interface
├── tests/
│   ├── __init__.py
│   ├── test_parser.py
│   ├── test_mapping.py
│   ├── test_generator.py
│   ├── test_integration.py
│   └── fixtures/                # Sample protocols
├── analyzer/                    # Testing infrastructure
│   ├── __init__.py
│   ├── compare.py              # Compare analysis outputs
│   └── runner.py               # Run analyzer on both protocols
├── pyproject.toml
└── README.md
```

## Installation

```bash
# Clone or download this project
cd opentrons_api

# Install in development mode
pip install -e .

# Install with development dependencies
pip install -e ".[dev]"
```

## Usage

### Command Line Interface

The tool provides a unified CLI with multiple commands:

```bash
# Translate a protocol
opentrans translate input_protocol.py -o output_http_protocol.py

# Preview translation without writing file
opentrans translate input_protocol.py --preview

# Parse and inspect protocol structure
opentrans parse input_protocol.py

# Analyze a protocol (requires opentrons package or robot connection)
opentrans analyze input_protocol.py --local
opentrans analyze input_protocol.py --robot-ip 192.168.1.100

# Compare original and translated protocols
opentrans compare original.py translated.py --local
opentrans compare original.py translated.py --robot-ip 192.168.1.100
```

### Python API

```python
from opentrons_translator import ProtocolParser, HTTPGenerator

# Parse a protocol
parser = ProtocolParser()
parsed = parser.parse_file("my_protocol.py")

# Inspect parsed structure
print(f"Labware: {len(parsed.labware)}")
print(f"Pipettes: {len(parsed.pipettes)}")
print(f"Modules: {len(parsed.modules)}")
print(f"Commands: {len(parsed.commands)}")

# Generate HTTP API code
generator = HTTPGenerator(parsed)
http_code = generator.generate()

# Write to file
generator.generate_to_file("my_protocol_http.py")
```

### Comparing Analysis Results

To verify that the translated protocol produces identical commands:

```python
from analyzer import ProtocolComparator

comparator = ProtocolComparator(use_local=True)
result = comparator.compare("original.py", "translated.py")

if result.identical:
    print("Protocols produce identical commands!")
else:
    print(f"Found {len(result.differences)} differences")
    for diff in result.differences:
        print(f"  Command {diff.index}: {diff.reason}")

# Save detailed report
result.save_report("comparison_report.json")
```

## Supported Features

### Python API Features → HTTP API Commands

| Python API | HTTP API Command |
|------------|------------------|
| `load_labware()` | `loadLabware` |
| `load_adapter()` | `loadLabware` |
| `load_instrument()` | `loadPipette` |
| `load_module()` | `loadModule` |
| `load_trash_bin()` | `loadTrashBin` |
| `load_waste_chute()` | `loadWasteChute` |
| `pick_up_tip()` | `pickUpTip` |
| `drop_tip()` | `dropTip` / `dropTipInPlace` |
| `return_tip()` | `dropTip` |
| `aspirate()` | `aspirate` / `aspirateInPlace` |
| `dispense()` | `dispense` / `dispenseInPlace` |
| `blow_out()` | `blowout` / `blowOutInPlace` |
| `touch_tip()` | `touchTip` |
| `air_gap()` | `airGapInPlace` |
| `mix()` | Multiple `aspirate`/`dispense` |
| `transfer()` | Expanded to multiple commands |
| `distribute()` | Expanded to multiple commands |
| `consolidate()` | Expanded to multiple commands |
| `move_to()` | `moveToWell` |
| `move_labware()` | `moveLabware` |
| `home()` | `home` |
| `pause()` | `waitForResume` |
| `delay()` | `waitForDuration` |
| `comment()` | `comment` |
| `set_rail_lights()` | `setRailLights` |
| `configure_for_volume()` | `configureForVolume` |
| `configure_nozzle_layout()` | `configureNozzleLayout` |
| `define_liquid()` | `defineLiquid` |

### Module Support

#### Temperature Module
- `set_temperature()` → `temperatureModule/setTargetTemperature`
- `await_temperature()` → `temperatureModule/waitForTemperature`
- `deactivate()` → `temperatureModule/deactivate`

#### Thermocycler
- `open_lid()` → `thermocycler/openLid`
- `close_lid()` → `thermocycler/closeLid`
- `set_block_temperature()` → `thermocycler/setTargetBlockTemperature`
- `set_lid_temperature()` → `thermocycler/setTargetLidTemperature`
- `execute_profile()` → `thermocycler/runProfile`
- `deactivate_lid()` → `thermocycler/deactivateLid`
- `deactivate_block()` → `thermocycler/deactivateBlock`

#### Heater-Shaker
- `set_target_temperature()` → `heaterShaker/setTargetTemperature`
- `wait_for_temperature()` → `heaterShaker/waitForTemperature`
- `set_and_wait_for_shake_speed()` → `heaterShaker/setAndWaitForShakeSpeed`
- `open_labware_latch()` → `heaterShaker/openLabwareLatch`
- `close_labware_latch()` → `heaterShaker/closeLabwareLatch`
- `deactivate_heater()` → `heaterShaker/deactivateHeater`
- `deactivate_shaker()` → `heaterShaker/deactivateShaker`

#### Magnetic Module
- `engage()` → `magneticModule/engage`
- `disengage()` → `magneticModule/disengage`

#### Absorbance Plate Reader
- `initialize()` → `absorbanceReader/initialize`
- `open_lid()` → `absorbanceReader/openLid`
- `close_lid()` → `absorbanceReader/closeLid`
- `read()` → `absorbanceReader/read`

#### Flex Stacker
- `store()` → `flexStacker/store`
- `retrieve()` → `flexStacker/retrieve`

## Testing

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_parser.py

# Run with coverage
pytest --cov=opentrons_translator
```

## How It Works

### 1. Parsing (AST Analysis)

The parser uses Python's AST module to analyze protocol source code:
- Extracts `metadata` and `requirements` dictionaries
- Identifies the `run()` function and its parameter
- Tracks variable assignments for labware, pipettes, and modules
- Captures method calls on the protocol context and instruments
- Expands loops to capture all commands

### 2. Internal Representation

Parsed protocols are converted to a structured representation:
- `ParsedProtocol` - Complete protocol with metadata and commands
- `LoadedLabware`, `LoadedPipette`, `LoadedModule` - Resources
- `ProtocolCommand` - Individual commands with parameters

### 3. Command Mapping

Commands are mapped from Python API to HTTP API:
- Direct mappings for simple commands (1:1)
- Expansion for complex commands (`mix`, `transfer`, etc.)
- Variable resolution (converting variable names to IDs)

### 4. Code Generation

The generator produces executable Python code that:
- Creates a connection to the robot
- Manages a run session
- Executes commands via HTTP API
- Tracks resource IDs dynamically

### 5. Verification

The analyzer compares protocols by:
- Running both through the Opentrons analyzer
- Normalizing commands (removing runtime-specific data)
- Comparing command sequences
- Reporting differences

## Limitations

- **Dynamic code**: Protocols with complex runtime logic may not translate perfectly
- **Custom labware**: Custom labware definitions need to be handled separately
- **Runtime parameters**: Runtime parameters are captured but may need manual handling
- **Python features**: Advanced Python features (generators, closures) may not be fully supported

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest`
5. Submit a pull request

## License

MIT
