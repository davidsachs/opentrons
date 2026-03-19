"""
Thermocycler Protocol for Testing

Demonstrates thermocycler operations including lid control,
temperature management, and thermal cycling profiles.
"""

metadata = {
    "protocolName": "Thermocycler Test Protocol",
    "author": "Test Author",
    "description": "Protocol to test thermocycler functionality",
    "apiLevel": "2.19",
}

requirements = {
    "robotType": "OT-3 Standard",
}


def run(protocol):
    # Load thermocycler
    tc = protocol.load_module("thermocycler module gen2", "B1")

    # Load other labware
    tip_rack = protocol.load_labware("opentrons_flex_96_tiprack_200ul", "A1")
    reservoir = protocol.load_labware("nest_12_reservoir_15ml", "A2")

    # Load pipette
    pipette = protocol.load_instrument(
        "flex_8channel_1000",
        "left",
        tip_racks=[tip_rack],
    )

    # Open lid and load plate
    protocol.comment("Opening thermocycler lid")
    tc.open_lid()

    # Load labware on thermocycler
    tc_plate = tc.load_labware("nest_96_wellplate_100ul_pcr_full_skirt")

    # Transfer samples to thermocycler plate
    protocol.comment("Loading samples")
    pipette.pick_up_tip()
    pipette.aspirate(50, reservoir["A1"])
    pipette.dispense(50, tc_plate["A1"])
    pipette.drop_tip()

    # Close lid
    protocol.comment("Closing lid and starting thermal cycling")
    tc.close_lid()

    # Set lid temperature
    tc.set_lid_temperature(105)

    # Set block temperature for denaturation
    tc.set_block_temperature(
        temperature=95,
        hold_time_seconds=300,  # 5 minute initial denaturation
        block_max_volume=50,
    )

    # Execute PCR profile
    protocol.comment("Running PCR cycles")

    profile = [
        {"temperature": 95, "hold_time_seconds": 30},   # Denaturation
        {"temperature": 55, "hold_time_seconds": 30},   # Annealing
        {"temperature": 72, "hold_time_seconds": 60},   # Extension
    ]

    tc.execute_profile(steps=profile, repetitions=30, block_max_volume=50)

    # Final extension
    protocol.comment("Final extension")
    tc.set_block_temperature(
        temperature=72,
        hold_time_seconds=300,  # 5 minutes
        block_max_volume=50,
    )

    # Cool down
    protocol.comment("Cooling to 4°C")
    tc.set_block_temperature(temperature=4)

    # Deactivate and open
    tc.deactivate_lid()
    tc.deactivate_block()
    tc.open_lid()

    protocol.comment("PCR complete")
