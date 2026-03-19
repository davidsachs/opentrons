"""
Complex Opentrons Protocol for Testing

Demonstrates advanced features including modules, complex liquid handling,
and various pipette operations.
"""

metadata = {
    "protocolName": "Complex Test Protocol",
    "author": "Test Author",
    "description": "A complex protocol testing various features",
    "apiLevel": "2.19",
}

requirements = {
    "robotType": "OT-3 Standard",
}


def run(protocol):
    # Load modules
    temp_module = protocol.load_module("temperature module gen2", "B1")
    heater_shaker = protocol.load_module("heater-shaker", "B3")

    # Load labware
    tip_rack_1 = protocol.load_labware("opentrons_flex_96_tiprack_1000ul", "A1")
    tip_rack_2 = protocol.load_labware("opentrons_flex_96_tiprack_200ul", "A2")

    # Labware on modules
    temp_plate = temp_module.load_labware("nest_96_wellplate_100ul_pcr_full_skirt")
    hs_plate = heater_shaker.load_labware("nest_96_wellplate_2ml_deep")

    # Regular labware
    source_plate = protocol.load_labware("nest_96_wellplate_200ul_flat", "C1")
    dest_plate = protocol.load_labware("nest_96_wellplate_200ul_flat", "C2")
    reservoir = protocol.load_labware("nest_12_reservoir_15ml", "D1")

    # Load pipettes
    p1000 = protocol.load_instrument(
        "flex_1channel_1000",
        "left",
        tip_racks=[tip_rack_1],
    )
    p50 = protocol.load_instrument(
        "flex_8channel_50",
        "right",
        tip_racks=[tip_rack_2],
    )

    # Load waste
    trash = protocol.load_trash_bin("A3")

    # Define liquids
    water = protocol.define_liquid(
        name="Water",
        description="Sterile water",
        display_color="#0000FF",
    )
    sample = protocol.define_liquid(
        name="Sample",
        description="Sample solution",
        display_color="#FF0000",
    )

    # Module operations
    protocol.comment("Setting up modules")

    # Temperature module
    temp_module.set_temperature(4)
    temp_module.await_temperature(4)

    # Heater-shaker
    heater_shaker.close_labware_latch()
    heater_shaker.set_target_temperature(37)
    heater_shaker.wait_for_temperature()

    # Complex liquid handling with p1000
    protocol.comment("Complex liquid handling")

    # Transfer with mixing
    p1000.pick_up_tip()

    # Aspirate with specific well position
    p1000.aspirate(200, reservoir["A1"].bottom(z=2))
    p1000.touch_tip()
    p1000.air_gap(20)

    # Dispense with blow out
    p1000.dispense(200, source_plate["A1"].top(z=-5))
    p1000.blow_out(source_plate["A1"].top())

    p1000.drop_tip()

    # Mix operation
    p1000.pick_up_tip()
    p1000.mix(3, 150, source_plate["A1"])
    p1000.drop_tip()

    # Transfer command
    protocol.comment("Using transfer command")
    p1000.transfer(
        100,
        source_plate.wells()[:4],
        dest_plate.wells()[:4],
        new_tip="always",
        touch_tip=True,
        mix_after=(2, 50),
    )

    # Distribute command
    protocol.comment("Using distribute command")
    p1000.distribute(
        50,
        reservoir["A2"],
        source_plate.columns()[1],
        disposal_volume=10,
    )

    # Consolidate command
    protocol.comment("Using consolidate command")
    p1000.consolidate(
        30,
        source_plate.columns()[0],
        dest_plate["A12"],
        air_gap=10,
    )

    # 8-channel operations
    protocol.comment("8-channel operations")
    p50.pick_up_tip()
    p50.aspirate(30, reservoir["A3"])
    p50.dispense(30, source_plate["A1"])
    p50.return_tip()

    # Heater-shaker shake
    protocol.comment("Shaking sample")
    heater_shaker.set_and_wait_for_shake_speed(500)
    protocol.delay(seconds=30)
    heater_shaker.deactivate_shaker()

    # Move labware with gripper
    protocol.comment("Moving labware")
    heater_shaker.open_labware_latch()
    protocol.move_labware(hs_plate, "D2", use_gripper=True)

    # Cleanup modules
    protocol.comment("Cleaning up")
    temp_module.deactivate()
    heater_shaker.deactivate_heater()

    protocol.comment("Protocol complete")
