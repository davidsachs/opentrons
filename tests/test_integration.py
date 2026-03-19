"""Integration tests for the full translation pipeline."""

import pytest
from pathlib import Path

from opentrons_translator.parser import ProtocolParser
from opentrons_translator.generator import HTTPGenerator


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestFullTranslation:
    """Integration tests for complete protocol translation."""

    def test_translate_simple_protocol(self):
        """Test full translation of simple protocol."""
        # Parse
        parser = ProtocolParser()
        parsed = parser.parse_file(FIXTURES_DIR / "simple_protocol.py")

        assert parsed is not None
        assert len(parsed.labware) > 0
        assert len(parsed.pipettes) > 0
        assert len(parsed.commands) > 0

        # Generate
        generator = HTTPGenerator(parsed)
        http_code = generator.generate()

        assert http_code is not None
        assert len(http_code) > 1000  # Should be substantial

        # Verify code is valid Python
        compile(http_code, "<string>", "exec")

        # Check key elements are present
        assert "HTTPProtocolRunner" in http_code
        assert "execute_protocol" in http_code
        assert "run_protocol" in http_code
        assert "load_labware" in http_code
        assert "load_pipette" in http_code
        assert "aspirate" in http_code
        assert "dispense" in http_code

    def test_translate_complex_protocol(self):
        """Test full translation of complex protocol."""
        # Parse
        parser = ProtocolParser()
        parsed = parser.parse_file(FIXTURES_DIR / "complex_protocol.py")

        assert parsed is not None
        assert len(parsed.modules) > 0
        assert len(parsed.pipettes) > 0

        # Generate
        generator = HTTPGenerator(parsed)
        http_code = generator.generate()

        # Verify code is valid Python
        compile(http_code, "<string>", "exec")

        # Check module-specific elements
        assert "load_module" in http_code

    def test_round_trip_metadata_preservation(self):
        """Test that metadata is preserved through translation."""
        source = '''
metadata = {
    "protocolName": "My Special Protocol",
    "author": "Dr. Scientist",
    "description": "A very important protocol",
    "apiLevel": "2.19",
}
requirements = {"robotType": "OT-3 Standard"}

def run(protocol):
    protocol.comment("Hello")
'''
        # Parse
        parser = ProtocolParser()
        parsed = parser.parse_source(source)

        assert parsed.metadata.protocol_name == "My Special Protocol"
        assert parsed.metadata.author == "Dr. Scientist"
        assert parsed.metadata.api_level == "2.19"

        # Generate
        generator = HTTPGenerator(parsed)
        http_code = generator.generate()

        # Check metadata appears in generated code
        assert "My Special Protocol" in http_code
        assert "2.19" in http_code

    def test_command_count_consistency(self):
        """Test that command counts are reasonable after translation."""
        source = '''
metadata = {"apiLevel": "2.19"}
requirements = {"robotType": "OT-3 Standard"}

def run(protocol):
    tips = protocol.load_labware("opentrons_flex_96_tiprack_200ul", "A1")
    plate = protocol.load_labware("nest_96_wellplate_200ul_flat", "A2")
    pipette = protocol.load_instrument("flex_1channel_1000", "left", tip_racks=[tips])

    # 5 iterations
    for i in range(5):
        pipette.pick_up_tip()
        pipette.aspirate(100, plate["A1"])
        pipette.dispense(100, plate["A2"])
        pipette.drop_tip()
'''
        parser = ProtocolParser()
        parsed = parser.parse_source(source)

        # Should have 5 pick_up_tip commands
        pick_ups = [c for c in parsed.commands if "PICK_UP" in c.command_type.name]
        assert len(pick_ups) == 5

        # Should have 5 aspirate commands
        aspirates = [c for c in parsed.commands if c.command_type.name == "ASPIRATE"]
        assert len(aspirates) == 5

    def test_translation_with_all_liquid_operations(self):
        """Test translation includes all liquid handling operations."""
        source = '''
metadata = {"apiLevel": "2.19"}
requirements = {"robotType": "OT-3 Standard"}

def run(protocol):
    tips = protocol.load_labware("opentrons_flex_96_tiprack_200ul", "A1")
    plate = protocol.load_labware("nest_96_wellplate_200ul_flat", "A2")
    reservoir = protocol.load_labware("nest_12_reservoir_15ml", "A3")
    pipette = protocol.load_instrument("flex_1channel_1000", "left", tip_racks=[tips])

    pipette.pick_up_tip()

    # Aspirate
    pipette.aspirate(100, reservoir["A1"])

    # Touch tip
    pipette.touch_tip()

    # Air gap
    pipette.air_gap(20)

    # Move
    pipette.move_to(plate["A1"].top())

    # Dispense
    pipette.dispense(100, plate["A1"])

    # Blow out
    pipette.blow_out()

    # Mix
    pipette.mix(3, 50, plate["A1"])

    pipette.drop_tip()
'''
        parser = ProtocolParser()
        parsed = parser.parse_source(source)

        generator = HTTPGenerator(parsed)
        http_code = generator.generate()

        # Verify all operations are in generated code
        assert "aspirate" in http_code
        assert "dispense" in http_code
        assert "touch_tip" in http_code
        assert "blow_out" in http_code
        # Mix is expanded
        assert "for _ in range(3)" in http_code


class TestTranslationEdgeCases:
    """Tests for edge cases in translation."""

    def test_empty_protocol(self):
        """Test translation of minimal protocol."""
        source = '''
metadata = {"apiLevel": "2.19"}
requirements = {"robotType": "OT-3 Standard"}

def run(protocol):
    pass
'''
        parser = ProtocolParser()
        parsed = parser.parse_source(source)

        generator = HTTPGenerator(parsed)
        http_code = generator.generate()

        # Should still produce valid code
        compile(http_code, "<string>", "exec")

    def test_protocol_with_only_comments(self):
        """Test protocol with only comment commands."""
        source = '''
metadata = {"apiLevel": "2.19"}
requirements = {"robotType": "OT-3 Standard"}

def run(protocol):
    protocol.comment("Step 1")
    protocol.comment("Step 2")
    protocol.comment("Step 3")
'''
        parser = ProtocolParser()
        parsed = parser.parse_source(source)

        generator = HTTPGenerator(parsed)
        http_code = generator.generate()

        assert "Step 1" in http_code
        assert "Step 2" in http_code
        assert "Step 3" in http_code

    def test_multiple_tip_racks(self):
        """Test protocol with multiple tip racks."""
        source = '''
metadata = {"apiLevel": "2.19"}
requirements = {"robotType": "OT-3 Standard"}

def run(protocol):
    tips1 = protocol.load_labware("opentrons_flex_96_tiprack_200ul", "A1")
    tips2 = protocol.load_labware("opentrons_flex_96_tiprack_200ul", "A2")
    tips3 = protocol.load_labware("opentrons_flex_96_tiprack_200ul", "A3")
    pipette = protocol.load_instrument(
        "flex_1channel_1000",
        "left",
        tip_racks=[tips1, tips2, tips3]
    )
'''
        parser = ProtocolParser()
        parsed = parser.parse_source(source)

        assert len(parsed.labware) == 3

        generator = HTTPGenerator(parsed)
        http_code = generator.generate()
        compile(http_code, "<string>", "exec")

    def test_labware_on_adapters(self):
        """Test labware loaded on adapters."""
        source = '''
metadata = {"apiLevel": "2.19"}
requirements = {"robotType": "OT-3 Standard"}

def run(protocol):
    adapter = protocol.load_adapter("opentrons_flex_96_tiprack_adapter", "A1")
    tips = protocol.load_labware(
        "opentrons_flex_96_tiprack_200ul",
        adapter
    )
'''
        parser = ProtocolParser()
        parsed = parser.parse_source(source)

        assert len(parsed.labware) == 2

        generator = HTTPGenerator(parsed)
        http_code = generator.generate()
        compile(http_code, "<string>", "exec")


class TestGeneratedCodeStructure:
    """Tests for the structure of generated code."""

    def test_has_imports(self):
        """Test that generated code has necessary imports."""
        parser = ProtocolParser()
        parsed = parser.parse_file(FIXTURES_DIR / "simple_protocol.py")

        generator = HTTPGenerator(parsed)
        http_code = generator.generate()

        assert "import requests" in http_code
        assert "import json" in http_code

    def test_has_robot_connection_class(self):
        """Test that generated code has RobotConnection class."""
        parser = ProtocolParser()
        parsed = parser.parse_file(FIXTURES_DIR / "simple_protocol.py")

        generator = HTTPGenerator(parsed)
        http_code = generator.generate()

        assert "class RobotConnection" in http_code
        assert "def health_check" in http_code

    def test_has_protocol_runner_class(self):
        """Test that generated code has HTTPProtocolRunner class."""
        parser = ProtocolParser()
        parsed = parser.parse_file(FIXTURES_DIR / "simple_protocol.py")

        generator = HTTPGenerator(parsed)
        http_code = generator.generate()

        assert "class HTTPProtocolRunner" in http_code
        assert "def create_run" in http_code
        assert "def execute_command" in http_code

    def test_has_main_entry_point(self):
        """Test that generated code has main entry point."""
        parser = ProtocolParser()
        parsed = parser.parse_file(FIXTURES_DIR / "simple_protocol.py")

        generator = HTTPGenerator(parsed)
        http_code = generator.generate()

        assert 'if __name__ == "__main__"' in http_code
        assert "run_protocol" in http_code


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
