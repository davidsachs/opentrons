"""
Example protocol showing how to use the calibrated custom 2-well reservoir.

The custom labware definition is loaded from a JSON file and can be used
in any protocol without re-calibrating.
"""

from opentrons import protocol_api
import json

metadata = {
    'protocolName': 'Example Using Custom Reservoir',
    'author': 'David Sachs',
    'description': 'Demonstrates loading custom labware from JSON file',
}

requirements = {"robotType": "Flex", "apiLevel": "2.19"}


def run(protocol: protocol_api.ProtocolContext):
    """Main protocol execution."""

    # Load the custom labware definition from JSON file
    # The definition is embedded in the protocol at analysis time
    custom_reservoir_def = {
        "ordering": [["A1"], ["A2"]],
        "brand": {"brand": "Custom", "brandId": ["custom-2-reservoir"]},
        "metadata": {
            "displayName": "Custom 2-Well Reservoir 50mL",
            "displayCategory": "reservoir",
            "displayVolumeUnits": "mL",
            "tags": []
        },
        "dimensions": {
            "xDimension": 127.76,
            "yDimension": 85.47,
            "zDimension": 64.0
        },
        "wells": {
            "A1": {
                "depth": 40.0,
                "totalLiquidVolume": 50000,
                "shape": "rectangular",
                "xDimension": 55.0,
                "yDimension": 70.0,
                "x": 40.0,
                "y": 55.0,
                "z": 25.0
            },
            "A2": {
                "depth": 40.0,
                "totalLiquidVolume": 50000,
                "shape": "rectangular",
                "xDimension": 55.0,
                "yDimension": 70.0,
                "x": 90.76,
                "y": 55.0,
                "z": 25.0
            }
        },
        "groups": [{"metadata": {"wellBottomShape": "flat"}, "wells": ["A1", "A2"]}],
        "parameters": {
            "format": "irregular",
            "quirks": [],
            "isTiprack": False,
            "isMagneticModuleCompatible": False,
            "loadName": "custom_2_reservoir_50ml"
        },
        "namespace": "custom_labware",
        "version": 1,
        "schemaVersion": 2,
        "cornerOffsetFromSlot": {"x": 0, "y": 0, "z": 0}
    }

    # Load tip rack
    tiprack = protocol.load_labware(
        'opentrons_flex_96_filtertiprack_1000ul',
        'A2',
        label='1000uL Tips'
    )

    # Load custom reservoir using the definition
    reservoir = protocol.load_labware_from_definition(
        custom_reservoir_def,
        'D1',  # Can be any slot
        label='Custom 2-Reservoir'
    )

    # Load pipette
    pipette = protocol.load_instrument(
        'flex_8channel_1000',
        'right',
        tip_racks=[tiprack]
    )

    # Now use the reservoir like any other labware
    pipette.pick_up_tip()

    # Access wells normally - positions are already calibrated
    pipette.aspirate(500, reservoir['A1'].bottom(0))
    pipette.dispense(500, reservoir['A2'].bottom(10))
    pipette.blow_out(reservoir['A2'].top(-5))

    pipette.return_tip()
