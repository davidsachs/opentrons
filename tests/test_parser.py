"""Tests for the protocol parser."""

import pytest
from pathlib import Path

from opentrons_translator.parser import (
    ProtocolParser,
    ParsedProtocol,
    CommandType,
    PipetteMount,
    RobotType,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestProtocolParser:
    """Tests for ProtocolParser class."""

    def test_parse_simple_protocol(self):
        """Test parsing a simple protocol."""
        parser = ProtocolParser()
        parsed = parser.parse_file(FIXTURES_DIR / "simple_protocol.py")

        assert parsed is not None
        assert isinstance(parsed, ParsedProtocol)

        # Check metadata
        assert parsed.metadata.protocol_name == "Simple Test Protocol"
        assert parsed.metadata.api_level == "2.19"
        assert parsed.metadata.robot_type == RobotType.FLEX

        # Check labware
        assert len(parsed.labware) == 3
        tip_rack = next(lw for lw in parsed.labware if "tiprack" in lw.load_name)
        assert tip_rack.location.slot == "A1"

        # Check pipettes
        assert len(parsed.pipettes) == 1
        pipette = parsed.pipettes[0]
        assert pipette.instrument_name == "flex_1channel_1000"
        assert pipette.mount == PipetteMount.LEFT

        # Check commands
        assert len(parsed.commands) > 0

        # Verify command types
        command_types = [cmd.command_type for cmd in parsed.commands]
        assert CommandType.LOAD_LABWARE in command_types
        assert CommandType.LOAD_PIPETTE in command_types
        assert CommandType.PICK_UP_TIP in command_types
        assert CommandType.ASPIRATE in command_types
        assert CommandType.DISPENSE in command_types
        assert CommandType.DROP_TIP in command_types

    def test_parse_complex_protocol(self):
        """Test parsing a complex protocol with modules."""
        parser = ProtocolParser()
        parsed = parser.parse_file(FIXTURES_DIR / "complex_protocol.py")

        assert parsed is not None

        # Check metadata
        assert parsed.metadata.protocol_name == "Complex Test Protocol"

        # Check modules
        assert len(parsed.modules) == 2
        module_types = [m.module_type.value for m in parsed.modules]
        assert "temperatureModuleV2" in module_types or "temperatureModuleV1" in module_types
        assert "heaterShakerModuleV1" in module_types

        # Check multiple pipettes
        assert len(parsed.pipettes) == 2

        # Check liquids
        assert len(parsed.liquids) == 2

        # Check command variety
        command_types = set(cmd.command_type for cmd in parsed.commands)
        assert CommandType.LOAD_MODULE in command_types
        assert CommandType.MIX in command_types
        assert CommandType.TRANSFER in command_types
        assert CommandType.DISTRIBUTE in command_types
        assert CommandType.CONSOLIDATE in command_types
        assert CommandType.MOVE_LABWARE in command_types

    def test_parse_metadata(self):
        """Test metadata extraction."""
        source = '''
metadata = {
    "protocolName": "Test Protocol",
    "author": "Test Author",
    "description": "Test Description",
    "apiLevel": "2.20",
}

requirements = {
    "robotType": "OT-3 Standard",
}

def run(protocol):
    pass
'''
        parser = ProtocolParser()
        parsed = parser.parse_source(source)

        assert parsed.metadata.protocol_name == "Test Protocol"
        assert parsed.metadata.author == "Test Author"
        assert parsed.metadata.description == "Test Description"
        assert parsed.metadata.api_level == "2.20"
        assert parsed.metadata.robot_type == RobotType.FLEX

    def test_parse_labware_loading(self):
        """Test labware loading extraction."""
        source = '''
metadata = {"apiLevel": "2.19"}
requirements = {"robotType": "OT-3 Standard"}

def run(protocol):
    plate = protocol.load_labware(
        "nest_96_wellplate_200ul_flat",
        "A1",
        label="My Plate"
    )
    tips = protocol.load_labware("opentrons_flex_96_tiprack_200ul", "B1")
'''
        parser = ProtocolParser()
        parsed = parser.parse_source(source)

        assert len(parsed.labware) == 2

        plate = parsed.get_labware_by_var("plate")
        assert plate is not None
        assert plate.load_name == "nest_96_wellplate_200ul_flat"
        assert plate.location.slot == "A1"
        assert plate.label == "My Plate"

        tips = parsed.get_labware_by_var("tips")
        assert tips is not None
        assert tips.location.slot == "B1"

    def test_parse_pipette_loading(self):
        """Test pipette loading extraction."""
        source = '''
metadata = {"apiLevel": "2.19"}
requirements = {"robotType": "OT-3 Standard"}

def run(protocol):
    tips = protocol.load_labware("opentrons_flex_96_tiprack_200ul", "A1")
    left_pip = protocol.load_instrument(
        "flex_1channel_1000",
        "left",
        tip_racks=[tips]
    )
    right_pip = protocol.load_instrument(
        "flex_8channel_50",
        "right"
    )
'''
        parser = ProtocolParser()
        parsed = parser.parse_source(source)

        assert len(parsed.pipettes) == 2

        left = parsed.get_pipette_by_var("left_pip")
        assert left is not None
        assert left.instrument_name == "flex_1channel_1000"
        assert left.mount == PipetteMount.LEFT

        right = parsed.get_pipette_by_var("right_pip")
        assert right is not None
        assert right.instrument_name == "flex_8channel_50"
        assert right.mount == PipetteMount.RIGHT

    def test_parse_liquid_handling_commands(self):
        """Test liquid handling command extraction."""
        source = '''
metadata = {"apiLevel": "2.19"}
requirements = {"robotType": "OT-3 Standard"}

def run(protocol):
    tips = protocol.load_labware("opentrons_flex_96_tiprack_200ul", "A1")
    plate = protocol.load_labware("nest_96_wellplate_200ul_flat", "A2")
    pipette = protocol.load_instrument("flex_1channel_1000", "left", tip_racks=[tips])

    pipette.pick_up_tip()
    pipette.aspirate(100, plate["A1"])
    pipette.dispense(100, plate["A2"])
    pipette.blow_out()
    pipette.drop_tip()
'''
        parser = ProtocolParser()
        parsed = parser.parse_source(source)

        # Filter to just the liquid handling commands
        lh_commands = [
            cmd for cmd in parsed.commands
            if cmd.command_type in (
                CommandType.PICK_UP_TIP,
                CommandType.ASPIRATE,
                CommandType.DISPENSE,
                CommandType.BLOW_OUT,
                CommandType.BLOW_OUT_IN_PLACE,
                CommandType.DROP_TIP,
                CommandType.DROP_TIP_IN_PLACE,
            )
        ]

        assert len(lh_commands) == 5

        # Verify aspirate
        aspirate = next(c for c in lh_commands if c.command_type == CommandType.ASPIRATE)
        assert aspirate.params.get("volume") == 100
        assert aspirate.pipette_var == "pipette"

    def test_parse_module_commands(self):
        """Test module command extraction."""
        source = '''
metadata = {"apiLevel": "2.19"}
requirements = {"robotType": "OT-3 Standard"}

def run(protocol):
    temp_mod = protocol.load_module("temperature module gen2", "B1")
    temp_mod.set_temperature(37)
    temp_mod.await_temperature(37)
    temp_mod.deactivate()
'''
        parser = ProtocolParser()
        parsed = parser.parse_source(source)

        # Check module was loaded
        assert len(parsed.modules) == 1
        assert parsed.modules[0].variable_name == "temp_mod"

        # Check module commands
        module_commands = [
            cmd for cmd in parsed.commands
            if cmd.command_type.value.startswith("temperatureModule")
        ]

        assert len(module_commands) == 3

    def test_parse_for_loop(self):
        """Test for loop expansion."""
        source = '''
metadata = {"apiLevel": "2.19"}
requirements = {"robotType": "OT-3 Standard"}

def run(protocol):
    tips = protocol.load_labware("opentrons_flex_96_tiprack_200ul", "A1")
    plate = protocol.load_labware("nest_96_wellplate_200ul_flat", "A2")
    pipette = protocol.load_instrument("flex_1channel_1000", "left", tip_racks=[tips])

    for i in range(3):
        pipette.pick_up_tip()
        pipette.aspirate(50, plate["A1"])
        pipette.dispense(50, plate["A2"])
        pipette.drop_tip()
'''
        parser = ProtocolParser()
        parsed = parser.parse_source(source)

        # Should have 3 iterations of 4 commands each = 12 liquid handling commands
        # Plus load commands
        pick_up_commands = [
            cmd for cmd in parsed.commands
            if cmd.command_type == CommandType.PICK_UP_TIP
        ]

        assert len(pick_up_commands) == 3

    def test_parse_delay_and_pause(self):
        """Test delay and pause command extraction."""
        source = '''
metadata = {"apiLevel": "2.19"}
requirements = {"robotType": "OT-3 Standard"}

def run(protocol):
    protocol.delay(seconds=30)
    protocol.delay(minutes=2, seconds=15)
    protocol.pause("Please check the setup")
'''
        parser = ProtocolParser()
        parsed = parser.parse_source(source)

        delay_commands = [
            cmd for cmd in parsed.commands
            if cmd.command_type == CommandType.DELAY
        ]
        assert len(delay_commands) == 2
        assert delay_commands[0].params["seconds"] == 30
        assert delay_commands[1].params["seconds"] == 135  # 2*60 + 15

        pause_commands = [
            cmd for cmd in parsed.commands
            if cmd.command_type == CommandType.PAUSE
        ]
        assert len(pause_commands) == 1
        assert pause_commands[0].params["message"] == "Please check the setup"


class TestParseSource:
    """Tests for parsing from source code string."""

    def test_minimal_protocol(self):
        """Test parsing minimal valid protocol."""
        source = '''
metadata = {"apiLevel": "2.19"}

def run(protocol):
    protocol.comment("Hello")
'''
        parser = ProtocolParser()
        parsed = parser.parse_source(source)

        assert parsed is not None
        assert len(parsed.commands) == 1
        assert parsed.commands[0].command_type == CommandType.COMMENT

    def test_empty_run_function(self):
        """Test protocol with empty run function."""
        source = '''
metadata = {"apiLevel": "2.19"}

def run(protocol):
    pass
'''
        parser = ProtocolParser()
        parsed = parser.parse_source(source)

        assert parsed is not None
        assert len(parsed.commands) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
