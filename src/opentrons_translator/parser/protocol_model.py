"""
Data models for parsed protocol representation.

These models provide an intermediate representation between the Python API
and HTTP API, capturing all the information needed for translation.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Union


class RobotType(str, Enum):
    """Supported robot types."""
    FLEX = "OT-3 Standard"
    OT2 = "OT-2 Standard"


class ModuleType(str, Enum):
    """Hardware module types."""
    TEMPERATURE = "temperatureModuleV2"
    TEMPERATURE_V1 = "temperatureModuleV1"
    THERMOCYCLER = "thermocyclerModuleV2"
    THERMOCYCLER_V1 = "thermocyclerModuleV1"
    HEATER_SHAKER = "heaterShakerModuleV1"
    MAGNETIC_MODULE = "magneticModuleV2"
    MAGNETIC_MODULE_V1 = "magneticModuleV1"
    MAGNETIC_BLOCK = "magneticBlockV1"
    ABSORBANCE_READER = "absorbanceReaderV1"
    FLEX_STACKER = "flexStackerModuleV1"


class PipetteMount(str, Enum):
    """Pipette mount positions."""
    LEFT = "left"
    RIGHT = "right"
    EXTENSION = "extension"  # For 96-channel on Flex


class CommandType(str, Enum):
    """Protocol command types."""
    # Labware operations
    LOAD_LABWARE = "loadLabware"
    LOAD_ADAPTER = "loadAdapter"
    MOVE_LABWARE = "moveLabware"
    LOAD_LID = "loadLid"
    LOAD_LID_STACK = "loadLidStack"
    MOVE_LID = "moveLid"

    # Pipette operations
    LOAD_PIPETTE = "loadPipette"
    PICK_UP_TIP = "pickUpTip"
    DROP_TIP = "dropTip"
    DROP_TIP_IN_PLACE = "dropTipInPlace"
    ASPIRATE = "aspirate"
    ASPIRATE_IN_PLACE = "aspirateInPlace"
    DISPENSE = "dispense"
    DISPENSE_IN_PLACE = "dispenseInPlace"
    BLOW_OUT = "blowout"
    BLOW_OUT_IN_PLACE = "blowOutInPlace"
    TOUCH_TIP = "touchTip"
    AIR_GAP = "airGapInPlace"
    MIX = "mix"  # Expands to multiple aspirate/dispense
    PREPARE_TO_ASPIRATE = "prepareToAspirate"

    # Complex liquid handling (expand to multiple commands)
    TRANSFER = "transfer"
    DISTRIBUTE = "distribute"
    CONSOLIDATE = "consolidate"

    # Movement
    MOVE_TO_WELL = "moveToWell"
    MOVE_TO_COORDINATES = "moveToCoordinates"
    MOVE_RELATIVE = "moveRelative"
    HOME = "home"
    RETRACT_AXIS = "retractAxis"

    # Module operations
    LOAD_MODULE = "loadModule"

    # Temperature module
    TEMP_SET_TEMPERATURE = "temperatureModule/setTargetTemperature"
    TEMP_WAIT_FOR_TEMPERATURE = "temperatureModule/waitForTemperature"
    TEMP_DEACTIVATE = "temperatureModule/deactivate"

    # Thermocycler
    TC_OPEN_LID = "thermocycler/openLid"
    TC_CLOSE_LID = "thermocycler/closeLid"
    TC_SET_TARGET_BLOCK_TEMPERATURE = "thermocycler/setTargetBlockTemperature"
    TC_WAIT_FOR_BLOCK_TEMPERATURE = "thermocycler/waitForBlockTemperature"
    TC_SET_TARGET_LID_TEMPERATURE = "thermocycler/setTargetLidTemperature"
    TC_WAIT_FOR_LID_TEMPERATURE = "thermocycler/waitForLidTemperature"
    TC_RUN_PROFILE = "thermocycler/runProfile"
    TC_DEACTIVATE_BLOCK = "thermocycler/deactivateBlock"
    TC_DEACTIVATE_LID = "thermocycler/deactivateLid"
    TC_RUN_EXTENDED_PROFILE = "thermocycler/runExtendedProfile"

    # Heater-Shaker
    HS_SET_TARGET_TEMPERATURE = "heaterShaker/setTargetTemperature"
    HS_WAIT_FOR_TEMPERATURE = "heaterShaker/waitForTemperature"
    HS_SET_AND_WAIT_FOR_SHAKE_SPEED = "heaterShaker/setAndWaitForShakeSpeed"
    HS_DEACTIVATE_HEATER = "heaterShaker/deactivateHeater"
    HS_DEACTIVATE_SHAKER = "heaterShaker/deactivateShaker"
    HS_OPEN_LABWARE_LATCH = "heaterShaker/openLabwareLatch"
    HS_CLOSE_LABWARE_LATCH = "heaterShaker/closeLabwareLatch"

    # Magnetic module
    MAG_ENGAGE = "magneticModule/engage"
    MAG_DISENGAGE = "magneticModule/disengage"

    # Absorbance reader
    ABS_INITIALIZE = "absorbanceReader/initialize"
    ABS_OPEN_LID = "absorbanceReader/openLid"
    ABS_CLOSE_LID = "absorbanceReader/closeLid"
    ABS_READ = "absorbanceReader/read"

    # Flex Stacker
    STACKER_STORE = "flexStacker/store"
    STACKER_RETRIEVE = "flexStacker/retrieve"

    # Liquid handling
    DEFINE_LIQUID = "defineLiquid"
    LOAD_LIQUID = "loadLiquid"
    LOAD_LIQUID_CLASS = "loadLiquidClass"
    LIQUID_PROBE = "liquidProbe"
    TRY_LIQUID_PROBE = "tryLiquidProbe"

    # Pipette configuration
    CONFIGURE_FOR_VOLUME = "configureForVolume"
    CONFIGURE_NOZZLE_LAYOUT = "configureNozzleLayout"

    # Trash/waste
    LOAD_TRASH_BIN = "loadTrashBin"
    LOAD_WASTE_CHUTE = "loadWasteChute"

    # Utility
    COMMENT = "comment"
    DELAY = "waitForDuration"
    PAUSE = "waitForResume"
    SET_RAIL_LIGHTS = "setRailLights"

    # Robot context
    GET_TIP_PRESENCE = "getTipPresence"
    VERIFY_TIP_PRESENCE = "verifyTipPresence"


@dataclass
class WellLocation:
    """Represents a location within a well."""
    origin: str = "top"  # "top", "bottom", "center", "meniscus"
    offset_x: float = 0.0
    offset_y: float = 0.0
    offset_z: float = 0.0


@dataclass
class DeckLocation:
    """Represents a location on the deck."""
    slot: str  # e.g., "A1", "B2", "C3" for Flex, or "1"-"12" for OT-2
    module_id: Optional[str] = None  # If on a module
    adapter_id: Optional[str] = None  # If on an adapter
    labware_id: Optional[str] = None  # If stacked on labware


@dataclass
class LoadedLabware:
    """Represents loaded labware."""
    variable_name: str
    load_name: str
    location: DeckLocation
    label: Optional[str] = None
    namespace: str = "opentrons"
    version: int = 1
    labware_id: Optional[str] = None  # Assigned during translation


@dataclass
class LoadedPipette:
    """Represents a loaded pipette."""
    variable_name: str
    instrument_name: str
    mount: PipetteMount
    tip_racks: list[str] = field(default_factory=list)  # Variable names of tip racks
    pipette_id: Optional[str] = None  # Assigned during translation
    liquid_presence_detection: bool = False


@dataclass
class LoadedModule:
    """Represents a loaded module."""
    variable_name: str
    module_type: ModuleType
    location: str  # Deck slot
    module_id: Optional[str] = None  # Assigned during translation
    configuration: Optional[str] = None


@dataclass
class DefinedLiquid:
    """Represents a defined liquid."""
    variable_name: str
    name: str
    description: Optional[str] = None
    display_color: Optional[str] = None
    liquid_id: Optional[str] = None


@dataclass
class ProtocolCommand:
    """Represents a single protocol command."""
    command_type: CommandType
    params: dict[str, Any] = field(default_factory=dict)

    # Source tracking for debugging
    source_line: Optional[int] = None
    source_code: Optional[str] = None

    # Variable references (resolved during translation)
    pipette_var: Optional[str] = None
    labware_var: Optional[str] = None
    module_var: Optional[str] = None
    well_name: Optional[str] = None

    # For complex commands that expand to multiple HTTP commands
    sub_commands: list["ProtocolCommand"] = field(default_factory=list)


@dataclass
class RuntimeParameter:
    """Represents a runtime parameter."""
    variable_name: str
    param_type: str  # "int", "float", "bool", "str", "csv_file"
    display_name: str
    default: Any
    description: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    choices: Optional[list[dict[str, Any]]] = None


@dataclass
class ProtocolMetadata:
    """Protocol metadata from the metadata dictionary."""
    protocol_name: Optional[str] = None
    author: Optional[str] = None
    description: Optional[str] = None
    api_level: str = "2.19"
    robot_type: RobotType = RobotType.FLEX


@dataclass
class ParsedProtocol:
    """Complete parsed protocol representation."""
    metadata: ProtocolMetadata
    requirements: dict[str, Any] = field(default_factory=dict)

    # Loaded resources
    labware: list[LoadedLabware] = field(default_factory=list)
    pipettes: list[LoadedPipette] = field(default_factory=list)
    modules: list[LoadedModule] = field(default_factory=list)
    liquids: list[DefinedLiquid] = field(default_factory=list)

    # Runtime parameters
    runtime_parameters: list[RuntimeParameter] = field(default_factory=list)

    # Protocol commands in execution order
    commands: list[ProtocolCommand] = field(default_factory=list)

    # Source file info
    source_file: Optional[str] = None
    source_code: Optional[str] = None

    # Variable name to ID mappings (populated during translation)
    labware_id_map: dict[str, str] = field(default_factory=dict)
    pipette_id_map: dict[str, str] = field(default_factory=dict)
    module_id_map: dict[str, str] = field(default_factory=dict)
    liquid_id_map: dict[str, str] = field(default_factory=dict)

    def get_labware_by_var(self, var_name: str) -> Optional[LoadedLabware]:
        """Get labware by variable name."""
        for lw in self.labware:
            if lw.variable_name == var_name:
                return lw
        return None

    def get_pipette_by_var(self, var_name: str) -> Optional[LoadedPipette]:
        """Get pipette by variable name."""
        for p in self.pipettes:
            if p.variable_name == var_name:
                return p
        return None

    def get_module_by_var(self, var_name: str) -> Optional[LoadedModule]:
        """Get module by variable name."""
        for m in self.modules:
            if m.variable_name == var_name:
                return m
        return None
