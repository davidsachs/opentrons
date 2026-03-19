"""
Pipette mapping utilities.

Maps Python API pipette names to HTTP API pipette names and provides
utilities for pipette-related operations.
"""

from typing import Any, Optional
from enum import Enum


class PipetteType(str, Enum):
    """Pipette types for Flex."""
    FLEX_1CH_50 = "flex_1channel_50"
    FLEX_1CH_1000 = "flex_1channel_1000"
    FLEX_8CH_50 = "flex_8channel_50"
    FLEX_8CH_1000 = "flex_8channel_1000"
    FLEX_96CH_1000 = "flex_96channel_1000"


class NozzleLayout(str, Enum):
    """Nozzle layout configurations for multi-channel pipettes."""
    ALL = "ALL"
    SINGLE = "SINGLE"
    COLUMN = "COLUMN"
    ROW = "ROW"
    PARTIAL_COLUMN = "PARTIAL_COLUMN"
    QUADRANT = "QUADRANT"


class PipetteMapper:
    """
    Maps pipettes between Python API and HTTP API representations.
    """

    # Python API instrument name to HTTP API pipette name
    PIPETTE_NAME_MAP = {
        # Flex pipettes
        "flex_1channel_50": "flex_1channel_50",
        "flex_1channel_1000": "flex_1channel_1000",
        "flex_8channel_50": "flex_8channel_50",
        "flex_8channel_1000": "flex_8channel_1000",
        "flex_96channel_1000": "flex_96channel_1000",

        # OT-2 pipettes (for reference)
        "p20_single_gen2": "p20_single_gen2",
        "p20_multi_gen2": "p20_multi_gen2",
        "p300_single_gen2": "p300_single_gen2",
        "p300_multi_gen2": "p300_multi_gen2",
        "p1000_single_gen2": "p1000_single_gen2",
    }

    # Pipette volume ranges
    PIPETTE_VOLUMES = {
        "flex_1channel_50": {"min": 1, "max": 50},
        "flex_1channel_1000": {"min": 5, "max": 1000},
        "flex_8channel_50": {"min": 1, "max": 50},
        "flex_8channel_1000": {"min": 5, "max": 1000},
        "flex_96channel_1000": {"min": 5, "max": 1000},
    }

    # Number of channels per pipette
    PIPETTE_CHANNELS = {
        "flex_1channel_50": 1,
        "flex_1channel_1000": 1,
        "flex_8channel_50": 8,
        "flex_8channel_1000": 8,
        "flex_96channel_1000": 96,
    }

    # Compatible tip racks for each pipette
    COMPATIBLE_TIP_RACKS = {
        "flex_1channel_50": [
            "opentrons_flex_96_tiprack_50ul",
            "opentrons_flex_96_filtertiprack_50ul",
        ],
        "flex_1channel_1000": [
            "opentrons_flex_96_tiprack_200ul",
            "opentrons_flex_96_tiprack_1000ul",
            "opentrons_flex_96_filtertiprack_200ul",
            "opentrons_flex_96_filtertiprack_1000ul",
        ],
        "flex_8channel_50": [
            "opentrons_flex_96_tiprack_50ul",
            "opentrons_flex_96_filtertiprack_50ul",
        ],
        "flex_8channel_1000": [
            "opentrons_flex_96_tiprack_200ul",
            "opentrons_flex_96_tiprack_1000ul",
            "opentrons_flex_96_filtertiprack_200ul",
            "opentrons_flex_96_filtertiprack_1000ul",
        ],
        "flex_96channel_1000": [
            "opentrons_flex_96_tiprack_200ul",
            "opentrons_flex_96_tiprack_1000ul",
            "opentrons_flex_96_filtertiprack_200ul",
            "opentrons_flex_96_filtertiprack_1000ul",
        ],
    }

    # Default flow rates (uL/s)
    DEFAULT_FLOW_RATES = {
        "flex_1channel_50": {"aspirate": 35, "dispense": 57, "blow_out": 57},
        "flex_1channel_1000": {"aspirate": 160, "dispense": 160, "blow_out": 160},
        "flex_8channel_50": {"aspirate": 35, "dispense": 57, "blow_out": 57},
        "flex_8channel_1000": {"aspirate": 160, "dispense": 160, "blow_out": 160},
        "flex_96channel_1000": {"aspirate": 160, "dispense": 160, "blow_out": 160},
    }

    @classmethod
    def get_http_pipette_name(cls, python_name: str) -> str:
        """Get HTTP API pipette name from Python API name."""
        return cls.PIPETTE_NAME_MAP.get(python_name, python_name)

    @classmethod
    def get_channels(cls, pipette_name: str) -> int:
        """Get number of channels for a pipette."""
        return cls.PIPETTE_CHANNELS.get(pipette_name, 1)

    @classmethod
    def get_volume_range(cls, pipette_name: str) -> dict[str, float]:
        """Get volume range for a pipette."""
        return cls.PIPETTE_VOLUMES.get(pipette_name, {"min": 1, "max": 1000})

    @classmethod
    def get_compatible_tip_racks(cls, pipette_name: str) -> list[str]:
        """Get compatible tip racks for a pipette."""
        return cls.COMPATIBLE_TIP_RACKS.get(pipette_name, [])

    @classmethod
    def get_default_flow_rate(
        cls, pipette_name: str, operation: str = "aspirate"
    ) -> float:
        """Get default flow rate for a pipette operation."""
        rates = cls.DEFAULT_FLOW_RATES.get(pipette_name, {})
        return rates.get(operation, 100)

    @classmethod
    def is_multi_channel(cls, pipette_name: str) -> bool:
        """Check if pipette is multi-channel."""
        return cls.get_channels(pipette_name) > 1

    @classmethod
    def is_96_channel(cls, pipette_name: str) -> bool:
        """Check if pipette is 96-channel."""
        return cls.get_channels(pipette_name) == 96

    @classmethod
    def build_load_pipette_params(
        cls,
        pipette_name: str,
        mount: str,
    ) -> dict[str, Any]:
        """Build parameters for loadPipette HTTP command."""
        return {
            "pipetteName": cls.get_http_pipette_name(pipette_name),
            "mount": mount,
        }

    @classmethod
    def build_configure_for_volume_params(
        cls,
        volume: float,
    ) -> dict[str, Any]:
        """Build parameters for configureForVolume HTTP command."""
        return {"volume": volume}

    @classmethod
    def build_configure_nozzle_layout_params(
        cls,
        style: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        front_right: Optional[str] = None,
        back_left: Optional[str] = None,
    ) -> dict[str, Any]:
        """Build parameters for configureNozzleLayout HTTP command."""
        params: dict[str, Any] = {"style": style}

        if style == "SINGLE" and start:
            params["primaryNozzle"] = start
        elif style == "COLUMN" and start:
            params["primaryNozzle"] = start
        elif style == "ROW" and start:
            params["primaryNozzle"] = start
        elif style == "PARTIAL_COLUMN":
            if start:
                params["primaryNozzle"] = start
            if end:
                params["backLeftNozzle"] = end
        elif style == "QUADRANT":
            if front_right:
                params["frontRightNozzle"] = front_right
            if back_left:
                params["backLeftNozzle"] = back_left

        return {"configurationParams": params}

    @classmethod
    def get_nozzle_map_for_layout(
        cls, pipette_name: str, layout: NozzleLayout
    ) -> list[str]:
        """Get active nozzles for a given layout configuration."""
        channels = cls.get_channels(pipette_name)

        if channels == 1:
            return ["A1"]

        if channels == 8:
            # 8-channel pipette nozzles are A1-H1
            all_nozzles = [f"{chr(65 + i)}1" for i in range(8)]
            if layout == NozzleLayout.ALL:
                return all_nozzles
            elif layout == NozzleLayout.SINGLE:
                return ["A1"]  # Default to first nozzle
            elif layout == NozzleLayout.COLUMN:
                return all_nozzles
            else:
                return all_nozzles

        if channels == 96:
            # 96-channel has A1-H12 nozzle arrangement
            all_nozzles = [
                f"{chr(65 + row)}{col}" for row in range(8) for col in range(1, 13)
            ]
            if layout == NozzleLayout.ALL:
                return all_nozzles
            elif layout == NozzleLayout.SINGLE:
                return ["A1"]
            elif layout == NozzleLayout.COLUMN:
                return [f"{chr(65 + row)}1" for row in range(8)]
            elif layout == NozzleLayout.ROW:
                return [f"A{col}" for col in range(1, 13)]
            else:
                return all_nozzles

        return ["A1"]
