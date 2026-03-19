# Opentrons Control GUI - Quick Reference

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| **Tab** | Pause/Resume protocol |
| **Enter** | Execute command or step through protocol |
| **Ctrl+L** | Load protocol file |
| **Ctrl+U** | Upload media change CSV |
| **+/-** | Resize deck visualizer |
| **ESC** | Quit immediately |

## Mouse Controls (Right Panel)

| Modifier + Drag | Action |
|-----------------|--------|
| **Ctrl + Drag** | Move Opentrons X/Y (yellow line) |
| **Shift + Drag** | Move Microscope X/Y (magenta line) |

*Scaling: Full video width = 2.5mm movement*

## Movement Commands

```
RELATIVE MOVEMENT          ABSOLUTE MOVEMENT
X10    → move +10mm X      GX200  → go to X=200
Y-5    → move -5mm Y       GY150  → go to Y=150
Z2     → move +2mm Z       GZ50   → go to Z=50

COMBINED: X10 Y10 F50  (diagonal at 50mm/s)
```

## Position Memory

```
SET0  → Save current position as #0
SET1  → Save current position as #1
G0    → Move to saved position #0
G1    → Move to saved position #1
```

## Instrument Control

```
P1  → Select left pipette
P2  → Select right pipette
P3  → Select gripper
GO  → Open gripper
GC  → Close gripper
H   → Home all axes
```

## Pipette Commands

```
PA50    → Aspirate 50µL
PD50    → Dispense 50µL
PRAT10  → Set flow rate to 10µL/s
```

## Protocol Control

```
Tab   → Pause/Resume (protocols start PAUSED)
Enter → Step through when paused
R     → Restart from beginning
Q     → Quit
```

## Microscope Commands (Right Panel)

```
MOVEMENT               LIGHTS (0-1)           IMAGING MODE
X# Y# Z#  relative     LH#   brightfield      I0  microscope
F#        feedrate     LLA# LLB# LLC# oblique I1  processing
                       LA# LB#   fluorescence I2  both
                                              I3  projector

PROJECTOR
PROJI#   illuminate for # seconds
PROJR    show chip reference (drag with mouse)
PROJM*   set mask by name (drag with mouse)
PROJS*   set video by name
PROJIS   illuminate video
```

## Deck Visualizer Colors

- **Cyan** = Tip racks
- **Green** = Well plates
- **Blue** = Reservoirs
- **Red** = Tube racks
- **Yellow dotted** = Destination slots
- **Yellow circle** = Starting position

## CSV Format for Media Change

```csv
#Tube locations
A1_tube,reagent_name

#Plate layout
A1_plate,reagent1,volume1,reagent2,volume2
```

## Common Workflows

### Run a Protocol
1. Press **Ctrl+L** → select protocol file
2. Press **Tab** to start
3. Press **Tab** to pause anytime
4. Press **Enter** to step manually

### Manual Position Adjustment
1. Pause protocol (**Tab**)
2. Type commands: `X5`, `Y-2`, `Z1`
3. Save position: `SET0`
4. Resume: **Tab**

### Use Saved Position in Protocol
Protocol can use: `protocol.comment("G0")` to move to saved position

## Protocols Summary

| Protocol | Purpose | Key Feature |
|----------|---------|-------------|
| `seeding_test_2` | Pick up spheroid | Manual chip positioning |
| `washing_out` | Wash hydrogel | Slow 2µL/s flow rate |
| `spheroid_media_change` | Change culture media | CSV-configurable reagents |
| `lid_test_3` | Test gripper | Lid/plate movement |

## Emergency

**ESC** - Immediately quit application
