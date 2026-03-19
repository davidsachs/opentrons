"""
Module mapping utilities.

Maps Python API module types to HTTP API module models and commands.
"""

from typing import Any, Optional
from ..parser.protocol_model import ModuleType


class ModuleMapper:
    """
    Maps hardware modules between Python API and HTTP API representations.
    """

    # Module type to HTTP API model mapping
    MODULE_MODEL_MAP = {
        ModuleType.TEMPERATURE: "temperatureModuleV2",
        ModuleType.TEMPERATURE_V1: "temperatureModuleV1",
        ModuleType.THERMOCYCLER: "thermocyclerModuleV2",
        ModuleType.THERMOCYCLER_V1: "thermocyclerModuleV1",
        ModuleType.HEATER_SHAKER: "heaterShakerModuleV1",
        ModuleType.MAGNETIC_MODULE: "magneticModuleV2",
        ModuleType.MAGNETIC_MODULE_V1: "magneticModuleV1",
        ModuleType.MAGNETIC_BLOCK: "magneticBlockV1",
        ModuleType.ABSORBANCE_READER: "absorbanceReaderV1",
        ModuleType.FLEX_STACKER: "flexStackerModuleV1",
    }

    # Python API name to module type
    PYTHON_NAME_MAP = {
        "temperature module": ModuleType.TEMPERATURE,
        "temperature module gen2": ModuleType.TEMPERATURE,
        "temperatureModuleV1": ModuleType.TEMPERATURE_V1,
        "temperatureModuleV2": ModuleType.TEMPERATURE,
        "thermocycler": ModuleType.THERMOCYCLER,
        "thermocycler module": ModuleType.THERMOCYCLER,
        "thermocycler module gen2": ModuleType.THERMOCYCLER,
        "thermocyclerModuleV1": ModuleType.THERMOCYCLER_V1,
        "thermocyclerModuleV2": ModuleType.THERMOCYCLER,
        "heater-shaker": ModuleType.HEATER_SHAKER,
        "heaterShakerModuleV1": ModuleType.HEATER_SHAKER,
        "magnetic module": ModuleType.MAGNETIC_MODULE,
        "magnetic module gen2": ModuleType.MAGNETIC_MODULE,
        "magneticModuleV1": ModuleType.MAGNETIC_MODULE_V1,
        "magneticModuleV2": ModuleType.MAGNETIC_MODULE,
        "magnetic block": ModuleType.MAGNETIC_BLOCK,
        "magneticBlockV1": ModuleType.MAGNETIC_BLOCK,
        "absorbance plate reader": ModuleType.ABSORBANCE_READER,
        "absorbanceReaderV1": ModuleType.ABSORBANCE_READER,
        "flex stacker": ModuleType.FLEX_STACKER,
        "flexStackerModuleV1": ModuleType.FLEX_STACKER,
    }

    # Valid Flex deck slots for each module type
    MODULE_SLOT_CONSTRAINTS = {
        ModuleType.THERMOCYCLER: ["B1"],  # Thermocycler takes up B1 and A1
        ModuleType.THERMOCYCLER_V1: ["B1"],
        ModuleType.HEATER_SHAKER: ["A1", "A3", "B1", "B3", "C1", "C3", "D1", "D3"],
        ModuleType.TEMPERATURE: ["A1", "A3", "B1", "B3", "C1", "C3", "D1", "D3"],
        ModuleType.TEMPERATURE_V1: ["A1", "A3", "B1", "B3", "C1", "C3", "D1", "D3"],
        ModuleType.MAGNETIC_MODULE: ["A1", "A3", "B1", "B3", "C1", "C3", "D1", "D3"],
        ModuleType.MAGNETIC_MODULE_V1: ["A1", "A3", "B1", "B3", "C1", "C3", "D1", "D3"],
        ModuleType.MAGNETIC_BLOCK: ["A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "C3", "D1", "D2", "D3"],
        ModuleType.ABSORBANCE_READER: ["D3"],
        ModuleType.FLEX_STACKER: ["A4", "B4", "C4", "D4"],  # Staging area slots
    }

    @classmethod
    def get_module_type(cls, python_name: str) -> Optional[ModuleType]:
        """Get ModuleType from Python API name."""
        return cls.PYTHON_NAME_MAP.get(python_name.lower())

    @classmethod
    def get_http_model(cls, module_type: ModuleType) -> str:
        """Get HTTP API model name for a module type."""
        return cls.MODULE_MODEL_MAP.get(module_type, "unknown")

    @classmethod
    def get_valid_slots(cls, module_type: ModuleType) -> list[str]:
        """Get valid deck slots for a module type."""
        return cls.MODULE_SLOT_CONSTRAINTS.get(module_type, [])

    @classmethod
    def build_load_module_params(
        cls,
        module_type: ModuleType,
        slot: str,
    ) -> dict[str, Any]:
        """Build parameters for loadModule HTTP command."""
        return {
            "model": cls.get_http_model(module_type),
            "location": {"slotName": slot},
        }

    @classmethod
    def get_module_command_prefix(cls, module_type: ModuleType) -> str:
        """Get the command prefix for module commands."""
        prefixes = {
            ModuleType.TEMPERATURE: "temperatureModule",
            ModuleType.TEMPERATURE_V1: "temperatureModule",
            ModuleType.THERMOCYCLER: "thermocycler",
            ModuleType.THERMOCYCLER_V1: "thermocycler",
            ModuleType.HEATER_SHAKER: "heaterShaker",
            ModuleType.MAGNETIC_MODULE: "magneticModule",
            ModuleType.MAGNETIC_MODULE_V1: "magneticModule",
            ModuleType.MAGNETIC_BLOCK: "magneticModule",
            ModuleType.ABSORBANCE_READER: "absorbanceReader",
            ModuleType.FLEX_STACKER: "flexStacker",
        }
        return prefixes.get(module_type, "unknown")


class TemperatureModuleMapper:
    """Mapping utilities for Temperature Module."""

    @staticmethod
    def build_set_temperature_params(celsius: float) -> dict[str, Any]:
        """Build params for setTargetTemperature command."""
        return {"celsius": celsius}

    @staticmethod
    def build_wait_for_temperature_params(celsius: Optional[float] = None) -> dict[str, Any]:
        """Build params for waitForTemperature command."""
        params: dict[str, Any] = {}
        if celsius is not None:
            params["celsius"] = celsius
        return params


class ThermocyclerMapper:
    """Mapping utilities for Thermocycler."""

    @staticmethod
    def build_set_block_temperature_params(
        celsius: float,
        hold_time_seconds: Optional[float] = None,
        block_max_volume: Optional[float] = None,
    ) -> dict[str, Any]:
        """Build params for setTargetBlockTemperature command."""
        params: dict[str, Any] = {"celsius": celsius}
        if hold_time_seconds is not None:
            params["holdTimeSeconds"] = hold_time_seconds
        if block_max_volume is not None:
            params["blockMaxVolumeUl"] = block_max_volume
        return params

    @staticmethod
    def build_set_lid_temperature_params(celsius: float) -> dict[str, Any]:
        """Build params for setTargetLidTemperature command."""
        return {"celsius": celsius}

    @staticmethod
    def build_run_profile_params(
        profile: list[dict[str, Any]],
        block_max_volume: Optional[float] = None,
    ) -> dict[str, Any]:
        """Build params for runProfile command."""
        params: dict[str, Any] = {"profile": profile}
        if block_max_volume is not None:
            params["blockMaxVolumeUl"] = block_max_volume
        return params


class HeaterShakerMapper:
    """Mapping utilities for Heater-Shaker."""

    @staticmethod
    def build_set_temperature_params(celsius: float) -> dict[str, Any]:
        """Build params for setTargetTemperature command."""
        return {"celsius": celsius}

    @staticmethod
    def build_set_shake_speed_params(rpm: int) -> dict[str, Any]:
        """Build params for setAndWaitForShakeSpeed command."""
        return {"rpm": rpm}


class MagneticModuleMapper:
    """Mapping utilities for Magnetic Module."""

    @staticmethod
    def build_engage_params(height: Optional[float] = None) -> dict[str, Any]:
        """Build params for engage command."""
        params: dict[str, Any] = {}
        if height is not None:
            params["height"] = height
        return params


class AbsorbanceReaderMapper:
    """Mapping utilities for Absorbance Reader."""

    @staticmethod
    def build_initialize_params(
        mode: str = "single",
        wavelengths: Optional[list[int]] = None,
        reference_wavelength: Optional[int] = None,
    ) -> dict[str, Any]:
        """Build params for initialize command."""
        params: dict[str, Any] = {
            "measureMode": mode,
            "sampleWavelengths": wavelengths or [],
        }
        if reference_wavelength is not None:
            params["referenceWavelength"] = reference_wavelength
        return params

    @staticmethod
    def build_read_params(filename: Optional[str] = None) -> dict[str, Any]:
        """Build params for read command."""
        params: dict[str, Any] = {}
        if filename is not None:
            params["fileName"] = filename
        return params
