from opentrons import protocol_api
from opentrons.types import Point

metadata = {
    'protocolName': 'Gripper Lid and Plate Movement',
    'author': 'OpentronsAI',
    'description': 'Move lid from plate at C2 to B2, move plate to D2, then move lid back onto plate',
    'source': 'OpentronsAI'
}
 
requirements = {
    'robotType': 'Flex',
    'apiLevel': '2.22'
}

def run(protocol: protocol_api.ProtocolContext):
    
    # -------------------------------------------------------------------------
    # CONSTANTS
    # -------------------------------------------------------------------------
    # The approximate height of the Corning 96 plate is 14.2 mm.
    # The gripper needs to know the lid is starting this high up.
    PLATE_HEIGHT_MM = 14.2

    # -------------------------------------------------------------------------
    # STEP 1: LOAD & REMOVE LID
    # -------------------------------------------------------------------------
    # We load the LID at C2. 
    # Logic: The robot thinks C2 contains *only* a lid right now.
    lid = protocol.load_labware(
        'opentrons_tough_pcr_auto_sealing_lid', 
        'C2', 
        'Plate Lid'
    )
    
    # Optional trash bin
    trash = protocol.load_trash_bin('A3')

    protocol.comment("Step 1: Removing lid from C2 to B2")

    # Move lid to B2.
    # FIX: We use a dictionary {'x':.., 'y':.., 'z':..} instead of Point()
    protocol.move_labware(
        labware=lid,
        new_location='B2',
        use_gripper=True,
        pick_up_offset={'x': 0, 'y': 0, 'z': PLATE_HEIGHT_MM}
    )

    # -------------------------------------------------------------------------
    # STEP 2: LOAD & MOVE PLATE
    # -------------------------------------------------------------------------
    # Now that the lid is at B2, slot C2 is logically empty.
    # We load the PLATE into C2 so the robot knows where to grab the next item.
    plate = protocol.load_labware(
        'corning_96_wellplate_360ul_flat', 
        'C2',
        'Cell Culture Plate'
    )

    protocol.comment("Step 2: Moving Plate from C2 to D2")

    protocol.move_labware(
        labware=plate,
        new_location='D2',
        use_gripper=True
    )

    # -------------------------------------------------------------------------
    # STEP 3: REPLACE LID
    # -------------------------------------------------------------------------
    protocol.comment("Step 3: Replacing Lid from B2 onto Plate at D2")

    # Move lid from B2 back onto the Plate (now at D2).
    # Setting new_location=plate tells the API to stack it.
    protocol.move_labware(
        labware=lid,
        new_location=plate,
        use_gripper=True,
        drop_offset={'x': 0, 'y': 0, 'z': 2} # 2mm extra height to clear the lip
    )