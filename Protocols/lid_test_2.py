import json
from opentrons import protocol_api, types

metadata = {
    "protocolName": "Lid movement test",
    "author": "adsf",
    "description": "asdf",
    "created": "2026-01-01T22:18:55.229Z",
    "internalAppBuildDate": "Tue, 16 Dec 2025 16:02:03 GMT",
    "lastModified": "2026-01-01T22:21:41.440Z",
    "protocolDesigner": "8.7.1",
    "source": "Protocol Designer",
}

requirements = {"robotType": "Flex", "apiLevel": "2.26"}

# =============================================================================
# SPHEROID PLATE SLOT OFFSET
# Adjust these to fine-tune the plate position in slot C3
# All values are in mm
# =============================================================================

SPHEROID_PLATE_X_OFFSET = 42.25   # mm: positive = right, negative = left
SPHEROID_PLATE_Y_OFFSET = 0.0     # mm: positive = back, negative = front
SPHEROID_PLATE_Z_OFFSET = 0.0     # mm: positive = up, negative = down

def run(protocol: protocol_api.ProtocolContext) -> None:
    # Load Labware:
    spheroid_plate = protocol.load_labware(
        "corning_96_wellplate_360ul_flat",
        location="C3",
        namespace="opentrons",
        version=4,
        lid="corning_96_wellplate_360ul_lid",
        lid_namespace="opentrons",
        lid_version=1,
    )

    # Note: set_offset() only affects pipette operations, NOT gripper operations
    # For gripper moves, use pick_up_offset and drop_offset parameters instead
    spheroid_plate.set_offset(
        x=SPHEROID_PLATE_X_OFFSET,
        y=SPHEROID_PLATE_Y_OFFSET,
        z=SPHEROID_PLATE_Z_OFFSET
    )

    # Gripper offset dict - used for pick_up_offset and drop_offset parameters
    gripper_offset = {
        "x": SPHEROID_PLATE_X_OFFSET,
        "y": SPHEROID_PLATE_Y_OFFSET,
        "z": SPHEROID_PLATE_Z_OFFSET
    }

    # Load Pipettes:
    #pipette_left = protocol.load_instrument("flex_8channel_50", "left")

    # Load Trash Bins:
    trash_bin_1 = protocol.load_trash_bin("A3")
    #550.6, 149.5, 70.5/39.5

    # PROTOCOL STEPS
    # Move gripper to offset position for visual check
    slot_center = protocol.deck.get_slot_center("C3")
    slot_center = types.Point(
        x=slot_center.x + SPHEROID_PLATE_X_OFFSET,
        y=slot_center.y + SPHEROID_PLATE_Y_OFFSET,
        z=164
    )
    slot_center = types.Location(point=slot_center, labware=None)

    protocol.robot.move_to(mount='gripper', destination=slot_center)
    #protocol.delay(seconds = 5)
    protocol.comment("Pause.")

    # Move lid from plate (at offset position) to B3
    protocol.move_lid(spheroid_plate, "B3", use_gripper=True, pick_up_offset=gripper_offset)

    # Move plate from C3 (at offset) to D3
    protocol.move_labware(spheroid_plate, "D3", use_gripper=True, pick_up_offset=gripper_offset)

    # Move plate from D3 back to C3 (drop at offset position)
    protocol.move_labware(spheroid_plate, "C3", use_gripper=True, drop_offset=gripper_offset)

    # Move lid from B3 back onto plate (at offset position)
    protocol.move_lid("B3", spheroid_plate, use_gripper=True, drop_offset=gripper_offset)

    
#DESIGNER_APPLICATION = """{"robot":{"model":"OT-3 Standard"},"designerApplication":{"name":"opentrons/protocol-designer","version":"8.7.0","data":{"pipetteTiprackAssignments":{"495b79ba-5da3-49c1-8aa7-61daddb7e25f":["opentrons/opentrons_flex_96_filtertiprack_50ul/1"]},"dismissedWarnings":{"form":[],"timeline":[]},"ingredients":{},"ingredLocations":{},"savedStepForms":{"__INITIAL_DECK_SETUP_STEP__":{"stepType":"manualIntervention","id":"__INITIAL_DECK_SETUP_STEP__","labwareLocationUpdate":{"4c195197-5d4f-4635-985e-73d7f130dbdb:opentrons/corning_96_wellplate_360ul_flat/5":"C2","dc05cfe6-f476-48c8-92bf-2724d2e24de8:opentrons/corning_96_wellplate_360ul_lid/1":"4c195197-5d4f-4635-985e-73d7f130dbdb:opentrons/corning_96_wellplate_360ul_flat/5"},"pipetteLocationUpdate":{"495b79ba-5da3-49c1-8aa7-61daddb7e25f":"left"},"moduleLocationUpdate":{},"trashBinLocationUpdate":{"7afffad1-3937-49fa-ba57-47feef895633:trashBin":"cutoutA3"},"wasteChuteLocationUpdate":{},"stagingAreaLocationUpdate":{},"gripperLocationUpdate":{"d663b480-f3b1-439a-8cbc-d5a64dc251f2:gripper":"mounted"}},"94e9965c-1193-4d84-a658-61e3cc5cfa71":{"id":"94e9965c-1193-4d84-a658-61e3cc5cfa71","stepType":"moveLabware","stepName":"move","stepDetails":"","stepNumber":0,"labware":"dc05cfe6-f476-48c8-92bf-2724d2e24de8:opentrons/corning_96_wellplate_360ul_lid/1","newLocation":"D2","useGripper":true},"750ab668-e542-4292-9a3b-ae0f65daff78":{"id":"750ab668-e542-4292-9a3b-ae0f65daff78","stepType":"moveLabware","stepName":"move","stepDetails":"","stepNumber":0,"labware":"4c195197-5d4f-4635-985e-73d7f130dbdb:opentrons/corning_96_wellplate_360ul_flat/5","newLocation":"B2","useGripper":true},"030e7cd7-679e-4f3c-b43b-f738eb5c4c6c":{"id":"030e7cd7-679e-4f3c-b43b-f738eb5c4c6c","stepType":"moveLabware","stepName":"move","stepDetails":"","stepNumber":0,"labware":"dc05cfe6-f476-48c8-92bf-2724d2e24de8:opentrons/corning_96_wellplate_360ul_lid/1","newLocation":"4c195197-5d4f-4635-985e-73d7f130dbdb:opentrons/corning_96_wellplate_360ul_flat/5","useGripper":true}},"orderedStepIds":["94e9965c-1193-4d84-a658-61e3cc5cfa71","750ab668-e542-4292-9a3b-ae0f65daff78","030e7cd7-679e-4f3c-b43b-f738eb5c4c6c"],"pipettes":{"495b79ba-5da3-49c1-8aa7-61daddb7e25f":{"pipetteName":"p50_multi_flex"}},"modules":{},"labware":{"4c195197-5d4f-4635-985e-73d7f130dbdb:opentrons/corning_96_wellplate_360ul_flat/5":{"displayName":"Corning 96 Well Plate 360 µL Flat","labwareDefURI":"opentrons/corning_96_wellplate_360ul_flat/5"},"dc05cfe6-f476-48c8-92bf-2724d2e24de8:opentrons/corning_96_wellplate_360ul_lid/1":{"displayName":"Corning 96 Wellplate 360ul Lid","labwareDefURI":"opentrons/corning_96_wellplate_360ul_lid/1"}}}},"metadata":{"protocolName":"asdf","author":"adsf","description":"asdf","source":"Protocol Designer","created":1767305935229,"lastModified":1767306101440}}"""
