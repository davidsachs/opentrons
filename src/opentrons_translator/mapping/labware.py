"""
Labware mapping utilities.

Maps Python API labware names to HTTP API load names and definitions.
"""

from typing import Any, Optional


class LabwareMapper:
    """
    Maps labware between Python API and HTTP API representations.

    The labware load names are generally the same between APIs,
    but this class handles any necessary conversions and provides
    utilities for labware-related operations.
    """

    # Common Flex labware mappings (load_name -> HTTP API load_name)
    # Most are 1:1, but some may have variations
    LABWARE_MAPPING = {
        # Tip racks
        "opentrons_flex_96_tiprack_50ul": "opentrons_flex_96_tiprack_50ul",
        "opentrons_flex_96_tiprack_200ul": "opentrons_flex_96_tiprack_200ul",
        "opentrons_flex_96_tiprack_1000ul": "opentrons_flex_96_tiprack_1000ul",
        "opentrons_flex_96_filtertiprack_50ul": "opentrons_flex_96_filtertiprack_50ul",
        "opentrons_flex_96_filtertiprack_200ul": "opentrons_flex_96_filtertiprack_200ul",
        "opentrons_flex_96_filtertiprack_1000ul": "opentrons_flex_96_filtertiprack_1000ul",

        # Well plates
        "nest_96_wellplate_100ul_pcr_full_skirt": "nest_96_wellplate_100ul_pcr_full_skirt",
        "nest_96_wellplate_200ul_flat": "nest_96_wellplate_200ul_flat",
        "nest_96_wellplate_2ml_deep": "nest_96_wellplate_2ml_deep",
        "corning_96_wellplate_360ul_flat": "corning_96_wellplate_360ul_flat",
        "biorad_96_wellplate_200ul_pcr": "biorad_96_wellplate_200ul_pcr",
        "opentrons_96_wellplate_200ul_pcr_full_skirt": "opentrons_96_wellplate_200ul_pcr_full_skirt",

        # Reservoirs
        "nest_12_reservoir_15ml": "nest_12_reservoir_15ml",
        "nest_1_reservoir_195ml": "nest_1_reservoir_195ml",
        "nest_1_reservoir_290ml": "nest_1_reservoir_290ml",
        "agilent_1_reservoir_290ml": "agilent_1_reservoir_290ml",

        # Tube racks
        "opentrons_24_tuberack_eppendorf_1.5ml_safelock_snapcap": "opentrons_24_tuberack_eppendorf_1.5ml_safelock_snapcap",
        "opentrons_24_tuberack_nest_1.5ml_screwcap": "opentrons_24_tuberack_nest_1.5ml_screwcap",
        "opentrons_24_tuberack_nest_2ml_screwcap": "opentrons_24_tuberack_nest_2ml_screwcap",
        "opentrons_6_tuberack_falcon_50ml_conical": "opentrons_6_tuberack_falcon_50ml_conical",
        "opentrons_15_tuberack_falcon_15ml_conical": "opentrons_15_tuberack_falcon_15ml_conical",

        # Aluminum blocks
        "opentrons_96_aluminumblock_nest_wellplate_100ul": "opentrons_96_aluminumblock_nest_wellplate_100ul",
        "opentrons_96_aluminumblock_biorad_wellplate_200ul": "opentrons_96_aluminumblock_biorad_wellplate_200ul",

        # Adapters
        "opentrons_flex_96_tiprack_adapter": "opentrons_flex_96_tiprack_adapter",
        "opentrons_universal_flat_adapter": "opentrons_universal_flat_adapter",
        "opentrons_aluminum_flat_bottom_plate": "opentrons_aluminum_flat_bottom_plate",
    }

    # Standard 96-well plate wells
    WELLS_96 = [f"{row}{col}" for row in "ABCDEFGH" for col in range(1, 13)]

    # Standard 384-well plate wells
    WELLS_384 = [f"{row}{col}" for row in "ABCDEFGHIJKLMNOP" for col in range(1, 25)]

    # Standard 24-well plate wells
    WELLS_24 = [f"{row}{col}" for row in "ABCD" for col in range(1, 7)]

    # Standard 12-well reservoir wells
    WELLS_12 = [f"A{col}" for col in range(1, 13)]

    @classmethod
    def get_http_load_name(cls, python_load_name: str) -> str:
        """Get the HTTP API load name for a Python API load name."""
        return cls.LABWARE_MAPPING.get(python_load_name, python_load_name)

    @classmethod
    def get_wells_for_labware(cls, load_name: str) -> list[str]:
        """Get the list of wells for a labware type."""
        load_name_lower = load_name.lower()

        if "384" in load_name_lower:
            return cls.WELLS_384
        elif "24" in load_name_lower:
            return cls.WELLS_24
        elif "12_reservoir" in load_name_lower:
            return cls.WELLS_12
        elif "1_reservoir" in load_name_lower:
            return ["A1"]
        elif "6_tuberack" in load_name_lower:
            return [f"{row}{col}" for row in "AB" for col in range(1, 4)]
        elif "15_tuberack" in load_name_lower:
            return [f"{row}{col}" for row in "ABC" for col in range(1, 6)]
        else:
            # Default to 96-well
            return cls.WELLS_96

    @classmethod
    def get_columns_for_labware(cls, load_name: str) -> list[list[str]]:
        """Get columns (lists of wells) for a labware type."""
        wells = cls.get_wells_for_labware(load_name)

        # Group by column number
        columns: dict[int, list[str]] = {}
        for well in wells:
            col_num = int(well[1:])
            if col_num not in columns:
                columns[col_num] = []
            columns[col_num].append(well)

        return [columns[col] for col in sorted(columns.keys())]

    @classmethod
    def get_rows_for_labware(cls, load_name: str) -> list[list[str]]:
        """Get rows (lists of wells) for a labware type."""
        wells = cls.get_wells_for_labware(load_name)

        # Group by row letter
        rows: dict[str, list[str]] = {}
        for well in wells:
            row_letter = well[0]
            if row_letter not in rows:
                rows[row_letter] = []
            rows[row_letter].append(well)

        return [rows[row] for row in sorted(rows.keys())]

    @classmethod
    def is_tip_rack(cls, load_name: str) -> bool:
        """Check if labware is a tip rack."""
        return "tiprack" in load_name.lower()

    @classmethod
    def is_reservoir(cls, load_name: str) -> bool:
        """Check if labware is a reservoir."""
        return "reservoir" in load_name.lower()

    @classmethod
    def is_adapter(cls, load_name: str) -> bool:
        """Check if labware is an adapter."""
        return "adapter" in load_name.lower()

    @classmethod
    def build_location(
        cls,
        slot: Optional[str] = None,
        module_id: Optional[str] = None,
        adapter_id: Optional[str] = None,
        labware_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Build a location object for HTTP API."""
        if labware_id:
            return {"labwareId": labware_id}
        if adapter_id:
            return {"labwareId": adapter_id}
        if module_id:
            return {"moduleId": module_id}
        if slot:
            return {"slotName": slot}
        return {}

    @classmethod
    def build_well_location(
        cls,
        origin: str = "top",
        offset_x: float = 0,
        offset_y: float = 0,
        offset_z: float = 0,
    ) -> dict[str, Any]:
        """Build a well location object for HTTP API."""
        location: dict[str, Any] = {"origin": origin}

        if offset_x != 0 or offset_y != 0 or offset_z != 0:
            location["offset"] = {
                "x": offset_x,
                "y": offset_y,
                "z": offset_z,
            }

        return location
