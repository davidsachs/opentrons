"""
Command mapping from Python API to HTTP API.

Maps internal command representations to HTTP API command format.
"""

from typing import Any, Optional
from dataclasses import dataclass

from ..parser.protocol_model import (
    ParsedProtocol,
    ProtocolCommand,
    CommandType,
)


@dataclass
class HTTPCommand:
    """Represents an HTTP API command."""

    command_type: str
    params: dict[str, Any]
    intent: str = "protocol"  # "protocol", "setup", or "fixit"

    def to_dict(self) -> dict[str, Any]:
        """Convert to HTTP API format."""
        return {
            "commandType": self.command_type,
            "params": self.params,
            "intent": self.intent,
        }


class CommandMapper:
    """
    Maps parsed protocol commands to HTTP API commands.

    Handles:
    - Simple 1:1 command mappings
    - Complex command expansion (transfer, distribute, consolidate, mix)
    - Variable resolution (replacing variable names with IDs)
    """

    # Direct mapping from CommandType to HTTP commandType
    DIRECT_MAPPING = {
        CommandType.LOAD_LABWARE: "loadLabware",
        CommandType.LOAD_ADAPTER: "loadLabware",  # Adapters use same command
        CommandType.MOVE_LABWARE: "moveLabware",
        CommandType.LOAD_LID: "loadLid",
        CommandType.LOAD_LID_STACK: "loadLidStack",
        CommandType.MOVE_LID: "moveLid",
        CommandType.LOAD_PIPETTE: "loadPipette",
        CommandType.PICK_UP_TIP: "pickUpTip",
        CommandType.DROP_TIP: "dropTip",
        CommandType.DROP_TIP_IN_PLACE: "dropTipInPlace",
        CommandType.ASPIRATE: "aspirate",
        CommandType.ASPIRATE_IN_PLACE: "aspirateInPlace",
        CommandType.DISPENSE: "dispense",
        CommandType.DISPENSE_IN_PLACE: "dispenseInPlace",
        CommandType.BLOW_OUT: "blowout",
        CommandType.BLOW_OUT_IN_PLACE: "blowOutInPlace",
        CommandType.TOUCH_TIP: "touchTip",
        CommandType.AIR_GAP: "airGapInPlace",
        CommandType.PREPARE_TO_ASPIRATE: "prepareToAspirate",
        CommandType.MOVE_TO_WELL: "moveToWell",
        CommandType.MOVE_TO_COORDINATES: "moveToCoordinates",
        CommandType.MOVE_RELATIVE: "moveRelative",
        CommandType.HOME: "home",
        CommandType.RETRACT_AXIS: "retractAxis",
        CommandType.LOAD_MODULE: "loadModule",
        CommandType.LOAD_TRASH_BIN: "loadTrashBin",
        CommandType.LOAD_WASTE_CHUTE: "loadWasteChute",
        CommandType.COMMENT: "comment",
        CommandType.DELAY: "waitForDuration",
        CommandType.PAUSE: "waitForResume",
        CommandType.SET_RAIL_LIGHTS: "setRailLights",
        CommandType.CONFIGURE_FOR_VOLUME: "configureForVolume",
        CommandType.CONFIGURE_NOZZLE_LAYOUT: "configureNozzleLayout",
        CommandType.LOAD_LIQUID: "loadLiquid",
        CommandType.LIQUID_PROBE: "liquidProbe",
        CommandType.TRY_LIQUID_PROBE: "tryLiquidProbe",
        CommandType.GET_TIP_PRESENCE: "getTipPresence",
        CommandType.VERIFY_TIP_PRESENCE: "verifyTipPresence",
        # Temperature module
        CommandType.TEMP_SET_TEMPERATURE: "temperatureModule/setTargetTemperature",
        CommandType.TEMP_WAIT_FOR_TEMPERATURE: "temperatureModule/waitForTemperature",
        CommandType.TEMP_DEACTIVATE: "temperatureModule/deactivate",
        # Thermocycler
        CommandType.TC_OPEN_LID: "thermocycler/openLid",
        CommandType.TC_CLOSE_LID: "thermocycler/closeLid",
        CommandType.TC_SET_TARGET_BLOCK_TEMPERATURE: "thermocycler/setTargetBlockTemperature",
        CommandType.TC_WAIT_FOR_BLOCK_TEMPERATURE: "thermocycler/waitForBlockTemperature",
        CommandType.TC_SET_TARGET_LID_TEMPERATURE: "thermocycler/setTargetLidTemperature",
        CommandType.TC_WAIT_FOR_LID_TEMPERATURE: "thermocycler/waitForLidTemperature",
        CommandType.TC_RUN_PROFILE: "thermocycler/runProfile",
        CommandType.TC_DEACTIVATE_BLOCK: "thermocycler/deactivateBlock",
        CommandType.TC_DEACTIVATE_LID: "thermocycler/deactivateLid",
        # Heater-Shaker
        CommandType.HS_SET_TARGET_TEMPERATURE: "heaterShaker/setTargetTemperature",
        CommandType.HS_WAIT_FOR_TEMPERATURE: "heaterShaker/waitForTemperature",
        CommandType.HS_SET_AND_WAIT_FOR_SHAKE_SPEED: "heaterShaker/setAndWaitForShakeSpeed",
        CommandType.HS_DEACTIVATE_HEATER: "heaterShaker/deactivateHeater",
        CommandType.HS_DEACTIVATE_SHAKER: "heaterShaker/deactivateShaker",
        CommandType.HS_OPEN_LABWARE_LATCH: "heaterShaker/openLabwareLatch",
        CommandType.HS_CLOSE_LABWARE_LATCH: "heaterShaker/closeLabwareLatch",
        # Magnetic module
        CommandType.MAG_ENGAGE: "magneticModule/engage",
        CommandType.MAG_DISENGAGE: "magneticModule/disengage",
        # Absorbance reader
        CommandType.ABS_INITIALIZE: "absorbanceReader/initialize",
        CommandType.ABS_OPEN_LID: "absorbanceReader/openLid",
        CommandType.ABS_CLOSE_LID: "absorbanceReader/closeLid",
        CommandType.ABS_READ: "absorbanceReader/read",
        # Flex stacker
        CommandType.STACKER_STORE: "flexStacker/store",
        CommandType.STACKER_RETRIEVE: "flexStacker/retrieve",
    }

    def __init__(self, protocol: ParsedProtocol) -> None:
        self.protocol = protocol
        self._command_id_counter = 0
        # Track tip origin for each pipette (pipette_var -> (labware_var, well_name))
        self._tip_origin: dict[str, tuple[str, str]] = {}

    def map_all_commands(self) -> list[HTTPCommand]:
        """Map all protocol commands to HTTP commands."""
        http_commands: list[HTTPCommand] = []

        for cmd in self.protocol.commands:
            mapped = self.map_command(cmd)
            http_commands.extend(mapped)

        return http_commands

    def map_command(self, cmd: ProtocolCommand) -> list[HTTPCommand]:
        """Map a single command, potentially expanding to multiple HTTP commands."""
        # Handle complex commands that expand to multiple
        if cmd.command_type == CommandType.MIX:
            return self._expand_mix(cmd)
        elif cmd.command_type == CommandType.TRANSFER:
            return self._expand_transfer(cmd)
        elif cmd.command_type == CommandType.DISTRIBUTE:
            return self._expand_distribute(cmd)
        elif cmd.command_type == CommandType.CONSOLIDATE:
            return self._expand_consolidate(cmd)

        # Simple 1:1 mapping
        http_type = self.DIRECT_MAPPING.get(cmd.command_type)
        if not http_type:
            return []

        params = self._build_params(cmd)
        return [HTTPCommand(command_type=http_type, params=params)]

    def _build_params(self, cmd: ProtocolCommand) -> dict[str, Any]:
        """Build HTTP API params from command."""
        params = dict(cmd.params)

        # Resolve variable references to IDs
        if cmd.pipette_var:
            pipette_id = self.protocol.pipette_id_map.get(cmd.pipette_var)
            if pipette_id:
                params["pipetteId"] = pipette_id

        if cmd.labware_var:
            labware_id = self.protocol.labware_id_map.get(cmd.labware_var)
            if labware_id:
                params["labwareId"] = labware_id

        if cmd.module_var:
            module_id = self.protocol.module_id_map.get(cmd.module_var)
            if module_id:
                params["moduleId"] = module_id

        if cmd.well_name:
            params["wellName"] = cmd.well_name

        # Handle specific command type params
        if cmd.command_type == CommandType.LOAD_LABWARE:
            params = self._build_load_labware_params(cmd)
        elif cmd.command_type == CommandType.LOAD_PIPETTE:
            params = self._build_load_pipette_params(cmd)
        elif cmd.command_type == CommandType.LOAD_MODULE:
            params = self._build_load_module_params(cmd)
        elif cmd.command_type in (CommandType.ASPIRATE, CommandType.DISPENSE):
            params = self._build_liquid_handling_params(cmd)
        elif cmd.command_type == CommandType.PICK_UP_TIP:
            params = self._build_pick_up_tip_params(cmd)
        elif cmd.command_type == CommandType.DROP_TIP:
            params = self._build_drop_tip_params(cmd)

        return params

    def _build_load_labware_params(self, cmd: ProtocolCommand) -> dict[str, Any]:
        """Build params for loadLabware command."""
        labware = self.protocol.get_labware_by_var(cmd.labware_var or "")

        params: dict[str, Any] = {
            "loadName": cmd.params.get("loadName"),
            "namespace": cmd.params.get("namespace", "opentrons"),
            "version": cmd.params.get("version", 1),
        }

        # Build location
        location = cmd.params.get("location")
        if isinstance(location, str):
            if location.startswith("$"):
                # Reference to another labware (stacking)
                ref_var = location[1:]
                ref_id = self.protocol.labware_id_map.get(ref_var)
                if ref_id:
                    params["location"] = {"labwareId": ref_id}
            else:
                params["location"] = {"slotName": location}
        elif isinstance(location, int):
            params["location"] = {"slotName": str(location)}
        elif isinstance(location, dict):
            params["location"] = location

        if cmd.params.get("label"):
            params["displayName"] = cmd.params["label"]

        return params

    def _build_load_pipette_params(self, cmd: ProtocolCommand) -> dict[str, Any]:
        """Build params for loadPipette command."""
        return {
            "pipetteName": cmd.params.get("instrumentName"),
            "mount": cmd.params.get("mount", "left"),
        }

    def _build_load_module_params(self, cmd: ProtocolCommand) -> dict[str, Any]:
        """Build params for loadModule command."""
        return {
            "model": cmd.params.get("moduleModel"),
            "location": cmd.params.get("location", {}),
        }

    def _build_liquid_handling_params(self, cmd: ProtocolCommand) -> dict[str, Any]:
        """Build params for aspirate/dispense commands."""
        params: dict[str, Any] = {
            "volume": cmd.params.get("volume"),
        }

        if cmd.pipette_var:
            pipette_id = self.protocol.pipette_id_map.get(cmd.pipette_var)
            if pipette_id:
                params["pipetteId"] = pipette_id

        if cmd.labware_var:
            labware_id = self.protocol.labware_id_map.get(cmd.labware_var)
            if labware_id:
                params["labwareId"] = labware_id

        if cmd.well_name:
            params["wellName"] = cmd.well_name

        if "flowRate" in cmd.params:
            params["flowRate"] = cmd.params["flowRate"]

        if "wellLocation" in cmd.params:
            params["wellLocation"] = cmd.params["wellLocation"]

        return params

    def _build_pick_up_tip_params(self, cmd: ProtocolCommand) -> dict[str, Any]:
        """Build params for pickUpTip command."""
        params: dict[str, Any] = {}

        if cmd.pipette_var:
            pipette_id = self.protocol.pipette_id_map.get(cmd.pipette_var)
            if pipette_id:
                params["pipetteId"] = pipette_id
            # Store tip origin for this pipette (for return_tip)
            if cmd.labware_var and cmd.well_name:
                self._tip_origin[cmd.pipette_var] = (cmd.labware_var, cmd.well_name)

        if cmd.labware_var:
            labware_id = self.protocol.labware_id_map.get(cmd.labware_var)
            if labware_id:
                params["labwareId"] = labware_id

        if cmd.well_name:
            params["wellName"] = cmd.well_name

        return params

    def _build_drop_tip_params(self, cmd: ProtocolCommand) -> dict[str, Any]:
        """Build params for dropTip command."""
        params: dict[str, Any] = {}

        if cmd.pipette_var:
            pipette_id = self.protocol.pipette_id_map.get(cmd.pipette_var)
            if pipette_id:
                params["pipetteId"] = pipette_id

        # Check if this is a return_tip (returnToOrigin flag set)
        if cmd.params.get("returnToOrigin") and cmd.pipette_var:
            # Use the stored tip origin location
            origin = self._tip_origin.get(cmd.pipette_var)
            if origin:
                labware_var, well_name = origin
                labware_id = self.protocol.labware_id_map.get(labware_var)
                if labware_id:
                    params["labwareId"] = labware_id
                params["wellName"] = well_name
                # Clear the origin after returning
                del self._tip_origin[cmd.pipette_var]
        else:
            # Normal drop_tip with explicit location
            if cmd.labware_var:
                labware_id = self.protocol.labware_id_map.get(cmd.labware_var)
                if labware_id:
                    params["labwareId"] = labware_id

            if cmd.well_name:
                params["wellName"] = cmd.well_name

        if cmd.params.get("homeAfter") is not None:
            params["homeAfter"] = cmd.params["homeAfter"]

        return params

    def _expand_mix(self, cmd: ProtocolCommand) -> list[HTTPCommand]:
        """Expand mix command to aspirate/dispense pairs."""
        commands: list[HTTPCommand] = []
        repetitions = cmd.params.get("repetitions", 1)
        volume = cmd.params.get("volume")

        base_params = {
            "volume": volume,
        }

        if cmd.pipette_var:
            pipette_id = self.protocol.pipette_id_map.get(cmd.pipette_var)
            if pipette_id:
                base_params["pipetteId"] = pipette_id

        if cmd.labware_var:
            labware_id = self.protocol.labware_id_map.get(cmd.labware_var)
            if labware_id:
                base_params["labwareId"] = labware_id

        if cmd.well_name:
            base_params["wellName"] = cmd.well_name

        for _ in range(repetitions):
            commands.append(HTTPCommand(
                command_type="aspirate",
                params=dict(base_params),
            ))
            commands.append(HTTPCommand(
                command_type="dispense",
                params=dict(base_params),
            ))

        return commands

    def _expand_transfer(self, cmd: ProtocolCommand) -> list[HTTPCommand]:
        """Expand transfer command to individual operations."""
        commands: list[HTTPCommand] = []

        volume = cmd.params.get("volume")
        source = cmd.params.get("source")
        dest = cmd.params.get("dest")
        new_tip = cmd.params.get("new_tip", "once")
        touch_tip = cmd.params.get("touch_tip", False)
        blow_out = cmd.params.get("blow_out", False)
        mix_before = cmd.params.get("mix_before")
        mix_after = cmd.params.get("mix_after")
        air_gap = cmd.params.get("air_gap", 0)

        pipette_id = None
        if cmd.pipette_var:
            pipette_id = self.protocol.pipette_id_map.get(cmd.pipette_var)

        # Normalize sources and destinations to lists
        sources = source if isinstance(source, list) else [source]
        dests = dest if isinstance(dest, list) else [dest]

        # Handle volume as list or scalar
        volumes = volume if isinstance(volume, list) else [volume] * max(len(sources), len(dests))

        # Zip sources and destinations
        transfers = list(zip(sources, dests, volumes))

        # Pick up tip if new_tip is "once" or "always"
        if new_tip in ("once", "always"):
            commands.extend(self._create_pick_up_tip(cmd))

        for src, dst, vol in transfers:
            if new_tip == "always" and transfers.index((src, dst, vol)) > 0:
                commands.extend(self._create_drop_tip(cmd))
                commands.extend(self._create_pick_up_tip(cmd))

            # Mix before
            if mix_before:
                reps, mix_vol = mix_before
                for _ in range(reps):
                    commands.append(self._create_aspirate(pipette_id, src, mix_vol))
                    commands.append(self._create_dispense(pipette_id, src, mix_vol))

            # Aspirate
            commands.append(self._create_aspirate(pipette_id, src, vol))

            # Air gap
            if air_gap:
                commands.append(HTTPCommand(
                    command_type="airGapInPlace",
                    params={"pipetteId": pipette_id, "volume": air_gap},
                ))

            # Touch tip at source
            if touch_tip:
                commands.append(self._create_touch_tip(pipette_id, src))

            # Dispense
            commands.append(self._create_dispense(pipette_id, dst, vol))

            # Touch tip at destination
            if touch_tip:
                commands.append(self._create_touch_tip(pipette_id, dst))

            # Blow out
            if blow_out:
                commands.append(HTTPCommand(
                    command_type="blowOutInPlace",
                    params={"pipetteId": pipette_id},
                ))

            # Mix after
            if mix_after:
                reps, mix_vol = mix_after
                for _ in range(reps):
                    commands.append(self._create_aspirate(pipette_id, dst, mix_vol))
                    commands.append(self._create_dispense(pipette_id, dst, mix_vol))

        # Drop tip
        if new_tip in ("once", "always"):
            commands.extend(self._create_drop_tip(cmd))

        return commands

    def _expand_distribute(self, cmd: ProtocolCommand) -> list[HTTPCommand]:
        """Expand distribute command to individual operations."""
        commands: list[HTTPCommand] = []

        volume = cmd.params.get("volume")
        source = cmd.params.get("source")
        dest = cmd.params.get("dest")
        new_tip = cmd.params.get("new_tip", "once")
        disposal_volume = cmd.params.get("disposal_volume", 0)
        air_gap = cmd.params.get("air_gap", 0)

        pipette_id = None
        if cmd.pipette_var:
            pipette_id = self.protocol.pipette_id_map.get(cmd.pipette_var)

        dests = dest if isinstance(dest, list) else [dest]
        volumes = volume if isinstance(volume, list) else [volume] * len(dests)

        if new_tip in ("once", "always"):
            commands.extend(self._create_pick_up_tip(cmd))

        # Calculate total volume needed
        total_vol = sum(volumes) + disposal_volume

        # Aspirate from source
        commands.append(self._create_aspirate(pipette_id, source, total_vol))

        # Dispense to each destination
        for dst, vol in zip(dests, volumes):
            if air_gap:
                commands.append(HTTPCommand(
                    command_type="airGapInPlace",
                    params={"pipetteId": pipette_id, "volume": air_gap},
                ))

            commands.append(self._create_dispense(pipette_id, dst, vol))

        # Blow out disposal volume
        if disposal_volume:
            commands.append(HTTPCommand(
                command_type="blowOutInPlace",
                params={"pipetteId": pipette_id},
            ))

        if new_tip in ("once", "always"):
            commands.extend(self._create_drop_tip(cmd))

        return commands

    def _expand_consolidate(self, cmd: ProtocolCommand) -> list[HTTPCommand]:
        """Expand consolidate command to individual operations."""
        commands: list[HTTPCommand] = []

        volume = cmd.params.get("volume")
        source = cmd.params.get("source")
        dest = cmd.params.get("dest")
        new_tip = cmd.params.get("new_tip", "once")
        air_gap = cmd.params.get("air_gap", 0)

        pipette_id = None
        if cmd.pipette_var:
            pipette_id = self.protocol.pipette_id_map.get(cmd.pipette_var)

        sources = source if isinstance(source, list) else [source]
        volumes = volume if isinstance(volume, list) else [volume] * len(sources)

        if new_tip in ("once", "always"):
            commands.extend(self._create_pick_up_tip(cmd))

        # Aspirate from each source
        for src, vol in zip(sources, volumes):
            commands.append(self._create_aspirate(pipette_id, src, vol))

            if air_gap:
                commands.append(HTTPCommand(
                    command_type="airGapInPlace",
                    params={"pipetteId": pipette_id, "volume": air_gap},
                ))

        # Dispense to destination
        total_vol = sum(volumes)
        commands.append(self._create_dispense(pipette_id, dest, total_vol))

        if new_tip in ("once", "always"):
            commands.extend(self._create_drop_tip(cmd))

        return commands

    def _create_pick_up_tip(self, cmd: ProtocolCommand) -> list[HTTPCommand]:
        """Create pick up tip command."""
        params: dict[str, Any] = {}

        if cmd.pipette_var:
            pipette_id = self.protocol.pipette_id_map.get(cmd.pipette_var)
            if pipette_id:
                params["pipetteId"] = pipette_id

            # Find tip rack from pipette
            pipette = self.protocol.get_pipette_by_var(cmd.pipette_var)
            if pipette and pipette.tip_racks:
                tip_rack_var = pipette.tip_racks[0]
                tip_rack_id = self.protocol.labware_id_map.get(tip_rack_var)
                if tip_rack_id:
                    params["labwareId"] = tip_rack_id
                    params["wellName"] = "A1"  # Will be auto-tracked

        return [HTTPCommand(command_type="pickUpTip", params=params)]

    def _create_drop_tip(self, cmd: ProtocolCommand) -> list[HTTPCommand]:
        """Create drop tip command."""
        params: dict[str, Any] = {}

        if cmd.pipette_var:
            pipette_id = self.protocol.pipette_id_map.get(cmd.pipette_var)
            if pipette_id:
                params["pipetteId"] = pipette_id

        return [HTTPCommand(command_type="dropTipInPlace", params=params)]

    def _create_aspirate(
        self, pipette_id: Optional[str], location: Any, volume: float
    ) -> HTTPCommand:
        """Create aspirate command."""
        params: dict[str, Any] = {"volume": volume}

        if pipette_id:
            params["pipetteId"] = pipette_id

        labware_id, well_name = self._resolve_location(location)
        if labware_id:
            params["labwareId"] = labware_id
        if well_name:
            params["wellName"] = well_name

        return HTTPCommand(command_type="aspirate", params=params)

    def _create_dispense(
        self, pipette_id: Optional[str], location: Any, volume: float
    ) -> HTTPCommand:
        """Create dispense command."""
        params: dict[str, Any] = {"volume": volume}

        if pipette_id:
            params["pipetteId"] = pipette_id

        labware_id, well_name = self._resolve_location(location)
        if labware_id:
            params["labwareId"] = labware_id
        if well_name:
            params["wellName"] = well_name

        return HTTPCommand(command_type="dispense", params=params)

    def _create_touch_tip(self, pipette_id: Optional[str], location: Any) -> HTTPCommand:
        """Create touch tip command."""
        params: dict[str, Any] = {}

        if pipette_id:
            params["pipetteId"] = pipette_id

        labware_id, well_name = self._resolve_location(location)
        if labware_id:
            params["labwareId"] = labware_id
        if well_name:
            params["wellName"] = well_name

        return HTTPCommand(command_type="touchTip", params=params)

    def _resolve_location(self, location: Any) -> tuple[Optional[str], Optional[str]]:
        """Resolve a location reference to labware ID and well name."""
        if isinstance(location, str):
            if location.startswith("$"):
                # Variable reference like "$plate[A1]"
                import re
                match = re.match(r"\$(\w+)\[([^\]]+)\]", location)
                if match:
                    var_name = match.group(1)
                    well_name = match.group(2)
                    labware_id = self.protocol.labware_id_map.get(var_name)
                    return labware_id, well_name

                # Just variable reference
                var_name = location[1:]
                labware_id = self.protocol.labware_id_map.get(var_name)
                return labware_id, None

        return None, None
