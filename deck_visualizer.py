#!/usr/bin/env python3
"""
Deck Visualizer for Opentrons Protocols

Provides a visual preview of the deck layout, labware, and reagent distributions.
Runs as a persistent second window alongside the main control GUI.

Features:
  - Real-time deck layout visualization
  - Hover over reagents to see volume distributions
  - Hover over labware to see detailed info
  - Live animation of protocol steps as they execute

Usage:
  Standalone: python deck_visualizer.py opentrons_spheroid_media_change.py
  Integrated: Import and use DeckVisualizer class
"""

import re
import cv2
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LabwareOffset:
    """Offset configuration for labware starting positions."""
    columns: int = 0  # Columns to skip
    rows: int = 0     # Rows to skip
    well_index: int = 0  # Starting well index (for reservoirs)


@dataclass
class LabwareInfo:
    """Information about a piece of labware on the deck."""
    id: str
    load_name: str
    slot: str
    display_name: str = ""
    labware_type: str = ""  # 'tiprack', 'plate', 'reservoir', 'tuberack', 'trash'
    well_count: int = 0  # Number of wells/tubes
    definition: Dict = field(default_factory=dict)  # Full labware definition
    offset: Optional[LabwareOffset] = None  # Starting position offset


@dataclass
class ReagentInfo:
    """Information about a reagent and where it's used."""
    name: str
    source_slot: str
    source_well: str
    destinations: Dict[str, float]  # well -> volume


@dataclass
class AnimationState:
    """Current state of protocol animation."""
    current_command_index: int = 0
    total_commands: int = 0
    current_command_type: str = ""
    current_command_desc: str = ""
    source_slot: Optional[str] = None
    source_well: Optional[str] = None
    dest_slot: Optional[str] = None
    dest_well: Optional[str] = None
    pipette_position: Optional[Tuple[float, float]] = None  # Screen coords
    is_aspirating: bool = False
    is_dispensing: bool = False
    has_tip: bool = False
    volume: float = 0.0


class DeckVisualizer:
    """
    Visualizes the Opentrons Flex deck layout with labware and reagent info.
    """

    # Deck slot layout for Flex (3x4 grid, A1 is top-left)
    # Columns: 1, 2, 3, 4 (left to right)
    # Rows: A, B, C, D (top to bottom)
    SLOTS = [
        ['A1', 'A2', 'A3', 'A4'],
        ['B1', 'B2', 'B3', 'B4'],
        ['C1', 'C2', 'C3', 'C4'],
        ['D1', 'D2', 'D3', 'D4'],
    ]

    # Colors (BGR format for OpenCV)
    COLORS = {
        'background': (40, 40, 40),
        'slot_empty': (60, 60, 60),
        'slot_border': (100, 100, 100),
        'slot_highlight': (0, 200, 200),  # Yellow border for hovered slot
        'tiprack': (180, 180, 80),      # Cyan-ish
        'plate': (80, 180, 80),          # Green
        'reservoir': (180, 80, 80),      # Blue
        'tuberack': (80, 80, 180),       # Red-ish
        'trash': (60, 60, 60),           # Dark gray
        'text': (255, 255, 255),         # White
        'text_dim': (150, 150, 150),     # Gray
        'highlight': (0, 255, 255),      # Yellow
        'reagent_low': (100, 200, 100),  # Light green
        'reagent_high': (100, 100, 255), # Light red
        'pipette': (255, 200, 0),        # Bright cyan for pipette
        'aspirate': (255, 100, 100),     # Blue-ish for aspirate
        'dispense': (100, 255, 100),     # Green for dispense
        'active_well': (0, 255, 255),    # Yellow for active well
        'command_bg': (30, 30, 30),      # Dark background for command display
    }

    def __init__(self, width: int = 800, height: int = 700):
        """Initialize the visualizer with canvas dimensions."""
        self.width = width
        self.height = height
        self.labware: Dict[str, LabwareInfo] = {}
        self.reagents: Dict[str, ReagentInfo] = {}
        self.plate_layout: Dict[str, List[Tuple[str, float]]] = {}
        self.reagent_locations: Dict[str, str] = {}
        self.base_media_volume = 150
        self.hovered_reagent: Optional[str] = None
        self.hovered_slot: Optional[str] = None
        self.mouse_pos = (0, 0)

        # Tiprack click state - for interactive offset setting
        self.tiprack_click_enabled = True  # Enable click-to-set tip offset
        self.pending_offset_change: Optional[Dict] = None  # {slot, columns, rows} when user clicks

        # Labware drag state - for repositioning labware on deck
        self.dragging_labware: Optional[str] = None  # Slot being dragged
        self.drag_start_pos: Optional[Tuple[int, int]] = None  # Mouse position when drag started
        self.pending_labware_move: Optional[Dict] = None  # {from_slot, to_slot} when user drops

        # Animation state
        self.animation = AnimationState()
        self.protocol_commands: List[Dict] = []
        self.labware_id_to_slot: Dict[str, str] = {}  # Maps labware IDs to slots
        self.protocol_accessed_slots: set = set()  # Slots accessed by the protocol (for showing empty destinations)

        # Command display area height
        self.command_area_height = 80

        # Protocol name for display
        self.protocol_name: str = ""

        # Calculate slot dimensions
        self.margin = 40
        self.slot_gap = 10
        self.deck_width = width - 2 * self.margin
        self.deck_height = height - 2 * self.margin - 60 - self.command_area_height  # Leave room for legend and commands
        self.slot_width = (self.deck_width - 3 * self.slot_gap) // 4
        self.slot_height = (self.deck_height - 3 * self.slot_gap) // 4

    def load_from_protocol_data(self,
                                 labware_list: List[Dict],
                                 plate_layout: Dict[str, List[Tuple[str, float]]],
                                 reagent_locations: Dict[str, str],
                                 base_media_volume: float = 150,
                                 commands: Optional[List[Dict]] = None,
                                 labware_offsets: Optional[Dict[str, Dict[str, int]]] = None,
                                 protocol_name: str = ""):
        """
        Load visualization data from protocol analysis results.

        Args:
            labware_list: List of labware dicts from analyzer
            plate_layout: Well -> [(reagent, volume), ...] mapping
            reagent_locations: Reagent name -> tube well mapping
            base_media_volume: Volume of base media per well
            commands: List of protocol commands for animation
            labware_offsets: Dict mapping slot -> {'columns': n, 'rows': n, 'well_index': n}
                            For tipracks: columns and rows to skip
                            For reservoirs: well_index (0-11) to start from
            protocol_name: Name of the protocol to display
        """
        self.protocol_name = protocol_name
        self.plate_layout = plate_layout
        self.reagent_locations = reagent_locations
        self.base_media_volume = base_media_volume
        self.labware.clear()
        self.reagents.clear()
        self.labware_id_to_slot.clear()

        # Store offsets for later use
        self.labware_offsets = labware_offsets or {}

        # Store commands for animation and extract accessed slots
        self.protocol_accessed_slots.clear()
        if commands:
            self.protocol_commands = commands
            self.animation.total_commands = len(commands)
            # Extract slots accessed by the protocol from commands
            self._extract_accessed_slots(commands)

        # Parse labware
        for lw in labware_list:
            # Handle various location formats
            location = lw.get('location', {})
            slot = ''

            if isinstance(location, dict):
                slot = location.get('slotName', '')
                # If labware is on another labware (like a lid on a plate), skip it for now
                if not slot and 'labwareId' in location:
                    continue
            elif isinstance(location, str):
                # System locations like 'systemLocation' - skip these
                if location in ('systemLocation', 'offDeck'):
                    continue
                slot = location

            if not slot:
                continue

            load_name = lw.get('loadName', '')
            display_name = lw.get('displayName', load_name)
            labware_id = lw.get('id', '')

            # Determine labware type and well count
            # Check displayCategory from metadata first (most reliable for custom labware)
            display_category = lw.get('metadata', {}).get('displayCategory', '').lower()

            lw_type = 'unknown'
            well_count = 0

            # Use displayCategory if available
            if display_category == 'reservoir':
                lw_type = 'reservoir'
            elif display_category == 'wellPlate':
                lw_type = 'plate'
            elif display_category == 'tipRack':
                lw_type = 'tiprack'
            elif display_category == 'tubeRack':
                lw_type = 'tuberack'
            elif display_category == 'trash':
                lw_type = 'trash'

            # Fall back to load_name parsing if displayCategory not available
            if lw_type == 'unknown':
                if 'tiprack' in load_name.lower():
                    lw_type = 'tiprack'
                elif 'plate' in load_name.lower() or 'wellplate' in load_name.lower():
                    lw_type = 'plate'
                elif 'reservoir' in load_name.lower():
                    lw_type = 'reservoir'
                elif 'tuberack' in load_name.lower():
                    lw_type = 'tuberack'
                elif 'trash' in load_name.lower():
                    lw_type = 'trash'

            # Try to get well count from definition, fall back to parsing load_name
            definition = lw.get('definition', {})
            wells = definition.get('wells', {})
            if wells:
                well_count = len(wells)
            else:
                # Parse from load_name
                if lw_type == 'tiprack':
                    well_count = 96 if '96' in load_name else 24
                elif lw_type == 'plate':
                    well_count = 96 if '96' in load_name else (384 if '384' in load_name else 24)
                elif lw_type == 'reservoir':
                    # Try to extract number from name
                    match = re.search(r'(\d+)', load_name)
                    well_count = int(match.group(1)) if match else 12
                elif lw_type == 'tuberack':
                    well_count = 24 if '24' in load_name else 6

            # Get offset for this slot if configured
            slot_offset = None
            if slot in self.labware_offsets:
                offset_data = self.labware_offsets[slot]
                slot_offset = LabwareOffset(
                    columns=offset_data.get('columns', 0),
                    rows=offset_data.get('rows', 0),
                    well_index=offset_data.get('well_index', 0)
                )

            self.labware[slot] = LabwareInfo(
                id=labware_id,
                load_name=load_name,
                slot=slot,
                display_name=display_name,
                labware_type=lw_type,
                well_count=well_count,
                definition=lw,
                offset=slot_offset
            )

            # Build ID to slot mapping
            if labware_id:
                self.labware_id_to_slot[labware_id] = slot

        # Build reagent info
        # Base media (from reservoir)
        self.reagents['base_media'] = ReagentInfo(
            name='Base Media',
            source_slot='C1',  # Default reservoir slot
            source_well='A1',
            destinations={well: base_media_volume for well in plate_layout.keys()}
        )

        # Other reagents (from tube rack)
        for reagent_name, tube_well in reagent_locations.items():
            destinations = {}
            for well, reagents in plate_layout.items():
                for r_name, volume in reagents:
                    if r_name == reagent_name:
                        destinations[well] = volume

            self.reagents[reagent_name] = ReagentInfo(
                name=reagent_name.replace('_', ' ').title(),
                source_slot='B1',  # Default tube rack slot
                source_well=tube_well,
                destinations=destinations
            )

    def get_slot_rect(self, slot: str) -> Tuple[int, int, int, int]:
        """Get the rectangle (x, y, w, h) for a deck slot."""
        # Find slot position
        row_idx = -1
        col_idx = -1
        for r, row in enumerate(self.SLOTS):
            if slot in row:
                row_idx = r
                col_idx = row.index(slot)
                break

        if row_idx < 0:
            return (0, 0, 0, 0)

        x = self.margin + col_idx * (self.slot_width + self.slot_gap)
        y = self.margin + row_idx * (self.slot_height + self.slot_gap)

        return (x, y, self.slot_width, self.slot_height)

    def get_slot_at_pos(self, x: int, y: int) -> Optional[str]:
        """Get the slot name at a given position, or None if not over a slot."""
        for row in self.SLOTS:
            for slot in row:
                sx, sy, sw, sh = self.get_slot_rect(slot)
                if sx <= x <= sx + sw and sy <= y <= sy + sh:
                    return slot
        return None

    def _draw_dotted_rect(self, frame: np.ndarray, x: int, y: int, w: int, h: int,
                          color: tuple, thickness: int = 2, gap: int = 8):
        """Draw a dotted/dashed rectangle border."""
        # Top edge
        for i in range(x, x + w, gap * 2):
            cv2.line(frame, (i, y), (min(i + gap, x + w), y), color, thickness)
        # Bottom edge
        for i in range(x, x + w, gap * 2):
            cv2.line(frame, (i, y + h), (min(i + gap, x + w), y + h), color, thickness)
        # Left edge
        for i in range(y, y + h, gap * 2):
            cv2.line(frame, (x, i), (x, min(i + gap, y + h)), color, thickness)
        # Right edge
        for i in range(y, y + h, gap * 2):
            cv2.line(frame, (x + w, i), (x + w, min(i + gap, y + h)), color, thickness)

    def draw_slot(self, frame: np.ndarray, slot: str, labware: Optional[LabwareInfo] = None):
        """Draw a deck slot with optional labware."""
        x, y, w, h = self.get_slot_rect(slot)

        # Check if this slot is being dragged
        is_being_dragged = (slot == self.dragging_labware)
        is_drag_target = (self.dragging_labware and slot == self.hovered_slot and slot != self.dragging_labware)

        # Check if this empty slot is accessed by the protocol
        is_protocol_destination = (not labware and slot in self.protocol_accessed_slots)

        # Background color based on labware type
        if labware:
            color = self.COLORS.get(labware.labware_type, self.COLORS['slot_empty'])
            # Dim the color if being dragged
            if is_being_dragged:
                color = tuple(c // 2 for c in color)
        else:
            color = self.COLORS['slot_empty']

        # Check if this slot is active in animation
        is_active = (slot == self.animation.source_slot or slot == self.animation.dest_slot)

        # Draw slot rectangle
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, -1)

        # Highlight border based on state
        if is_being_dragged:
            # Dashed border effect for dragged item
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 165, 255), 3)  # Orange
        elif is_drag_target:
            # Bright green for valid drop target
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 4)
        elif slot == self.hovered_slot:
            cv2.rectangle(frame, (x, y), (x + w, y + h), self.COLORS['slot_highlight'], 3)
        elif is_active:
            cv2.rectangle(frame, (x, y), (x + w, y + h), self.COLORS['active_well'], 2)
        elif is_protocol_destination:
            # Draw dotted border for empty slots accessed by the protocol
            self._draw_dotted_rect(frame, x, y, w, h, self.COLORS['highlight'], thickness=2, gap=8)
        else:
            cv2.rectangle(frame, (x, y), (x + w, y + h), self.COLORS['slot_border'], 2)

        # Draw slot label
        cv2.putText(frame, slot, (x + 5, y + 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.COLORS['text_dim'], 1, cv2.LINE_AA)

        # Draw labware info
        if labware:
            # Shorten display name if needed
            display = labware.display_name[:15] if len(labware.display_name) > 15 else labware.display_name
            cv2.putText(frame, display, (x + 5, y + h - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, self.COLORS['text'], 1, cv2.LINE_AA)
        elif is_protocol_destination:
            # Label for protocol destination slots
            cv2.putText(frame, "(destination)", (x + 5, y + h - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.35, self.COLORS['text_dim'], 1, cv2.LINE_AA)

    def draw_plate_wells(self, frame: np.ndarray, slot: str,
                         highlight_reagent: Optional[str] = None):
        """Draw wells for a plate, optionally highlighting reagent volumes and starting position."""
        x, y, w, h = self.get_slot_rect(slot)
        labware = self.labware.get(slot)

        # 96-well plate layout: 8 rows x 12 cols
        well_margin = 8
        well_area_w = w - 2 * well_margin
        well_area_h = h - 30  # Leave room for label
        well_w = well_area_w // 12
        well_h = well_area_h // 8
        well_r = min(well_w, well_h) // 2 - 2

        # Get offset configuration
        offset = labware.offset if labware and labware.offset else LabwareOffset()
        start_col = offset.columns
        start_row = offset.rows

        # Find first well with content to highlight
        first_content_well = None
        if self.plate_layout:
            content_wells = list(self.plate_layout.keys())
            if content_wells:
                def well_sort_key(w):
                    row = ord(w[0]) - ord('A')
                    col = int(w[1:]) - 1
                    return (col, row)
                content_wells.sort(key=well_sort_key)
                first_content_well = content_wells[0]

        for row_idx, row in enumerate('ABCDEFGH'):
            for col in range(12):
                well = f'{row}{col + 1}'
                wx = x + well_margin + col * well_w + well_w // 2
                wy = y + 25 + row_idx * well_h + well_h // 2

                # Check if this is before the starting position
                is_before_start = (col < start_col) or (col == start_col and row_idx < start_row)
                is_start_position = (col == start_col and row_idx == start_row)
                is_first_content = (well == first_content_well)

                # Check if this well has reagents
                if well in self.plate_layout:
                    # Default: light fill
                    fill_color = (80, 80, 80)

                    # If highlighting a reagent, color by volume
                    if highlight_reagent and highlight_reagent in self.reagents:
                        reagent = self.reagents[highlight_reagent]
                        if well in reagent.destinations:
                            vol = reagent.destinations[well]
                            # Color intensity based on volume (1-10 uL range typical)
                            max_vol = max(reagent.destinations.values()) if reagent.destinations else 1
                            intensity = min(1.0, vol / max(max_vol, 1))
                            # Interpolate between low and high colors
                            low = np.array(self.COLORS['reagent_low'])
                            high = np.array(self.COLORS['reagent_high'])
                            fill_color = tuple(map(int, low + intensity * (high - low)))

                    cv2.circle(frame, (wx, wy), well_r, fill_color, -1)

                    # Highlight starting position with yellow border
                    if is_start_position:
                        cv2.circle(frame, (wx, wy), well_r + 2, self.COLORS['highlight'], 2)
                        cv2.circle(frame, (wx, wy), well_r, self.COLORS['text'], 1)
                        cv2.circle(frame, (wx, wy), 3, self.COLORS['text'], -1)
                    elif is_first_content:
                        cv2.circle(frame, (wx, wy), well_r + 2, self.COLORS['highlight'], 2)
                        cv2.circle(frame, (wx, wy), well_r, self.COLORS['text'], 1)
                    else:
                        cv2.circle(frame, (wx, wy), well_r, self.COLORS['slot_border'], 1)
                elif is_before_start:
                    # Used/unavailable well (before offset)
                    cv2.circle(frame, (wx, wy), well_r, self.COLORS['slot_empty'], -1)
                    cv2.circle(frame, (wx, wy), well_r, self.COLORS['slot_border'], 1)
                elif is_start_position:
                    # Starting position marker (always show, even for A1)
                    cv2.circle(frame, (wx, wy), well_r + 2, self.COLORS['highlight'], 2)
                    cv2.circle(frame, (wx, wy), well_r, self.COLORS['slot_empty'], -1)
                    cv2.circle(frame, (wx, wy), well_r, self.COLORS['text'], 1)
                    # Draw small dot indicator (same as tiprack)
                    cv2.circle(frame, (wx, wy), 3, self.COLORS['text'], -1)
                else:
                    # Empty well
                    cv2.circle(frame, (wx, wy), well_r, self.COLORS['slot_empty'], -1)
                    cv2.circle(frame, (wx, wy), well_r, self.COLORS['slot_border'], 1)

        # Always show starting position label
        start_well = f"{chr(ord('A') + start_row)}{start_col + 1}"
        label = f"Start: {start_well}"
        cv2.putText(frame, label, (x + 5, y + h - 3),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.35, self.COLORS['highlight'], 1, cv2.LINE_AA)

        # Draw "click to set" hint if hovering over this plate
        if self.hovered_slot == slot:
            cv2.putText(frame, "Click well to set start", (x + 5, y + 15),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.3, self.COLORS['text'], 1, cv2.LINE_AA)

    def draw_tube_rack(self, frame: np.ndarray, slot: str,
                       highlight_reagent: Optional[str] = None):
        """Draw tubes in a tube rack, highlighting the source of a reagent and starting position."""
        x, y, w, h = self.get_slot_rect(slot)
        labware = self.labware.get(slot)

        # 24-tube rack: 4 rows x 6 cols
        tube_margin = 8
        tube_area_w = w - 2 * tube_margin
        tube_area_h = h - 30
        tube_w = tube_area_w // 6
        tube_h = tube_area_h // 4
        tube_r = min(tube_w, tube_h) // 2 - 2

        # Get offset configuration for starting position
        offset = labware.offset if labware and labware.offset else LabwareOffset()
        start_col = offset.columns
        start_row = offset.rows

        # Find the first tube with reagent to highlight as "first used"
        first_reagent_well = None
        if self.reagent_locations:
            # Sort reagent wells to find the first one
            reagent_wells = list(self.reagent_locations.values())
            if reagent_wells:
                def well_sort_key(w):
                    row = ord(w[0]) - ord('A')
                    col = int(w[1:]) - 1
                    return (col, row)  # Column-major order
                reagent_wells.sort(key=well_sort_key)
                first_reagent_well = reagent_wells[0]

        for row_idx, row in enumerate('ABCD'):
            for col in range(6):
                well = f'{row}{col + 1}'
                tx = x + tube_margin + col * tube_w + tube_w // 2
                ty = y + 25 + row_idx * tube_h + tube_h // 2

                # Check if this tube has a reagent
                reagent_name = None
                for rname, rwell in self.reagent_locations.items():
                    if rwell == well:
                        reagent_name = rname
                        break

                # Check if this is before the starting position (if offset configured)
                is_before_start = (col < start_col) or (col == start_col and row_idx < start_row)
                is_first_reagent = (well == first_reagent_well)

                if reagent_name:
                    # Filled tube
                    if highlight_reagent == reagent_name:
                        fill_color = self.COLORS['highlight']
                    else:
                        fill_color = self.COLORS['tuberack']
                    cv2.circle(frame, (tx, ty), tube_r, fill_color, -1)

                    # Highlight first reagent tube with yellow border
                    if is_first_reagent:
                        cv2.circle(frame, (tx, ty), tube_r + 2, self.COLORS['highlight'], 2)
                        cv2.circle(frame, (tx, ty), tube_r, self.COLORS['text'], 2)
                    else:
                        cv2.circle(frame, (tx, ty), tube_r, self.COLORS['text'], 2)

                    # Draw reagent initial
                    initial = reagent_name[0].upper()
                    cv2.putText(frame, initial, (tx - 4, ty + 4),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.3, self.COLORS['text'], 1, cv2.LINE_AA)
                elif is_before_start:
                    # Used/unavailable tube slot (before offset)
                    cv2.circle(frame, (tx, ty), tube_r, self.COLORS['slot_empty'], -1)
                    cv2.circle(frame, (tx, ty), tube_r, self.COLORS['slot_border'], 1)
                else:
                    # Empty tube slot (available)
                    cv2.circle(frame, (tx, ty), tube_r, self.COLORS['slot_empty'], -1)
                    cv2.circle(frame, (tx, ty), tube_r, self.COLORS['slot_border'], 1)

        # Show first reagent location label
        if first_reagent_well:
            label = f"First: {first_reagent_well}"
            cv2.putText(frame, label, (x + 5, y + h - 3),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.35, self.COLORS['highlight'], 1, cv2.LINE_AA)

    def draw_tiprack(self, frame: np.ndarray, slot: str):
        """Draw tips in a tiprack, showing starting position marker."""
        x, y, w, h = self.get_slot_rect(slot)
        labware = self.labware.get(slot)

        # 96-tip rack: 8 rows x 12 cols
        tip_margin = 8
        tip_area_w = w - 2 * tip_margin
        tip_area_h = h - 30
        tip_w = tip_area_w // 12
        tip_h = tip_area_h // 8
        tip_r = min(tip_w, tip_h) // 2 - 2

        # Get offset configuration
        offset = labware.offset if labware and labware.offset else LabwareOffset()
        start_col = offset.columns
        start_row = offset.rows

        for row_idx in range(8):
            for col in range(12):
                tx = x + tip_margin + col * tip_w + tip_w // 2
                ty = y + 25 + row_idx * tip_h + tip_h // 2

                # Check if this is the starting position
                is_start_position = (col == start_col and row_idx == start_row)

                if is_start_position:
                    # Starting position - bright highlight with marker
                    cv2.circle(frame, (tx, ty), tip_r + 2, self.COLORS['highlight'], 2)
                    cv2.circle(frame, (tx, ty), tip_r, self.COLORS['tiprack'], -1)
                    cv2.circle(frame, (tx, ty), tip_r, self.COLORS['text'], 1)
                    # Draw small dot indicator
                    cv2.circle(frame, (tx, ty), 3, self.COLORS['text'], -1)
                else:
                    # All other tips - normal appearance
                    cv2.circle(frame, (tx, ty), tip_r, self.COLORS['tiprack'], -1)
                    cv2.circle(frame, (tx, ty), tip_r, self.COLORS['slot_border'], 1)

        # Draw start position label
        if start_col > 0 or start_row > 0:
            start_well = f"{chr(ord('A') + start_row)}{start_col + 1}"
            label = f"Start: {start_well}"
            cv2.putText(frame, label, (x + 5, y + h - 3),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.35, self.COLORS['highlight'], 1, cv2.LINE_AA)

        # Draw "click to set" hint if hovering over this tiprack
        if self.tiprack_click_enabled and self.hovered_slot == slot:
            cv2.putText(frame, "Click tip to set start", (x + 5, y + 15),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.3, self.COLORS['text'], 1, cv2.LINE_AA)

    def get_tiprack_tip_at_pos(self, slot: str, mx: int, my: int) -> Optional[Tuple[int, int]]:
        """
        Get the (column, row) of a tip at mouse position, or None if not over a tip.
        Returns 0-indexed (col, row).
        """
        x, y, w, h = self.get_slot_rect(slot)

        # Same geometry as draw_tiprack
        tip_margin = 8
        tip_area_w = w - 2 * tip_margin
        tip_area_h = h - 30
        tip_w = tip_area_w // 12
        tip_h = tip_area_h // 8
        tip_r = min(tip_w, tip_h) // 2 - 2

        # Check if mouse is within tip area
        tip_start_x = x + tip_margin
        tip_start_y = y + 25

        if mx < tip_start_x or mx > tip_start_x + tip_area_w:
            return None
        if my < tip_start_y or my > tip_start_y + tip_area_h:
            return None

        # Calculate which tip
        col = (mx - tip_start_x) // tip_w
        row = (my - tip_start_y) // tip_h

        if 0 <= col < 12 and 0 <= row < 8:
            # Verify click is actually on the tip circle
            tx = tip_start_x + col * tip_w + tip_w // 2
            ty = tip_start_y + row * tip_h + tip_h // 2
            dist = ((mx - tx) ** 2 + (my - ty) ** 2) ** 0.5
            if dist <= tip_r + 3:  # Small tolerance
                return (col, row)

        return None

    def get_plate_well_at_pos(self, slot: str, mx: int, my: int) -> Optional[Tuple[int, int]]:
        """
        Get the (column, row) of a well at mouse position, or None if not over a well.
        Returns 0-indexed (col, row).
        """
        x, y, w, h = self.get_slot_rect(slot)

        # Same geometry as draw_plate_wells (96-well plate: 8 rows x 12 cols)
        well_margin = 8
        well_area_w = w - 2 * well_margin
        well_area_h = h - 30
        well_w = well_area_w // 12
        well_h = well_area_h // 8
        well_r = min(well_w, well_h) // 2 - 2

        # Check if mouse is within well area
        well_start_x = x + well_margin
        well_start_y = y + 25

        if mx < well_start_x or mx > well_start_x + well_area_w:
            return None
        if my < well_start_y or my > well_start_y + well_area_h:
            return None

        # Calculate which well
        col = (mx - well_start_x) // well_w
        row = (my - well_start_y) // well_h

        if 0 <= col < 12 and 0 <= row < 8:
            # Verify click is actually on the well circle
            wx = well_start_x + col * well_w + well_w // 2
            wy = well_start_y + row * well_h + well_h // 2
            dist = ((mx - wx) ** 2 + (my - wy) ** 2) ** 0.5
            if dist <= well_r + 3:  # Small tolerance
                return (col, row)

        return None

    def draw_reservoir(self, frame: np.ndarray, slot: str,
                       highlight_reagent: Optional[str] = None):
        """Draw a reservoir with variable well count, showing starting well marker."""
        x, y, w, h = self.get_slot_rect(slot)
        labware = self.labware.get(slot)

        # Determine number of wells from labware info
        num_wells = labware.well_count if labware and labware.well_count > 0 else 12

        well_margin = 8
        well_area_w = w - 2 * well_margin
        well_w = well_area_w // max(num_wells, 1)
        well_h = h - 40

        # Get starting well from offset
        offset = labware.offset if labware and labware.offset else LabwareOffset()
        start_well_idx = offset.well_index

        for col in range(num_wells):
            wx = x + well_margin + col * well_w
            wy = y + 25

            is_before_start = col < start_well_idx
            is_start_position = col == start_well_idx

            if is_before_start:
                # Used/empty well - darker
                fill_color = self.COLORS['slot_empty']
            elif highlight_reagent == 'base_media':
                fill_color = self.COLORS['highlight']
            else:
                fill_color = self.COLORS['reservoir']

            cv2.rectangle(frame, (wx + 2, wy), (wx + well_w - 2, wy + well_h),
                         fill_color, -1)

            # Highlight the starting/first well with bright border
            if is_start_position:
                cv2.rectangle(frame, (wx + 1, wy - 1), (wx + well_w - 1, wy + well_h + 1),
                             self.COLORS['highlight'], 2)
            else:
                cv2.rectangle(frame, (wx + 2, wy), (wx + well_w - 2, wy + well_h),
                             self.COLORS['slot_border'], 1)

            # Draw well label for small reservoirs
            if num_wells <= 4:
                well_label = f"A{col + 1}"
                cv2.putText(frame, well_label, (wx + 5, wy + 15),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.3, self.COLORS['text'], 1, cv2.LINE_AA)

        # Draw start/first position label
        label = f"First: A{start_well_idx + 1}"
        cv2.putText(frame, label, (x + 5, y + h - 3),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.35, self.COLORS['highlight'], 1, cv2.LINE_AA)

    def draw_legend(self, frame: np.ndarray):
        """Draw a legend showing reagent names and colors (if any reagents defined)."""
        legend_y = self.height - 50
        legend_x = self.margin

        self.reagent_buttons = {}

        # Only show reagent legend if there are reagents defined
        if not self.reagent_locations and not self.plate_layout:
            # Show simple labware type legend instead
            cv2.putText(frame, "Labware types:", (legend_x, legend_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.COLORS['text'], 1, cv2.LINE_AA)

            btn_x = legend_x
            btn_y = legend_y + 10
            btn_h = 20

            labware_types = [
                ('Tiprack', self.COLORS['tiprack']),
                ('Plate', self.COLORS['plate']),
                ('Reservoir', self.COLORS['reservoir']),
                ('Tube Rack', self.COLORS['tuberack']),
            ]

            for name, color in labware_types:
                btn_w = len(name) * 8 + 15
                cv2.rectangle(frame, (btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h), color, -1)
                cv2.putText(frame, name, (btn_x + 5, btn_y + 14),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.35, self.COLORS['text'], 1, cv2.LINE_AA)
                btn_x += btn_w + 5
            return

        cv2.putText(frame, "Reagents (hover to highlight):", (legend_x, legend_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.COLORS['text'], 1, cv2.LINE_AA)

        # Draw reagent buttons
        btn_x = legend_x
        btn_y = legend_y + 10
        btn_h = 25

        # Base media first (only if plate_layout exists)
        if self.plate_layout:
            btn_w = 80
            self.reagent_buttons['base_media'] = (btn_x, btn_y, btn_w, btn_h)
            color = self.COLORS['highlight'] if self.hovered_reagent == 'base_media' else self.COLORS['reservoir']
            cv2.rectangle(frame, (btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h), color, -1)
            cv2.putText(frame, "Base", (btn_x + 5, btn_y + 17),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, self.COLORS['text'], 1, cv2.LINE_AA)
            btn_x += btn_w + 5

        # Other reagents
        for reagent_name in sorted(self.reagent_locations.keys()):
            display = reagent_name.replace('_', ' ').title()[:8]
            btn_w = max(60, len(display) * 8 + 10)
            self.reagent_buttons[reagent_name] = (btn_x, btn_y, btn_w, btn_h)

            color = self.COLORS['highlight'] if self.hovered_reagent == reagent_name else self.COLORS['tuberack']
            cv2.rectangle(frame, (btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h), color, -1)
            cv2.putText(frame, display, (btn_x + 5, btn_y + 17),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.35, self.COLORS['text'], 1, cv2.LINE_AA)
            btn_x += btn_w + 5

    def draw_volume_tooltip(self, frame: np.ndarray):
        """Draw a tooltip showing volumes when hovering over a reagent."""
        if not self.hovered_reagent or self.hovered_reagent not in self.reagents:
            return

        reagent = self.reagents[self.hovered_reagent]

        # Find unique volumes and wells
        vol_to_wells: Dict[float, List[str]] = {}
        for well, vol in reagent.destinations.items():
            if vol not in vol_to_wells:
                vol_to_wells[vol] = []
            vol_to_wells[vol].append(well)

        # Build tooltip text
        lines = [f"{reagent.name} from {reagent.source_slot}:{reagent.source_well}"]
        for vol in sorted(vol_to_wells.keys()):
            wells = vol_to_wells[vol]
            if len(wells) <= 4:
                wells_str = ', '.join(wells)
            else:
                wells_str = f"{wells[0]}-{wells[-1]} ({len(wells)} wells)"
            lines.append(f"  {vol:.1f}uL -> {wells_str}")

        # Draw tooltip box
        tooltip_x = self.mouse_pos[0] + 15
        tooltip_y = self.mouse_pos[1]
        line_height = 18
        max_width = max(len(line) for line in lines) * 8 + 20
        box_height = len(lines) * line_height + 10

        # Keep tooltip on screen
        if tooltip_x + max_width > self.width:
            tooltip_x = self.width - max_width - 10
        if tooltip_y + box_height > self.height:
            tooltip_y = self.height - box_height - 10

        # Draw background
        cv2.rectangle(frame, (tooltip_x, tooltip_y),
                     (tooltip_x + max_width, tooltip_y + box_height),
                     (20, 20, 20), -1)
        cv2.rectangle(frame, (tooltip_x, tooltip_y),
                     (tooltip_x + max_width, tooltip_y + box_height),
                     self.COLORS['highlight'], 1)

        # Draw text
        for i, line in enumerate(lines):
            cv2.putText(frame, line, (tooltip_x + 5, tooltip_y + 15 + i * line_height),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, self.COLORS['text'], 1, cv2.LINE_AA)

    def draw_labware_tooltip(self, frame: np.ndarray):
        """Draw a tooltip showing labware info when hovering over a slot."""
        if not self.hovered_slot or self.hovered_slot not in self.labware:
            return

        labware = self.labware[self.hovered_slot]

        # Build tooltip text
        lines = [
            f"Slot {self.hovered_slot}: {labware.display_name}",
            f"Type: {labware.labware_type.title()}",
            f"Load name: {labware.load_name[:40]}",
        ]
        if labware.well_count > 0:
            lines.append(f"Wells: {labware.well_count}")

        # Show reagent info for tube racks
        if labware.labware_type == 'tuberack':
            reagents_in_rack = []
            for name, well in self.reagent_locations.items():
                reagents_in_rack.append(f"  {well}: {name}")
            if reagents_in_rack:
                lines.append("Reagents:")
                lines.extend(reagents_in_rack[:5])  # Limit to 5

        # Draw tooltip box
        tooltip_x = self.mouse_pos[0] + 15
        tooltip_y = self.mouse_pos[1]
        line_height = 18
        max_width = max(len(line) for line in lines) * 7 + 20
        box_height = len(lines) * line_height + 10

        # Keep tooltip on screen
        if tooltip_x + max_width > self.width:
            tooltip_x = self.width - max_width - 10
        if tooltip_y + box_height > self.height:
            tooltip_y = self.height - box_height - 10

        # Draw background
        cv2.rectangle(frame, (tooltip_x, tooltip_y),
                     (tooltip_x + max_width, tooltip_y + box_height),
                     (20, 20, 20), -1)
        cv2.rectangle(frame, (tooltip_x, tooltip_y),
                     (tooltip_x + max_width, tooltip_y + box_height),
                     self.COLORS['slot_highlight'], 1)

        # Draw text
        for i, line in enumerate(lines):
            cv2.putText(frame, line, (tooltip_x + 5, tooltip_y + 15 + i * line_height),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, self.COLORS['text'], 1, cv2.LINE_AA)

    def draw_command_display(self, frame: np.ndarray):
        """Draw the current command and progress at the bottom of the screen."""
        # Command display area
        cmd_y = self.height - self.command_area_height
        cmd_x = self.margin
        cmd_w = self.width - 2 * self.margin
        cmd_h = self.command_area_height - 10

        # Draw background
        cv2.rectangle(frame, (cmd_x, cmd_y), (cmd_x + cmd_w, cmd_y + cmd_h),
                     self.COLORS['command_bg'], -1)
        cv2.rectangle(frame, (cmd_x, cmd_y), (cmd_x + cmd_w, cmd_y + cmd_h),
                     self.COLORS['slot_border'], 1)

        # Draw progress bar
        if self.animation.total_commands > 0:
            progress = self.animation.current_command_index / self.animation.total_commands
            bar_width = int((cmd_w - 20) * progress)
            cv2.rectangle(frame, (cmd_x + 10, cmd_y + 5),
                         (cmd_x + 10 + bar_width, cmd_y + 15),
                         self.COLORS['plate'], -1)
            cv2.rectangle(frame, (cmd_x + 10, cmd_y + 5),
                         (cmd_x + cmd_w - 10, cmd_y + 15),
                         self.COLORS['slot_border'], 1)

            # Progress text
            progress_text = f"Step {self.animation.current_command_index}/{self.animation.total_commands}"
            cv2.putText(frame, progress_text, (cmd_x + cmd_w - 120, cmd_y + 14),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, self.COLORS['text'], 1, cv2.LINE_AA)

        # Draw current command type
        if self.animation.current_command_type:
            cmd_type_color = self.COLORS['text']
            if self.animation.is_aspirating:
                cmd_type_color = self.COLORS['aspirate']
            elif self.animation.is_dispensing:
                cmd_type_color = self.COLORS['dispense']

            cv2.putText(frame, self.animation.current_command_type.upper(),
                       (cmd_x + 10, cmd_y + 35),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, cmd_type_color, 2, cv2.LINE_AA)

        # Draw command description
        if self.animation.current_command_desc:
            desc = self.animation.current_command_desc[:80]  # Truncate if too long
            cv2.putText(frame, desc, (cmd_x + 10, cmd_y + 55),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, self.COLORS['text_dim'], 1, cv2.LINE_AA)

        # Draw volume if relevant
        if self.animation.volume > 0:
            vol_text = f"{self.animation.volume:.1f} uL"
            cv2.putText(frame, vol_text, (cmd_x + cmd_w - 80, cmd_y + 35),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.COLORS['highlight'], 1, cv2.LINE_AA)

    def draw_pipette_indicator(self, frame: np.ndarray):
        """Draw pipette position indicator on the active well."""
        if not self.animation.dest_slot and not self.animation.source_slot:
            return

        # Determine which slot and well to highlight
        active_slot = self.animation.dest_slot or self.animation.source_slot
        active_well = self.animation.dest_well or self.animation.source_well

        if not active_slot or not active_well:
            return

        # Get slot rectangle
        x, y, w, h = self.get_slot_rect(active_slot)

        # Calculate well position (simplified - works for 96-well plates)
        well_margin = 8
        well_area_w = w - 2 * well_margin
        well_area_h = h - 30

        # Parse well (e.g., "A1" -> row=0, col=0)
        if len(active_well) >= 2:
            row_char = active_well[0].upper()
            try:
                col = int(active_well[1:]) - 1
                row = ord(row_char) - ord('A')

                # Get labware to determine grid size
                labware = self.labware.get(active_slot)
                if labware:
                    if labware.labware_type == 'plate':
                        well_w = well_area_w // 12
                        well_h = well_area_h // 8
                    elif labware.labware_type == 'tiprack':
                        # Tiprack: 8 rows x 12 cols, same as 96-well plate
                        well_w = well_area_w // 12
                        well_h = well_area_h // 8
                    elif labware.labware_type == 'tuberack':
                        well_w = well_area_w // 6
                        well_h = well_area_h // 4
                    elif labware.labware_type == 'reservoir':
                        well_w = well_area_w // 12
                        well_h = h - 40
                        row = 0  # Reservoir only has one row
                    else:
                        return

                    wx = x + well_margin + col * well_w + well_w // 2
                    wy = y + 25 + row * well_h + well_h // 2

                    # Draw pipette indicator (crosshair)
                    color = self.COLORS['aspirate'] if self.animation.is_aspirating else self.COLORS['dispense']
                    cv2.circle(frame, (wx, wy), 8, color, 2)
                    cv2.line(frame, (wx - 12, wy), (wx + 12, wy), color, 2)
                    cv2.line(frame, (wx, wy - 12), (wx, wy + 12), color, 2)

            except (ValueError, IndexError):
                pass

    def update_animation(self, command_index: int, command: Optional[Dict] = None):
        """Update animation state based on current protocol command."""
        self.animation.current_command_index = command_index

        if command is None:
            # Clear animation state
            self.animation.current_command_type = ""
            self.animation.current_command_desc = ""
            self.animation.source_slot = None
            self.animation.source_well = None
            self.animation.dest_slot = None
            self.animation.dest_well = None
            self.animation.is_aspirating = False
            self.animation.is_dispensing = False
            self.animation.volume = 0.0
            return

        cmd_type = command.get('commandType', '')
        params = command.get('params', {})

        self.animation.current_command_type = cmd_type

        # Reset state
        self.animation.is_aspirating = False
        self.animation.is_dispensing = False
        self.animation.source_slot = None
        self.animation.source_well = None
        self.animation.dest_slot = None
        self.animation.dest_well = None
        self.animation.volume = 0.0

        # Parse command
        if cmd_type == 'aspirate':
            self.animation.is_aspirating = True
            self.animation.volume = params.get('volume', 0)
            labware_id = params.get('labwareId', '')
            well = params.get('wellName', '')
            slot = self.labware_id_to_slot.get(labware_id, '')
            self.animation.source_slot = slot
            self.animation.source_well = well
            self.animation.current_command_desc = f"Aspirating {self.animation.volume}uL from {slot}:{well}"

        elif cmd_type == 'dispense':
            self.animation.is_dispensing = True
            self.animation.volume = params.get('volume', 0)
            labware_id = params.get('labwareId', '')
            well = params.get('wellName', '')
            slot = self.labware_id_to_slot.get(labware_id, '')
            self.animation.dest_slot = slot
            self.animation.dest_well = well
            self.animation.current_command_desc = f"Dispensing {self.animation.volume}uL to {slot}:{well}"

        elif cmd_type == 'pickUpTip':
            self.animation.has_tip = True
            labware_id = params.get('labwareId', '')
            well = params.get('wellName', '')
            slot = self.labware_id_to_slot.get(labware_id, '')
            self.animation.source_slot = slot
            self.animation.source_well = well
            self.animation.current_command_desc = f"Picking up tip from {slot}:{well}"

        elif cmd_type == 'dropTip':
            self.animation.has_tip = False
            labware_id = params.get('labwareId', '')
            well = params.get('wellName', '')
            slot = self.labware_id_to_slot.get(labware_id, '')
            self.animation.dest_slot = slot
            self.animation.dest_well = well
            self.animation.current_command_desc = f"Dropping tip at {slot}:{well}"

        elif cmd_type == 'moveToWell':
            labware_id = params.get('labwareId', '')
            well = params.get('wellName', '')
            slot = self.labware_id_to_slot.get(labware_id, '')
            self.animation.dest_slot = slot
            self.animation.dest_well = well
            self.animation.current_command_desc = f"Moving to {slot}:{well}"

        elif cmd_type == 'blowout':
            labware_id = params.get('labwareId', '')
            well = params.get('wellName', '')
            slot = self.labware_id_to_slot.get(labware_id, '')
            self.animation.dest_slot = slot
            self.animation.dest_well = well
            self.animation.current_command_desc = f"Blowout at {slot}:{well}"

        elif cmd_type == 'comment':
            message = params.get('message', '')
            self.animation.current_command_desc = f"Comment: {message[:60]}"

        elif cmd_type == 'waitForDuration':
            seconds = params.get('seconds', 0)
            self.animation.current_command_desc = f"Waiting {seconds}s"

        elif cmd_type in ('loadLabware', 'loadPipette', 'loadTrashBin'):
            self.animation.current_command_desc = f"Loading {cmd_type.replace('load', '')}"

        else:
            self.animation.current_command_desc = cmd_type

    def render(self) -> np.ndarray:
        """Render the full deck visualization."""
        frame = np.full((self.height, self.width, 3), self.COLORS['background'], dtype=np.uint8)

        # Draw protocol name prominently at the top
        if self.protocol_name:
            # Draw protocol name with highlight background
            name_text = self.protocol_name
            # Truncate if too long
            if len(name_text) > 50:
                name_text = name_text[:47] + "..."

            # Calculate text size for background
            (text_width, text_height), baseline = cv2.getTextSize(
                name_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)

            # Draw background bar
            cv2.rectangle(frame, (0, 0), (self.width, 32), (50, 50, 50), -1)

            # Draw protocol name centered
            text_x = (self.width - text_width) // 2
            cv2.putText(frame, name_text, (text_x, 22),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, self.COLORS['highlight'], 2, cv2.LINE_AA)
        else:
            # Fallback title
            cv2.putText(frame, "Deck Layout Preview", (self.margin, 25),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, self.COLORS['text'], 2, cv2.LINE_AA)

        # Draw all slots
        for row in self.SLOTS:
            for slot in row:
                labware = self.labware.get(slot)
                self.draw_slot(frame, slot, labware)

                # Draw details based on labware type
                if labware:
                    if labware.labware_type == 'plate':
                        self.draw_plate_wells(frame, slot, self.hovered_reagent)
                    elif labware.labware_type == 'tuberack':
                        self.draw_tube_rack(frame, slot, self.hovered_reagent)
                    elif labware.labware_type == 'reservoir':
                        self.draw_reservoir(frame, slot, self.hovered_reagent)
                    elif labware.labware_type == 'tiprack':
                        self.draw_tiprack(frame, slot)

        # Draw pipette indicator for animation
        self.draw_pipette_indicator(frame)

        # Draw legend
        self.draw_legend(frame)

        # Draw command display at bottom
        self.draw_command_display(frame)

        # Draw tooltips (on top of everything)
        if self.hovered_reagent:
            self.draw_volume_tooltip(frame)
        elif self.hovered_slot and not self.dragging_labware:
            self.draw_labware_tooltip(frame)

        # Draw drag indicator if dragging labware
        if self.dragging_labware:
            self._draw_drag_indicator(frame)

        return frame

    def _draw_drag_indicator(self, frame: np.ndarray):
        """Draw an indicator showing what is being dragged."""
        if not self.dragging_labware or self.dragging_labware not in self.labware:
            return

        labware = self.labware[self.dragging_labware]
        mx, my = self.mouse_pos

        # Draw a semi-transparent box following the mouse
        box_w, box_h = 120, 40
        box_x = mx - box_w // 2
        box_y = my - box_h - 10  # Above cursor

        # Clamp to screen bounds
        box_x = max(5, min(self.width - box_w - 5, box_x))
        box_y = max(5, min(self.height - box_h - 5, box_y))

        # Draw background
        overlay = frame.copy()
        cv2.rectangle(overlay, (box_x, box_y), (box_x + box_w, box_y + box_h),
                     (50, 50, 50), -1)
        cv2.rectangle(overlay, (box_x, box_y), (box_x + box_w, box_y + box_h),
                     (0, 165, 255), 2)  # Orange border
        cv2.addWeighted(overlay, 0.8, frame, 0.2, 0, frame)

        # Draw labware name
        name = labware.display_name[:15] if len(labware.display_name) > 15 else labware.display_name
        cv2.putText(frame, f"Moving: {name}", (box_x + 5, box_y + 15),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.35, self.COLORS['text'], 1, cv2.LINE_AA)
        cv2.putText(frame, f"From: {self.dragging_labware}", (box_x + 5, box_y + 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.35, self.COLORS['highlight'], 1, cv2.LINE_AA)

    def handle_mouse(self, event: int, x: int, y: int, flags: int, param: Any):
        """Handle mouse events for hover detection, tiprack click-to-set, and labware dragging."""
        import cv2
        self.mouse_pos = (x, y)

        # Check if hovering over a reagent button
        self.hovered_reagent = None
        if hasattr(self, 'reagent_buttons'):
            for reagent_name, (bx, by, bw, bh) in self.reagent_buttons.items():
                if bx <= x <= bx + bw and by <= y <= by + bh:
                    self.hovered_reagent = reagent_name
                    break

        # Check if hovering over a slot
        # When dragging, allow hovering over any slot (including empty ones) for drop targets
        # When not dragging, only hover over slots with labware
        if not self.hovered_reagent:
            self.hovered_slot = None
            for row in self.SLOTS:
                for slot in row:
                    sx, sy, sw, sh = self.get_slot_rect(slot)
                    if sx <= x <= sx + sw and sy <= y <= sy + sh:
                        if self.dragging_labware:
                            # When dragging, any slot is a valid hover target
                            self.hovered_slot = slot
                        elif slot in self.labware:
                            # When not dragging, only hover if labware present
                            self.hovered_slot = slot
                        break
                if self.hovered_slot:
                    break

        # Handle mouse down - start dragging or handle tiprack/plate click
        if event == cv2.EVENT_LBUTTONDOWN:
            if self.hovered_slot and self.hovered_slot in self.labware:
                labware = self.labware[self.hovered_slot]

                # Check if clicking on a tiprack tip first
                if labware.labware_type == 'tiprack' and self.tiprack_click_enabled:
                    tip_pos = self.get_tiprack_tip_at_pos(self.hovered_slot, x, y)
                    if tip_pos:
                        col, row = tip_pos
                        # Store the pending offset change for the GUI to pick up
                        self.pending_offset_change = {
                            'slot': self.hovered_slot,
                            'columns': col,
                            'rows': row,
                            'labware_type': labware.labware_type,
                            'display_name': labware.display_name
                        }
                        # Update the offset immediately for visual feedback
                        if labware.offset is None:
                            labware.offset = LabwareOffset(columns=col, rows=row)
                        else:
                            labware.offset.columns = col
                            labware.offset.rows = row
                        print(f"Tiprack offset set: {self.hovered_slot} -> column {col+1}, row {chr(ord('A')+row)}")
                        return  # Don't start dragging if we clicked a tip

                # Check if clicking on a plate well
                if labware.labware_type == 'plate':
                    well_pos = self.get_plate_well_at_pos(self.hovered_slot, x, y)
                    if well_pos:
                        col, row = well_pos
                        # Store the pending offset change for the GUI to pick up
                        self.pending_offset_change = {
                            'slot': self.hovered_slot,
                            'columns': col,
                            'rows': row,
                            'labware_type': labware.labware_type,
                            'display_name': labware.display_name
                        }
                        # Update the offset immediately for visual feedback
                        if labware.offset is None:
                            labware.offset = LabwareOffset(columns=col, rows=row)
                        else:
                            labware.offset.columns = col
                            labware.offset.rows = row
                        print(f"Plate offset set: {self.hovered_slot} -> column {col+1}, row {chr(ord('A')+row)}")
                        return  # Don't start dragging if we clicked a well

                # Start dragging this labware
                self.dragging_labware = self.hovered_slot
                self.drag_start_pos = (x, y)

        # Handle mouse move while dragging
        elif event == cv2.EVENT_MOUSEMOVE and self.dragging_labware:
            # Update hover to show potential drop target
            target_slot = self.get_slot_at_pos(x, y)
            if target_slot and target_slot != self.dragging_labware:
                self.hovered_slot = target_slot

        # Handle mouse up - complete drag
        elif event == cv2.EVENT_LBUTTONUP and self.dragging_labware:
            target_slot = self.get_slot_at_pos(x, y)
            if target_slot and target_slot != self.dragging_labware:
                # Store the pending move for the GUI to pick up
                self.pending_labware_move = {
                    'from_slot': self.dragging_labware,
                    'to_slot': target_slot
                }
                # Perform the swap immediately for visual feedback
                self._swap_labware(self.dragging_labware, target_slot)
                print(f"Moved labware: {self.dragging_labware} <-> {target_slot}")
            self.dragging_labware = None
            self.drag_start_pos = None

    def _swap_labware(self, slot1: str, slot2: str):
        """Swap labware between two slots."""
        labware1 = self.labware.get(slot1)
        labware2 = self.labware.get(slot2)

        # Update the labware dictionary
        if labware1:
            if labware2:
                # Both slots have labware - swap them
                self.labware[slot1] = labware2
                self.labware[slot2] = labware1
            else:
                # Only slot1 has labware - move it to slot2
                self.labware[slot2] = labware1
                del self.labware[slot1]
        elif labware2:
            # Only slot2 has labware - move it to slot1
            self.labware[slot1] = labware2
            del self.labware[slot2]

        # Update labware_id_to_slot mapping
        for labware_id, slot in list(self.labware_id_to_slot.items()):
            if slot == slot1:
                self.labware_id_to_slot[labware_id] = slot2
            elif slot == slot2:
                self.labware_id_to_slot[labware_id] = slot1

    def _extract_accessed_slots(self, commands: List[Dict]):
        """
        Extract all slots that are accessed by the protocol commands.
        This includes destinations for moveLabware, moveLid, etc.
        """
        for cmd in commands:
            cmd_type = cmd.get('commandType', '')
            params = cmd.get('params', {})

            # Check for newLocation in moveLabware commands
            if cmd_type in ('moveLabware', 'moveLid'):
                new_location = params.get('newLocation', {})
                if isinstance(new_location, dict):
                    slot = new_location.get('slotName', '')
                    if slot:
                        self.protocol_accessed_slots.add(slot)
                elif isinstance(new_location, str):
                    # Direct slot name
                    self.protocol_accessed_slots.add(new_location)

            # Check for location in loadLabware commands
            if cmd_type == 'loadLabware':
                location = params.get('location', {})
                if isinstance(location, dict):
                    slot = location.get('slotName', '')
                    if slot:
                        self.protocol_accessed_slots.add(slot)
                elif isinstance(location, str):
                    self.protocol_accessed_slots.add(location)

            # Check for moveToAddressableArea commands (gripper moves)
            if cmd_type == 'moveToAddressableArea':
                area_name = params.get('addressableAreaName', '')
                # Addressable areas can be slot names
                if area_name and len(area_name) == 2 and area_name[0] in 'ABCD' and area_name[1] in '1234':
                    self.protocol_accessed_slots.add(area_name)

    def _extract_protocol_offsets(self, protocol_path: str) -> Dict[str, Dict[str, int]]:
        """
        Try to extract offset configuration from protocol variables.

        This looks for common offset variable patterns in the protocol file.
        Returns a dict mapping slot -> offset config.
        """
        labware_offsets = {}

        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("protocol", protocol_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Look for any variables that look like offsets
            # Common patterns: TIPRACK_*_OFFSET, *_OFFSET, *_START_WELL, etc.
            for attr_name in dir(module):
                attr_value = getattr(module, attr_name)

                # Tuple offsets (columns, rows)
                if isinstance(attr_value, tuple) and len(attr_value) == 2:
                    if 'OFFSET' in attr_name.upper():
                        # Try to find which slot this applies to
                        # For now, store by variable name for later matching
                        pass

                # Integer well indices
                elif isinstance(attr_value, int) and 'START' in attr_name.upper() and 'WELL' in attr_name.upper():
                    pass

            # Get protocol-specific variables if they exist
            plate_layout = getattr(module, 'PLATE_LAYOUT', {})
            reagent_locations = getattr(module, 'REAGENT_LOCATIONS', {})

            # Store for use in load_from_protocol_data
            self._protocol_plate_layout = plate_layout
            self._protocol_reagent_locations = reagent_locations
            self._protocol_base_media_volume = getattr(module, 'BASE_MEDIA_VOLUME', 150)

        except Exception as e:
            print(f"Note: Could not extract variables from protocol: {e}")
            self._protocol_plate_layout = {}
            self._protocol_reagent_locations = {}
            self._protocol_base_media_volume = 150

        return labware_offsets

    def run_standalone(self, protocol_path: str):
        """Run the visualizer as a standalone window for any protocol."""
        from analyzer.runner import ProtocolAnalyzer

        # Analyze protocol
        print(f"Analyzing {protocol_path}...")
        analyzer = ProtocolAnalyzer()
        result = analyzer.analyze(protocol_path)

        if result.status != 'ok':
            print(f"Analysis failed: {result.errors}")
            return

        # Try to extract protocol-specific data (optional - works without it)
        self._extract_protocol_offsets(protocol_path)

        plate_layout = getattr(self, '_protocol_plate_layout', {})
        reagent_locations = getattr(self, '_protocol_reagent_locations', {})
        base_media_volume = getattr(self, '_protocol_base_media_volume', 150)

        # Extract protocol name from metadata if available
        protocol_name = ""
        if result.metadata:
            protocol_name = result.metadata.get('protocolName', '')
        if not protocol_name:
            # Fall back to filename
            protocol_name = Path(protocol_path).stem.replace('_', ' ').title()

        # Load data with commands for animation (no hardcoded offsets)
        self.load_from_protocol_data(
            result.labware,
            plate_layout,
            reagent_locations,
            base_media_volume,
            commands=result.commands,
            labware_offsets={},  # No hardcoded offsets - works with any protocol
            protocol_name=protocol_name
        )

        print(f"Loaded {len(result.commands)} commands, {len(self.labware)} labware items")

        # Show labware info
        print("\nLabware on deck:")
        for slot, lw in sorted(self.labware.items()):
            print(f"  {slot}: {lw.display_name} ({lw.labware_type})")

        # Create window
        window_name = 'Deck Visualizer'
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(window_name, self.handle_mouse)

        print("Press 'q' or ESC to exit")
        print("Press SPACE to step through commands, 'r' to reset")

        cmd_index = 0

        while True:
            frame = self.render()
            cv2.imshow(window_name, frame)

            key = cv2.waitKey(30) & 0xFF
            if key == ord('q') or key == 27:  # q or ESC
                break
            elif key == ord(' '):  # Space - step through commands
                if cmd_index < len(result.commands):
                    self.update_animation(cmd_index, result.commands[cmd_index])
                    cmd_index += 1
            elif key == ord('r'):  # Reset
                cmd_index = 0
                self.update_animation(0, None)

        cv2.destroyAllWindows()


def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: python deck_visualizer.py <protocol.py>")
        print("\nVisualizes the deck layout for an Opentrons protocol.")
        print("Hover over reagents in the legend to see volume distributions.")
        sys.exit(1)

    protocol_path = sys.argv[1]
    visualizer = DeckVisualizer()
    visualizer.run_standalone(protocol_path)


if __name__ == '__main__':
    main()
