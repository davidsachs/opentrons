"""Tests for the API mapping layer."""

import pytest

from opentrons_translator.parser import (
    ProtocolParser,
    ParsedProtocol,
    ProtocolCommand,
    CommandType,
)
from opentrons_translator.mapping import (
    CommandMapper,
    LabwareMapper,
    ModuleMapper,
    PipetteMapper,
)
from opentrons_translator.mapping.modules import ModuleType


class TestCommandMapper:
    """Tests for CommandMapper class."""

    def test_direct_command_mapping(self):
        """Test direct 1:1 command mapping."""
        # Create a minimal parsed protocol
        source = '''
metadata = {"apiLevel": "2.19"}
requirements = {"robotType": "OT-3 Standard"}

def run(protocol):
    tips = protocol.load_labware("opentrons_flex_96_tiprack_200ul", "A1")
    plate = protocol.load_labware("nest_96_wellplate_200ul_flat", "A2")
    pipette = protocol.load_instrument("flex_1channel_1000", "left", tip_racks=[tips])
    pipette.home()
'''
        parser = ProtocolParser()
        parsed = parser.parse_source(source)

        # Assign IDs
        parsed.labware_id_map = {"tips": "labware-1", "plate": "labware-2"}
        parsed.pipette_id_map = {"pipette": "pipette-1"}

        mapper = CommandMapper(parsed)

        # Find and map the home command
        home_cmd = next(
            c for c in parsed.commands if c.command_type == CommandType.HOME
        )
        http_commands = mapper.map_command(home_cmd)

        assert len(http_commands) == 1
        assert http_commands[0].command_type == "home"

    def test_mix_expansion(self):
        """Test that mix expands to aspirate/dispense pairs."""
        source = '''
metadata = {"apiLevel": "2.19"}
requirements = {"robotType": "OT-3 Standard"}

def run(protocol):
    tips = protocol.load_labware("opentrons_flex_96_tiprack_200ul", "A1")
    plate = protocol.load_labware("nest_96_wellplate_200ul_flat", "A2")
    pipette = protocol.load_instrument("flex_1channel_1000", "left", tip_racks=[tips])
    pipette.pick_up_tip()
    pipette.mix(5, 100, plate["A1"])
    pipette.drop_tip()
'''
        parser = ProtocolParser()
        parsed = parser.parse_source(source)

        # Assign IDs
        parsed.labware_id_map = {"tips": "labware-1", "plate": "labware-2"}
        parsed.pipette_id_map = {"pipette": "pipette-1"}

        mapper = CommandMapper(parsed)

        # Find and map the mix command
        mix_cmd = next(
            c for c in parsed.commands if c.command_type == CommandType.MIX
        )
        http_commands = mapper.map_command(mix_cmd)

        # Mix(5) should produce 5 aspirate + 5 dispense = 10 commands
        assert len(http_commands) == 10
        aspirate_count = sum(1 for c in http_commands if c.command_type == "aspirate")
        dispense_count = sum(1 for c in http_commands if c.command_type == "dispense")
        assert aspirate_count == 5
        assert dispense_count == 5

    def test_map_all_commands(self):
        """Test mapping all commands in a protocol."""
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
    pipette.drop_tip()
'''
        parser = ProtocolParser()
        parsed = parser.parse_source(source)

        # Assign IDs
        parsed.labware_id_map = {"tips": "labware-1", "plate": "labware-2"}
        parsed.pipette_id_map = {"pipette": "pipette-1"}

        mapper = CommandMapper(parsed)
        http_commands = mapper.map_all_commands()

        # Should have load commands + liquid handling commands
        assert len(http_commands) > 0

        # Check command types
        command_types = [c.command_type for c in http_commands]
        assert "loadLabware" in command_types
        assert "loadPipette" in command_types
        assert "pickUpTip" in command_types
        assert "aspirate" in command_types
        assert "dispense" in command_types


class TestLabwareMapper:
    """Tests for LabwareMapper class."""

    def test_get_http_load_name(self):
        """Test labware name mapping."""
        # Most names are 1:1
        assert LabwareMapper.get_http_load_name(
            "nest_96_wellplate_200ul_flat"
        ) == "nest_96_wellplate_200ul_flat"

        assert LabwareMapper.get_http_load_name(
            "opentrons_flex_96_tiprack_200ul"
        ) == "opentrons_flex_96_tiprack_200ul"

    def test_get_wells_for_labware(self):
        """Test well list generation."""
        wells_96 = LabwareMapper.get_wells_for_labware("nest_96_wellplate_200ul_flat")
        assert len(wells_96) == 96
        assert "A1" in wells_96
        assert "H12" in wells_96

        wells_384 = LabwareMapper.get_wells_for_labware("corning_384_wellplate_112ul_flat")
        assert len(wells_384) == 384

        wells_12 = LabwareMapper.get_wells_for_labware("nest_12_reservoir_15ml")
        assert len(wells_12) == 12

    def test_is_tip_rack(self):
        """Test tip rack detection."""
        assert LabwareMapper.is_tip_rack("opentrons_flex_96_tiprack_200ul") is True
        assert LabwareMapper.is_tip_rack("nest_96_wellplate_200ul_flat") is False

    def test_is_reservoir(self):
        """Test reservoir detection."""
        assert LabwareMapper.is_reservoir("nest_12_reservoir_15ml") is True
        assert LabwareMapper.is_reservoir("nest_96_wellplate_200ul_flat") is False

    def test_build_location(self):
        """Test location dictionary building."""
        loc = LabwareMapper.build_location(slot="A1")
        assert loc == {"slotName": "A1"}

        loc = LabwareMapper.build_location(module_id="module-1")
        assert loc == {"moduleId": "module-1"}

        loc = LabwareMapper.build_location(labware_id="labware-1")
        assert loc == {"labwareId": "labware-1"}

    def test_build_well_location(self):
        """Test well location dictionary building."""
        loc = LabwareMapper.build_well_location()
        assert loc == {"origin": "top"}

        loc = LabwareMapper.build_well_location(origin="bottom", offset_z=2)
        assert loc == {"origin": "bottom", "offset": {"x": 0, "y": 0, "z": 2}}


class TestModuleMapper:
    """Tests for ModuleMapper class."""

    def test_get_module_type(self):
        """Test module type lookup."""
        assert ModuleMapper.get_module_type("temperature module gen2") == ModuleType.TEMPERATURE
        assert ModuleMapper.get_module_type("heater-shaker") == ModuleType.HEATER_SHAKER
        assert ModuleMapper.get_module_type("thermocycler") == ModuleType.THERMOCYCLER

    def test_get_http_model(self):
        """Test HTTP model name lookup."""
        assert ModuleMapper.get_http_model(ModuleType.TEMPERATURE) == "temperatureModuleV2"
        assert ModuleMapper.get_http_model(ModuleType.HEATER_SHAKER) == "heaterShakerModuleV1"
        assert ModuleMapper.get_http_model(ModuleType.THERMOCYCLER) == "thermocyclerModuleV2"

    def test_get_valid_slots(self):
        """Test valid slot retrieval."""
        tc_slots = ModuleMapper.get_valid_slots(ModuleType.THERMOCYCLER)
        assert "B1" in tc_slots

        hs_slots = ModuleMapper.get_valid_slots(ModuleType.HEATER_SHAKER)
        assert len(hs_slots) > 0

    def test_build_load_module_params(self):
        """Test module load params building."""
        params = ModuleMapper.build_load_module_params(ModuleType.TEMPERATURE, "B1")
        assert params == {
            "model": "temperatureModuleV2",
            "location": {"slotName": "B1"},
        }


class TestPipetteMapper:
    """Tests for PipetteMapper class."""

    def test_get_http_pipette_name(self):
        """Test pipette name mapping."""
        assert PipetteMapper.get_http_pipette_name(
            "flex_1channel_1000"
        ) == "flex_1channel_1000"

        assert PipetteMapper.get_http_pipette_name(
            "flex_8channel_50"
        ) == "flex_8channel_50"

    def test_get_channels(self):
        """Test channel count lookup."""
        assert PipetteMapper.get_channels("flex_1channel_1000") == 1
        assert PipetteMapper.get_channels("flex_8channel_50") == 8
        assert PipetteMapper.get_channels("flex_96channel_1000") == 96

    def test_get_volume_range(self):
        """Test volume range lookup."""
        vol_range = PipetteMapper.get_volume_range("flex_1channel_50")
        assert vol_range["min"] == 1
        assert vol_range["max"] == 50

        vol_range = PipetteMapper.get_volume_range("flex_1channel_1000")
        assert vol_range["min"] == 5
        assert vol_range["max"] == 1000

    def test_is_multi_channel(self):
        """Test multi-channel detection."""
        assert PipetteMapper.is_multi_channel("flex_1channel_1000") is False
        assert PipetteMapper.is_multi_channel("flex_8channel_50") is True
        assert PipetteMapper.is_multi_channel("flex_96channel_1000") is True

    def test_get_compatible_tip_racks(self):
        """Test compatible tip rack lookup."""
        racks = PipetteMapper.get_compatible_tip_racks("flex_1channel_50")
        assert "opentrons_flex_96_tiprack_50ul" in racks

        racks = PipetteMapper.get_compatible_tip_racks("flex_1channel_1000")
        assert "opentrons_flex_96_tiprack_1000ul" in racks
        assert "opentrons_flex_96_tiprack_200ul" in racks

    def test_build_load_pipette_params(self):
        """Test pipette load params building."""
        params = PipetteMapper.build_load_pipette_params("flex_1channel_1000", "left")
        assert params == {
            "pipetteName": "flex_1channel_1000",
            "mount": "left",
        }


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
