"""Tests for the HTTP API code generator."""

import pytest
from pathlib import Path

from opentrons_translator.parser import ProtocolParser
from opentrons_translator.generator import HTTPGenerator


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestHTTPGenerator:
    """Tests for HTTPGenerator class."""

    def test_generate_simple_protocol(self):
        """Test generating HTTP API code from simple protocol."""
        parser = ProtocolParser()
        parsed = parser.parse_file(FIXTURES_DIR / "simple_protocol.py")

        generator = HTTPGenerator(parsed)
        http_code = generator.generate()

        assert http_code is not None
        assert len(http_code) > 0

        # Check for essential components
        assert "HTTPProtocolRunner" in http_code
        assert "execute_protocol" in http_code
        assert "def run_protocol" in http_code

        # Check for labware loading
        assert "load_labware" in http_code
        assert "opentrons_flex_96_tiprack_200ul" in http_code
        assert "nest_96_wellplate_200ul_flat" in http_code

        # Check for pipette loading
        assert "load_pipette" in http_code
        assert "flex_1channel_1000" in http_code

        # Check for liquid handling
        assert "aspirate" in http_code
        assert "dispense" in http_code
        assert "pick_up_tip" in http_code
        assert "drop_tip" in http_code

    def test_generate_complex_protocol(self):
        """Test generating HTTP API code from complex protocol."""
        parser = ProtocolParser()
        parsed = parser.parse_file(FIXTURES_DIR / "complex_protocol.py")

        generator = HTTPGenerator(parsed)
        http_code = generator.generate()

        # Check for module loading
        assert "load_module" in http_code
        assert "temperatureModule" in http_code.lower() or "temperature" in http_code.lower()

        # Check for module commands
        assert "setTargetTemperature" in http_code or "set_temperature" in http_code

        # Check for complex commands
        # The generator should expand transfer/distribute/consolidate

    def test_generate_header(self):
        """Test that header is correctly generated."""
        source = '''
metadata = {
    "protocolName": "Test Protocol",
    "apiLevel": "2.19",
}
requirements = {"robotType": "OT-3 Standard"}

def run(protocol):
    protocol.comment("test")
'''
        parser = ProtocolParser()
        parsed = parser.parse_source(source)

        generator = HTTPGenerator(parsed)
        http_code = generator.generate()

        # Check header content
        assert "HTTP API Protocol" in http_code
        assert "Test Protocol" in http_code
        assert "2.19" in http_code
        assert "OT-3" in http_code

    def test_generate_to_file(self, tmp_path):
        """Test generating to a file."""
        source = '''
metadata = {"apiLevel": "2.19"}
requirements = {"robotType": "OT-3 Standard"}

def run(protocol):
    tips = protocol.load_labware("opentrons_flex_96_tiprack_200ul", "A1")
    pipette = protocol.load_instrument("flex_1channel_1000", "left", tip_racks=[tips])
    pipette.pick_up_tip()
    pipette.drop_tip()
'''
        parser = ProtocolParser()
        parsed = parser.parse_source(source)

        generator = HTTPGenerator(parsed)
        output_path = tmp_path / "output.py"
        generator.generate_to_file(output_path)

        assert output_path.exists()
        content = output_path.read_text()
        assert "HTTPProtocolRunner" in content

    def test_generate_labware_locations(self):
        """Test that labware locations are correctly generated."""
        source = '''
metadata = {"apiLevel": "2.19"}
requirements = {"robotType": "OT-3 Standard"}

def run(protocol):
    plate1 = protocol.load_labware("nest_96_wellplate_200ul_flat", "A1")
    plate2 = protocol.load_labware("nest_96_wellplate_200ul_flat", "B2")
    plate3 = protocol.load_labware("nest_96_wellplate_200ul_flat", "C3")
'''
        parser = ProtocolParser()
        parsed = parser.parse_source(source)

        generator = HTTPGenerator(parsed)
        http_code = generator.generate()

        assert '"slotName": "A1"' in http_code
        assert '"slotName": "B2"' in http_code
        assert '"slotName": "C3"' in http_code

    def test_generate_mix_expansion(self):
        """Test that mix is expanded to aspirate/dispense loops."""
        source = '''
metadata = {"apiLevel": "2.19"}
requirements = {"robotType": "OT-3 Standard"}

def run(protocol):
    tips = protocol.load_labware("opentrons_flex_96_tiprack_200ul", "A1")
    plate = protocol.load_labware("nest_96_wellplate_200ul_flat", "A2")
    pipette = protocol.load_instrument("flex_1channel_1000", "left", tip_racks=[tips])

    pipette.pick_up_tip()
    pipette.mix(3, 100, plate["A1"])
    pipette.drop_tip()
'''
        parser = ProtocolParser()
        parsed = parser.parse_source(source)

        generator = HTTPGenerator(parsed)
        http_code = generator.generate()

        # Mix should be expanded to a loop
        assert "for _ in range(3)" in http_code
        assert "aspirate" in http_code
        assert "dispense" in http_code

    def test_generate_delay_command(self):
        """Test delay command generation."""
        source = '''
metadata = {"apiLevel": "2.19"}
requirements = {"robotType": "OT-3 Standard"}

def run(protocol):
    protocol.delay(seconds=30)
'''
        parser = ProtocolParser()
        parsed = parser.parse_source(source)

        generator = HTTPGenerator(parsed)
        http_code = generator.generate()

        assert "delay(30" in http_code or "waitForDuration" in http_code

    def test_generate_comment_command(self):
        """Test comment command generation."""
        source = '''
metadata = {"apiLevel": "2.19"}
requirements = {"robotType": "OT-3 Standard"}

def run(protocol):
    protocol.comment("Starting protocol")
'''
        parser = ProtocolParser()
        parsed = parser.parse_source(source)

        generator = HTTPGenerator(parsed)
        http_code = generator.generate()

        assert "comment" in http_code
        assert "Starting protocol" in http_code

    def test_generate_home_command(self):
        """Test home command generation."""
        source = '''
metadata = {"apiLevel": "2.19"}
requirements = {"robotType": "OT-3 Standard"}

def run(protocol):
    protocol.home()
'''
        parser = ProtocolParser()
        parsed = parser.parse_source(source)

        generator = HTTPGenerator(parsed)
        http_code = generator.generate()

        assert "home()" in http_code


class TestCodeValidity:
    """Tests that generated code is valid Python."""

    def test_generated_code_is_valid_python(self):
        """Test that generated code can be compiled."""
        parser = ProtocolParser()
        parsed = parser.parse_file(FIXTURES_DIR / "simple_protocol.py")

        generator = HTTPGenerator(parsed)
        http_code = generator.generate()

        # This will raise SyntaxError if code is invalid
        compile(http_code, "<string>", "exec")

    def test_generated_complex_code_is_valid_python(self):
        """Test that complex generated code can be compiled."""
        parser = ProtocolParser()
        parsed = parser.parse_file(FIXTURES_DIR / "complex_protocol.py")

        generator = HTTPGenerator(parsed)
        http_code = generator.generate()

        # This will raise SyntaxError if code is invalid
        compile(http_code, "<string>", "exec")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
