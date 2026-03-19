from opentrons import protocol_api, types

metadata = {
    'protocolName': 'pickup and dip labware',
    'author': 'Jon Klar',
    'description': 'Protocol for picking up a labware with the gripper and dipping it at another position without releasing',
}

requirements = {
    'robotType': 'OT-3',
    'apiLevel': '2.23'
}

def run(protocol: protocol_api.ProtocolContext):
    # Loading labware onto the deck is standard for every protocol using the load_labware command.
    # I save extra information like the deck slot string here as variables for easy reference later on in the protocol
    # and only have to change it in one place if you want to move things around on the deck.
    hold_plate_slot = "C1"
    #hold_plate = protocol.load_labware("opentrons_flex_96_filtertiprack_1000ul", hold_plate_slot) #This is the held labware.  I chose one at random fort he example.
    hold_plate_grip_height = 20  # High to hold the plate in mm.  We generally use 1/2 the total height of the labware

    #dip_labware_slot = "C2"
    #dip_labware = protocol.load_labware("nest_96_wellplate_2ml_deep", dip_labware_slot) #this is the labware to be dipped into. I chose one at random for the example.

    #hold_plate_destination = "C3" # This is the slot you want the held labware to be placed down after dipping
    
    # There are 2 custom data structures we will use in this protocol: Point and Location
    # A Point is a single point in 3D space defined by x, y, and z coordinates
    # A Location is a Point plus an optional reference to a labware.  This is what most built in functions will interact with.
    # Most defined positions (like plate.well("A1")) return Location objects.

    # We will be using the function protocol.deck.get_slot_center(slot_name) which returns a Point object for the center of a given deck slot.
    # Because the gripper needs to target the center of what it is picking up, and this is not usually a defined position for a given labware.
    # The returned point will always have 0 for its z coordinate, so we will need to add z offsets to get to the proper height for gripping and dipping.

    def add_z_offset_to_point(point: types.Point, z_offset):
        """Adds a z offset to a Point. Larger positive values are higher above the deck."""
        return types.Point(x=point.x, y=point.y, z=point.z + z_offset)
    
    def add_z_offset_to_location(location: types.Location, z_offset):
        """Adds a z offset to a Location. Larger positive values are higher above the deck."""
        new_point = add_z_offset_to_point(location.point, z_offset)
        return types.Location(point=new_point, labware=location.labware)
    
    def move_gripper_to(destination: types.Location, speed: float = None):
        """helper method to move gripper to a location.  Optionally specify speed."""
        protocol.robot.move_to(
            mount='gripper', 
            destination = destination,
            speed = speed
        )

    def labware_center_location(labware_slot, z_height):
        """Calculate the center location for a given labware for the purpose of gripping it correctly"""
        slot_center = protocol.deck.get_slot_center(labware_slot)
        return types.Location(
            point = (add_z_offset_to_point(
                slot_center, 
                (z_height)
                )
            ), 
            labware=None
        )
    
    DIP_SPEED = 10 # speed for dipping motion
    DIP_HEIGHT = 70 # height above deck to dip labware
    CEILING_HEIGHT = 120 # height above deck to perform lateral movement and avoid collisions when moving labware around the deck. Will throw an error if this is set too high.

    # Since we are using lower level control functions to control the gripper movement, the robot will not automatically avoid collisions for us.
    # It will move in a straight line from one position to the next, so we define way points here to ensure it avoids any labware on the deck.
    # The waypoints are enumerated in order of movement. i.e. 2---3---5
    #                                                         |   |   |
    #                                                         1   4   6
    # They are defined out of order because I chose to define the positions closest to the deck first, and then add offsets for the higher positions.
    POSITION_1 = labware_center_location(hold_plate_slot, hold_plate_grip_height)  # center of hold plate at the grip height of labware
    #POSITION_2 = add_z_offset_to_location(POSITION_1, CEILING_HEIGHT - hold_plate_grip_height)  # 100 mm above position 1. Attempting to keep a consistent ceiling of 120mm above the deck, but this is not a hard requirement.
    #POSITION_4 = labware_center_location(dip_labware_slot, DIP_HEIGHT)  # bottom point of dipping motion
    #POSITION_3 = add_z_offset_to_location(POSITION_4, CEILING_HEIGHT - DIP_HEIGHT) # 50 mm above dip location.  
    #POSITION_6 = labware_center_location(hold_plate_destination, hold_plate_grip_height)  # center of destination hold plate location at the grip height of labware.  
    #POSITION_5 = add_z_offset_to_location(POSITION_6, CEILING_HEIGHT - hold_plate_grip_height)  # 100 mm above destination hold plate location

    # This set of commands is what is actually commanding the robot to move
    #protocol.robot.open_gripper_jaw() 
    move_gripper_to(POSITION_1) 
    #protocol.robot.close_gripper_jaw()
    #move_gripper_to(POSITION_2)
    #move_gripper_to(POSITION_3)
    #move_gripper_to(POSITION_4, speed = DIP_SPEED) #Speed can be added as an optional parameter
    #protocol.delay(seconds = 120)  # hold labware in the dip position for 2 minutes
    #move_gripper_to(POSITION_3, speed = DIP_SPEED)
    #move_gripper_to(POSITION_5)
    #move_gripper_to(POSITION_6)
    #protocol.robot.open_gripper_jaw()
    #protocol.home() # I recommend homing after completing low level gripper movements before using standerd liquid handling commands again.

    # One of the quirks of using low level gripper commands is that the robot does not automatically update its internal state of where labware is located on the deck.
    # So we have to manually tell the robot that we have moved the held labware to a new location using the move_labware command.
    # I use a lower level move_labware command here to avoid having to pause.
    #protocol._core.move_labware(
    #    hold_plate._core, 
    #    types.DeckSlotName.from_primitive(hold_plate_destination), # DeckSlotName is another data structure used to define deck slots originally intended for internal use.
    #    use_gripper=False, 
    #    pause_for_manual_move=False, 
    #    pick_up_offset=None, 
    #    drop_offset=None)


