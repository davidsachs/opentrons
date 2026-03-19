# Opentrons Control GUI - User Guide

## Table of Contents
1. [Quick Start Tutorial](#quick-start-tutorial)
2. [Interface Overview](#interface-overview)
3. [Keyboard Controls](#keyboard-controls)
4. [Manual Commands](#manual-commands)
5. [Protocol Reference](#protocol-reference)
6. [CSV Media Change Upload](#csv-media-change-upload)
7. [Troubleshooting](#troubleshooting)

---

## Quick Start Tutorial

### Step 1: Launch the Application

Shortcuts are on the desktop (Windows-D shortcut to view the desktop). Make sure the projector is connected to the mobile hotspot (should see "DLP"). If not, turn the hotspot off and on (settings->network & internet->mobile hotspot), unplug and replug the projector. Start the microscope with "Microscope" shortcut. You can use all microscope features directly from there, if not pipetting, otherwise start the "Opentrons" shortcut. 

### Step 2: Connect to Robot

The application automatically connects to the robot at the configured IP address. You'll see:
- **Live video feed** from the robot's camera
- **Status bar** showing connection state and current position
- **Deck visualizer** (bottom-left) showing labware layout

### Step 3: Load a Protocol

Click "Load Protocol" or press **Ctrl+L** to open the file dialog and select a protocol file (`.py`).

The deck visualizer will update to show:
- Labware positions on the deck
- Protocol name at the top
- Destination slots (dotted borders) where labware will move

### Step 4: Run the Protocol

1. **Protocols start PAUSED** - This is intentional for safety
2. Press **Tab** to begin execution
3. The protocol will run automatically, pausing at any `protocol.comment("Pause.")` statements
4. Press **Tab** again to pause/resume at any time
5. Press **Enter** to manually step through commands when paused

### Step 5: Manual Adjustments

While paused, you can:
- Type movement commands (e.g., `X5` to move 5mm in X)
- Save positions with `SET0`, `SET1`, etc.
- Move to saved positions with `G0`, `G1`, etc.
- Control the gripper with `GO` (open) and `GC` (close)

---

## Interface Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     LIVE VIDEO FEED                         │
│                                                             │
│  ┌─────────────────┐                                        │
│  │ Deck Visualizer │                                        │
│  │                 │                                        │
│  │ [Protocol Name] │                                        │
│  │ ┌───┬───┬───┬───┤                                        │
│  │ │A1 │A2 │A3 │A4 │                                        │
│  │ ├───┼───┼───┼───┤                                        │
│  │ │B1 │B2 │B3 │B4 │                                        │
│  │ └───┴───┴───┴───┘                                        │
│  └─────────────────┘                                        │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│ Status: Protocol loaded | Step 5/42 | PAUSED                │
│ Position: X=245.3 Y=150.2 Z=100.5                          │
│ Command: _                                                  │
└─────────────────────────────────────────────────────────────┘
```

### Deck Visualizer Colors
- **Cyan** - Tip racks
- **Green** - Well plates
- **Blue** - Reservoirs
- **Red** - Tube racks
- **Dark gray** - Empty slots
- **Yellow dotted border** - Protocol destination (empty slot that will be used)
- **Yellow highlight** - Starting position markers

---

## Keyboard Controls

| Key | Action |
|-----|--------|
| **Enter** | Execute typed command, or step through paused protocol |
| **Tab** | Pause/Resume protocol execution |
| **Ctrl+L** | Load protocol file (opens file dialog) |
| **Ctrl+U** | Upload media change CSV (generates protocol) |
| **ESC** | Quit application immediately |

## Manual Commands

### Movement Commands

| Command | Description | Example |
|---------|-------------|---------|
| `X#` | Move relative in X axis (mm) | `X10` moves +10mm, `X-5` moves -5mm |
| `Y#` | Move relative in Y axis (mm) | `Y-20` moves -20mm |
| `Z#` | Move relative in Z axis (mm) | `Z5` moves up 5mm |
| `GX#` | Move to absolute X position | `GX200` moves to X=200mm |
| `GY#` | Move to absolute Y position | `GY150` |
| `GZ#` | Move to absolute Z position | `GZ50` |
| `F#` | Set feedrate/speed (mm/s) | `F50` sets speed to 50mm/s |
| `F0` | Reset to default speed | |

**Combined movements**: You can combine commands in one line:
- `X10 Y10` - Diagonal move
- `GX200 GY150 GZ50` - Move to absolute position
- `X5 F20` - Move with specific speed

### Position Memory

| Command | Description |
|---------|-------------|
| `SET0` | Save current position as location 0 |
| `SET1` | Save current position as location 1 |
| `SET#` | Save position (0-9 available) |
| `G0` | Move to saved location 0 |
| `G1` | Move to saved location 1 |
| `G#` | Move to saved location |

### Instrument Control

| Command | Description |
|---------|-------------|
| `P1` | Select left pipette |
| `P2` | Select right pipette |
| `P3` | Select gripper |
| `GO` | Open gripper |
| `GC` | Close gripper |
| `H` | Home all axes |

### Pipette Commands

| Command | Description | Example |
|---------|-------------|---------|
| `PA#` | Aspirate volume (µL) | `PA50` aspirates 50µL |
| `PD#` | Dispense volume (µL) | `PD50` dispenses 50µL |
| `PRAT#` | Set pipette rate (µL/s) | `PRAT10` sets 10µL/s |

### Protocol Control

| Command | Description |
|---------|-------------|
| `R` | Restart protocol from beginning |
| `Q` | Quit application |

---

## Microscope Commands

### Movement Commands

| Command | Description | Example |
|---------|-------------|---------|
| `X#` | Move relative in X axis (mm) | `X0.5` moves +0.5mm |
| `Y#` | Move relative in Y axis (mm) | `Y-0.2` moves -0.2mm |
| `Z#` | Move relative in Z axis (mm) | `Z0.1` moves up 0.1mm |
| `F#` | Set feedrate/speed (mm/s) | `F10` sets speed to 10mm/s |

### Light Controls

All light intensities range from 0 (off) to 1 (full brightness).

| Command | Description | Example |
|---------|-------------|---------|
| `LH#` | Brightfield illuminator (high light) | `LH0.5` sets to 50% |
| `LLA#` | Oblique illuminator A (low light) | `LLA0.8` |
| `LLB#` | Oblique illuminator B | `LLB0.5` |
| `LLC#` | Oblique illuminator C | `LLC0.3` |
| `LA#` | Fluorescence LED A | `LA1` full brightness |
| `LB#` | Fluorescence LED B | `LB0.7` |

### Imaging Mode

| Command | Description |
|---------|-------------|
| `I0` | Microscope only |
| `I1` | Image processing only |
| `I2` | Microscope + image processing |
| `I3` | Projector mode |

### Projector Commands

| Command | Description | Example |
|---------|-------------|---------|
| `PROJI#` | Illuminate for # seconds | `PROJI5` illuminates for 5 seconds |
| `PROJR` | Display chip reference (can be dragged with mouse) | |
| `PROJM*` | Set mask by name (can be dragged with mouse) | `PROJMMULTI` |
| `PROJS*` | Set projector video by name | `PROJSLV` |
| `PROJIS` | Illuminate current video | |

---

## Protocol Reference

### 1. Spheroid Seeding Test (`seeding_test_2.py`)

**Purpose**: Pick up a spheroid from a well plate and deposit it into a microfluidic chip.

**Deck Layout**:
- **B2**: 1000µL filter tip rack
- **D3**: 96-well plate (spheroid source)
- **A3**: Trash bin

**Workflow**:
1. Pick up a single tip (H1 nozzle configuration)
2. Move to chip position (absolute coordinates)
3. Pause for manual positioning. SET0 to record position
4. Aspirate from well plate A1 to dislodge spheroid (slow rate: 10µL/s)
5. Dispense partially to unstick spheroid
6. Aspirate again to pick up spheroid (30µL/s)
7. G0 to move back to chip and pause for manual insertion
8. Drop tip

**Key Parameters**:
- `unstick_rate = 10` µL/s - Gentle aspiration to dislodge spheroid
- `pickup_rate = 30` µL/s - Aspiration rate for pickup
- Chip position: X=400, Y=140, Z=50 (adjustable)

**Pause Points**:
- After moving to chip position (for manual adjustment)
- Before dispensing into chip (`G0` and `Pause` comments)

---

### 2. Hydrogel Washing (`washing_out.py`)

**Purpose**: Wash out hydrogel from a microfluidic chip using gentle flow.

**Deck Layout**:
- **B2**: 1000µL filter tip rack
- **D3**: 96-well plate (washing media source)
- **C3**: Placeholder for chip position
- **A3**: Trash bin

**Workflow**:
1. Pick up single tip
2. Aspirate 100µL washing media from well plate
3. Move to chip and pause for manual positioning
4. Dispense 50µL at slow rate (2µL/s)
5. Perform 3 wash cycles (aspirate/dispense 25µL each)
6. Blow out remaining liquid back to well plate
7. Drop tip

**Key Parameters**:
- `washing_rate = 2` µL/s - Very slow for gentle washing

**Pause Points**:
- After moving to chip (`Pause.` comment)

---

### 3. Spheroid Media Change (`spheroid_media_change.py`)

**Purpose**: Automated media change with custom reagent cocktails for spheroid culture.

**Deck Layout**:
- **B1**: 50µL filter tips (reagent dispensing)
- **B2**: 1000µL filter tips (bulk operations)
- **C1**: Custom 2-well reservoir (A1=fresh media, A2=waste)
- **C3**: Spheroid plate (with X offset for custom positioning)
- **D2**: 24-tube rack (reagent tubes)
- **D3**: New media assembly plate
- **A3**: Trash bin

**Workflow**:

**Step 1: Assemble New Media**
- Add base media (150µL) to assembly plate using 8-channel p1000
- Add reagents from tube rack using single-tip p50
- Each reagent is mixed before distribution

**Step 2: Wash Spheroids**
- Remove old media from spheroid plate → waste (slow aspiration)
- Add fresh base media from reservoir (slow dispense)

**Step 3: Transfer Assembled Media**
- Remove wash media → waste
- Mix assembled media and transfer to spheroid plate

**Key Parameters**:
- `SLOW_FLOW_RATE = 50` µL/s - Gentle for spheroid wells
- `DEFAULT_FLOW_RATE = 160` µL/s - Normal operations
- `BASE_MEDIA_VOLUME = 150` µL per well
- `WASH_VOLUME = 100` µL
- `TRANSFER_VOLUME = 100` µL

**Configurable Offsets**:
```python
TIPRACK_50_OFFSET = (6, 0)      # Skip 6 columns of 50µL tips
TIPRACK_1000_OFFSET = (0, 0)    # Start at column 1
SPHEROID_PLATE_X_OFFSET = 42.25 # mm offset for custom plate position
```

**CSV Configuration**: See [CSV Media Change Upload](#csv-media-change-upload)

---

### 4. Lid Movement Test (`lid_test_3.py`)

**Purpose**: Test gripper operations for lid handling and plate movement.

**Deck Layout**:
- **A1**: 96-well plate with lid
- **A2**: Temporary lid storage (empty)
- **B3**: Temporary plate storage (empty)
- **A3**: Trash bin

**Workflow**:
1. Remove lid from plate (A1 → A2)
2. Move plate to temporary location (A1 → B3)
3. Move plate back (B3 → A1)
4. Replace lid on plate (A2 → A1)

**Key Functions Used**:
- `protocol.move_lid()` - Move lid between locations
- `protocol.move_labware()` - Move plate with gripper

---

## CSV Media Change Upload

### Overview

Press **Ctrl+U** to upload a CSV file that defines your media change configuration. This generates a customized protocol automatically.

### CSV Format

```csv
#Starting reagent locations
A1_tube,activin_a
A2_tube,bmp4
A3_tube,fgf
A4_tube,chir
A5_tube,ascorbic_acid

#Plate layout
A1_plate,activin_a,1,bmp4,1,chir,1,ascorbic_acid,1,fgf,1
B1_plate,activin_a,2,bmp4,1,chir,1,ascorbic_acid,1,fgf,1
C1_plate,activin_a,3,bmp4,2,chir,1,ascorbic_acid,1,fgf,1
```

### Format Rules

1. **Comments**: Lines starting with `#` are ignored
2. **Tube locations**: `WELL_tube,reagent_name`
   - Example: `A1_tube,activin_a` means activin_a is in tube rack well A1
3. **Plate layout**: `WELL_plate,reagent1,volume1,reagent2,volume2,...`
   - Example: `A1_plate,activin_a,1,bmp4,2` means well A1 gets 1µL activin_a and 2µL bmp4

### What Happens

1. You select a CSV file
2. The system parses reagent locations and plate layout
3. A new protocol file is generated: `{csv_name}_protocol.py`
4. The protocol is automatically loaded
5. Deck visualizer updates to show the new configuration

---

## Troubleshooting

### Video Feed Not Showing
- Check robot IP address is correct
- Ensure video server is running on robot
- Try reconnecting (the app auto-reconnects after failures)

### Protocol Won't Load
- Check for Python syntax errors in protocol file
- Ensure all required labware definitions exist
- Check API level compatibility

### Deck Visualizer Empty
- Protocol may have failed to analyze
- Check console output for errors
- Ensure protocol has valid labware definitions

### Commands Not Working
- Ensure robot is homed (`H` command)
- Check if protocol is paused (Tab to toggle)
- Verify active instrument is correct (P1/P2/P3)

### Position Memory Lost
- Positions are cleared when loading new protocol
- Save positions again after protocol load
- Positions are saved per-session only

---

## Safety Notes

1. **Always home the robot** before starting operations
2. **Protocols start paused** - Press Tab to begin
3. **Use slow feedrates** when near labware
4. **Watch for collisions** during manual movements
5. **The ESC key** immediately quits (use for emergencies)
6. **Save positions** before complex manual operations

---

## Quick Reference Card

```
MOVEMENT          POSITIONS         INSTRUMENTS
X# Y# Z#  rel     SET0-9 save      P1 left pipette
GX# GY# GZ# abs   G0-9   goto      P2 right pipette
F#  speed         H      home      P3 gripper
                                   GO/GC open/close

PROTOCOL          PIPETTE          KEYBOARD
Tab  pause/run    PA# aspirate     Ctrl+L load protocol
R    restart      PD# dispense     Ctrl+U upload CSV
Enter step        PRAT# rate       +/- visualizer size
                                   ESC quit
```
