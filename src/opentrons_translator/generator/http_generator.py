"""
HTTP API code generator.

Generates Python scripts that use the HTTP API to execute protocols.
"""

import json
from typing import Any, Optional
from pathlib import Path

from ..parser.protocol_model import (
    ParsedProtocol,
    ProtocolCommand,
    CommandType,
    LoadedLabware,
    LoadedPipette,
    LoadedModule,
    RobotType,
)
from ..mapping.commands import CommandMapper, HTTPCommand
from ..mapping.labware import LabwareMapper
from ..mapping.modules import ModuleMapper
from ..mapping.pipettes import PipetteMapper
from .templates import ProtocolTemplate


class HTTPGenerator:
    """
    Generates HTTP API Python scripts from parsed protocols.

    The generated scripts:
    - Use the requests library to communicate with the robot
    - Execute commands in the same order as the original protocol
    - Track resource IDs (labware, pipettes, modules)
    - Handle errors appropriately
    """

    def __init__(self, protocol: ParsedProtocol) -> None:
        self.protocol = protocol
        self._indent = "    "
        self._current_indent = 0

        # Generate IDs for resources (these will be assigned by the robot at runtime)
        self._assign_placeholder_ids()

    def _assign_placeholder_ids(self) -> None:
        """Assign placeholder variable names for ID tracking."""
        for i, lw in enumerate(self.protocol.labware):
            self.protocol.labware_id_map[lw.variable_name] = lw.variable_name

        for i, p in enumerate(self.protocol.pipettes):
            self.protocol.pipette_id_map[p.variable_name] = p.variable_name

        for i, m in enumerate(self.protocol.modules):
            self.protocol.module_id_map[m.variable_name] = m.variable_name

        for i, liquid in enumerate(self.protocol.liquids):
            self.protocol.liquid_id_map[liquid.variable_name] = liquid.variable_name

    def generate(self) -> str:
        """Generate the complete HTTP API protocol script."""
        lines: list[str] = []

        # Header
        lines.append(ProtocolTemplate.get_header(
            original_name=self.protocol.metadata.protocol_name or "Translated Protocol",
            api_level=self.protocol.metadata.api_level,
            robot_type=self.protocol.metadata.robot_type.value,
        ))

        # Protocol execution function
        lines.append("")
        lines.append("def execute_protocol(runner: HTTPProtocolRunner) -> None:")
        lines.append('    """Execute the protocol commands."""')
        lines.append("")

        # Generate resource loading
        lines.extend(self._generate_resource_loading())

        # Generate command execution
        lines.extend(self._generate_command_execution())

        # Footer
        lines.append(ProtocolTemplate.get_footer())

        return "\n".join(lines)

    def generate_to_file(self, output_path: str | Path) -> None:
        """Generate and write to a file."""
        output_path = Path(output_path)
        content = self.generate()
        output_path.write_text(content)

    def _generate_resource_loading(self) -> list[str]:
        """Generate code for loading resources."""
        lines: list[str] = []
        indent = self._indent

        # Load modules first
        if self.protocol.modules:
            lines.append(f"{indent}# Load modules")
            for module in self.protocol.modules:
                lines.extend(self._generate_module_load(module))
            lines.append("")

        # Load labware
        if self.protocol.labware:
            lines.append(f"{indent}# Load labware")
            for labware in self.protocol.labware:
                lines.extend(self._generate_labware_load(labware))
            lines.append("")

        # Load pipettes
        if self.protocol.pipettes:
            lines.append(f"{indent}# Load pipettes")
            for pipette in self.protocol.pipettes:
                lines.extend(self._generate_pipette_load(pipette))
            lines.append("")

        return lines

    def _generate_module_load(self, module: LoadedModule) -> list[str]:
        """Generate code for loading a module."""
        indent = self._indent
        model = ModuleMapper.get_http_model(module.module_type)

        return [
            f'{indent}runner.load_module(',
            f'{indent}    "{module.variable_name}",',
            f'{indent}    "{model}",',
            f'{indent}    {{"slotName": "{module.location}"}},',
            f'{indent})',
        ]

    def _generate_labware_load(self, labware: LoadedLabware) -> list[str]:
        """Generate code for loading labware."""
        indent = self._indent
        load_name = LabwareMapper.get_http_load_name(labware.load_name)

        # Determine location
        location = self._build_location_dict(labware)
        location_str = json.dumps(location)

        lines = [
            f'{indent}runner.load_labware(',
            f'{indent}    "{labware.variable_name}",',
            f'{indent}    "{load_name}",',
            f'{indent}    {location_str},',
        ]

        if labware.namespace != "opentrons":
            lines.append(f'{indent}    namespace="{labware.namespace}",')

        if labware.version != 1:
            lines.append(f'{indent}    version={labware.version},')

        if labware.label:
            lines.append(f'{indent}    display_name="{labware.label}",')

        lines.append(f'{indent})')

        return lines

    def _build_location_dict(self, labware: LoadedLabware) -> dict[str, Any]:
        """Build location dictionary for labware."""
        loc = labware.location

        if loc.labware_id:
            # Stacked on another labware
            return {"labwareId": f"runner.labware_ids['{loc.labware_id}']"}
        elif loc.adapter_id:
            # On an adapter
            return {"labwareId": f"runner.labware_ids['{loc.adapter_id}']"}
        elif loc.module_id:
            # On a module
            return {"moduleId": f"runner.module_ids['{loc.module_id}']"}
        else:
            # On deck slot
            return {"slotName": loc.slot}

    def _generate_pipette_load(self, pipette: LoadedPipette) -> list[str]:
        """Generate code for loading a pipette."""
        indent = self._indent
        pipette_name = PipetteMapper.get_http_pipette_name(pipette.instrument_name)

        return [
            f'{indent}runner.load_pipette(',
            f'{indent}    "{pipette.variable_name}",',
            f'{indent}    "{pipette_name}",',
            f'{indent}    "{pipette.mount.value}",',
            f'{indent})',
        ]

    def _generate_command_execution(self) -> list[str]:
        """Generate code for executing protocol commands."""
        lines: list[str] = []
        indent = self._indent

        # Skip load commands as they're handled separately
        load_commands = {
            CommandType.LOAD_LABWARE,
            CommandType.LOAD_ADAPTER,
            CommandType.LOAD_PIPETTE,
            CommandType.LOAD_MODULE,
            CommandType.LOAD_TRASH_BIN,
            CommandType.LOAD_WASTE_CHUTE,
            CommandType.DEFINE_LIQUID,
        }

        lines.append(f"{indent}# Execute protocol commands")
        lines.append("")

        for cmd in self.protocol.commands:
            if cmd.command_type in load_commands:
                continue

            lines.extend(self._generate_command(cmd))

        return lines

    def _generate_command(self, cmd: ProtocolCommand) -> list[str]:
        """Generate code for a single command."""
        indent = self._indent
        lines: list[str] = []

        # Add source code as comment if available
        if cmd.source_code:
            source = cmd.source_code.strip()
            if source:
                lines.append(f"{indent}# {source}")

        # Handle different command types
        if cmd.command_type == CommandType.PICK_UP_TIP:
            lines.extend(self._generate_pick_up_tip(cmd))
        elif cmd.command_type in (CommandType.DROP_TIP, CommandType.DROP_TIP_IN_PLACE):
            lines.extend(self._generate_drop_tip(cmd))
        elif cmd.command_type == CommandType.ASPIRATE:
            lines.extend(self._generate_aspirate(cmd))
        elif cmd.command_type == CommandType.DISPENSE:
            lines.extend(self._generate_dispense(cmd))
        elif cmd.command_type in (CommandType.BLOW_OUT, CommandType.BLOW_OUT_IN_PLACE):
            lines.extend(self._generate_blow_out(cmd))
        elif cmd.command_type == CommandType.TOUCH_TIP:
            lines.extend(self._generate_touch_tip(cmd))
        elif cmd.command_type == CommandType.AIR_GAP:
            lines.extend(self._generate_air_gap(cmd))
        elif cmd.command_type == CommandType.MIX:
            lines.extend(self._generate_mix(cmd))
        elif cmd.command_type in (
            CommandType.TRANSFER,
            CommandType.DISTRIBUTE,
            CommandType.CONSOLIDATE,
        ):
            lines.extend(self._generate_complex_command(cmd))
        elif cmd.command_type == CommandType.HOME:
            lines.append(f"{indent}runner.home()")
        elif cmd.command_type == CommandType.DELAY:
            seconds = cmd.params.get("seconds", 0)
            lines.append(f"{indent}runner.delay({seconds})")
        elif cmd.command_type == CommandType.PAUSE:
            msg = cmd.params.get("message", "")
            lines.append(f'{indent}runner.pause("{msg}")')
        elif cmd.command_type == CommandType.COMMENT:
            msg = cmd.params.get("message", "")
            lines.append(f'{indent}runner.comment("{msg}")')
        elif cmd.command_type == CommandType.SET_RAIL_LIGHTS:
            on = cmd.params.get("on", True)
            lines.append(
                f'{indent}runner.execute_command("setRailLights", {{"on": {on}}})'
            )
        elif cmd.command_type == CommandType.MOVE_LABWARE:
            lines.extend(self._generate_move_labware(cmd))
        elif cmd.command_type == CommandType.CONFIGURE_FOR_VOLUME:
            lines.extend(self._generate_configure_for_volume(cmd))
        elif cmd.command_type == CommandType.CONFIGURE_NOZZLE_LAYOUT:
            lines.extend(self._generate_configure_nozzle_layout(cmd))
        # Module commands
        elif cmd.command_type.value.startswith("temperatureModule"):
            lines.extend(self._generate_temp_module_command(cmd))
        elif cmd.command_type.value.startswith("thermocycler"):
            lines.extend(self._generate_thermocycler_command(cmd))
        elif cmd.command_type.value.startswith("heaterShaker"):
            lines.extend(self._generate_heater_shaker_command(cmd))
        elif cmd.command_type.value.startswith("magneticModule"):
            lines.extend(self._generate_magnetic_module_command(cmd))
        elif cmd.command_type.value.startswith("absorbanceReader"):
            lines.extend(self._generate_absorbance_reader_command(cmd))
        elif cmd.command_type.value.startswith("flexStacker"):
            lines.extend(self._generate_flex_stacker_command(cmd))
        else:
            # Generic command
            lines.extend(self._generate_generic_command(cmd))

        lines.append("")
        return lines

    def _generate_pick_up_tip(self, cmd: ProtocolCommand) -> list[str]:
        """Generate pick up tip code."""
        indent = self._indent
        pipette_var = cmd.pipette_var or "pipette"
        labware_var = cmd.labware_var or "tip_rack"
        well_name = cmd.well_name or "A1"

        return [
            f'{indent}runner.pick_up_tip("{pipette_var}", "{labware_var}", "{well_name}")'
        ]

    def _generate_drop_tip(self, cmd: ProtocolCommand) -> list[str]:
        """Generate drop tip code."""
        indent = self._indent
        pipette_var = cmd.pipette_var or "pipette"

        if cmd.labware_var and cmd.well_name:
            return [
                f'{indent}runner.drop_tip("{pipette_var}", "{cmd.labware_var}", "{cmd.well_name}")'
            ]
        else:
            return [f'{indent}runner.drop_tip("{pipette_var}")']

    def _generate_aspirate(self, cmd: ProtocolCommand) -> list[str]:
        """Generate aspirate code."""
        indent = self._indent
        pipette_var = cmd.pipette_var or "pipette"
        labware_var = cmd.labware_var or "plate"
        well_name = cmd.well_name or "A1"
        volume = cmd.params.get("volume", 0)

        args = [
            f'"{pipette_var}"',
            f'"{labware_var}"',
            f'"{well_name}"',
            str(volume),
        ]

        if "flowRate" in cmd.params:
            args.append(f'flow_rate={cmd.params["flowRate"]}')

        return [f"{indent}runner.aspirate({', '.join(args)})"]

    def _generate_dispense(self, cmd: ProtocolCommand) -> list[str]:
        """Generate dispense code."""
        indent = self._indent
        pipette_var = cmd.pipette_var or "pipette"
        labware_var = cmd.labware_var or "plate"
        well_name = cmd.well_name or "A1"
        volume = cmd.params.get("volume", 0)

        args = [
            f'"{pipette_var}"',
            f'"{labware_var}"',
            f'"{well_name}"',
            str(volume),
        ]

        if "flowRate" in cmd.params:
            args.append(f'flow_rate={cmd.params["flowRate"]}')
        if "pushOut" in cmd.params:
            args.append(f'push_out={cmd.params["pushOut"]}')

        return [f"{indent}runner.dispense({', '.join(args)})"]

    def _generate_blow_out(self, cmd: ProtocolCommand) -> list[str]:
        """Generate blow out code."""
        indent = self._indent
        pipette_var = cmd.pipette_var or "pipette"

        if cmd.labware_var and cmd.well_name:
            return [
                f'{indent}runner.blow_out("{pipette_var}", "{cmd.labware_var}", "{cmd.well_name}")'
            ]
        else:
            return [f'{indent}runner.blow_out("{pipette_var}")']

    def _generate_touch_tip(self, cmd: ProtocolCommand) -> list[str]:
        """Generate touch tip code."""
        indent = self._indent
        pipette_var = cmd.pipette_var or "pipette"
        labware_var = cmd.labware_var or "plate"
        well_name = cmd.well_name or "A1"

        return [
            f'{indent}runner.touch_tip("{pipette_var}", "{labware_var}", "{well_name}")'
        ]

    def _generate_air_gap(self, cmd: ProtocolCommand) -> list[str]:
        """Generate air gap code."""
        indent = self._indent
        pipette_var = cmd.pipette_var or "pipette"
        volume = cmd.params.get("volume", 0)

        return [
            f'{indent}runner.execute_command("airGapInPlace", {{',
            f'{indent}    "pipetteId": runner.pipette_ids["{pipette_var}"],',
            f'{indent}    "volume": {volume},',
            f"{indent}}})",
        ]

    def _generate_mix(self, cmd: ProtocolCommand) -> list[str]:
        """Generate mix code (expanded to aspirate/dispense loops)."""
        indent = self._indent
        lines: list[str] = []

        pipette_var = cmd.pipette_var or "pipette"
        labware_var = cmd.labware_var or "plate"
        well_name = cmd.well_name or "A1"
        repetitions = cmd.params.get("repetitions", 1)
        volume = cmd.params.get("volume", 0)

        lines.append(f"{indent}# Mix {repetitions} times")
        lines.append(f"{indent}for _ in range({repetitions}):")
        lines.append(
            f'{indent}    runner.aspirate("{pipette_var}", "{labware_var}", "{well_name}", {volume})'
        )
        lines.append(
            f'{indent}    runner.dispense("{pipette_var}", "{labware_var}", "{well_name}", {volume})'
        )

        return lines

    def _generate_complex_command(self, cmd: ProtocolCommand) -> list[str]:
        """Generate code for complex commands (transfer, distribute, consolidate)."""
        indent = self._indent
        lines: list[str] = []

        # Use the command mapper to expand the command
        mapper = CommandMapper(self.protocol)
        http_commands = mapper.map_command(cmd)

        lines.append(f"{indent}# Complex command: {cmd.command_type.value}")

        for http_cmd in http_commands:
            params_str = json.dumps(http_cmd.params, indent=8)
            # Replace placeholder IDs with runtime lookups
            params_str = self._replace_id_placeholders(params_str)
            lines.append(
                f'{indent}runner.execute_command("{http_cmd.command_type}", {params_str})'
            )

        return lines

    def _generate_move_labware(self, cmd: ProtocolCommand) -> list[str]:
        """Generate move labware code."""
        indent = self._indent
        labware_var = cmd.labware_var or "labware"
        new_location = cmd.params.get("newLocation", {})
        strategy = cmd.params.get("strategy", "manualMoveWithPause")

        new_loc_str = json.dumps(new_location)

        return [
            f'{indent}runner.execute_command("moveLabware", {{',
            f'{indent}    "labwareId": runner.labware_ids["{labware_var}"],',
            f'{indent}    "newLocation": {new_loc_str},',
            f'{indent}    "strategy": "{strategy}",',
            f"{indent}}})",
        ]

    def _generate_configure_for_volume(self, cmd: ProtocolCommand) -> list[str]:
        """Generate configure for volume code."""
        indent = self._indent
        pipette_var = cmd.pipette_var or "pipette"
        volume = cmd.params.get("volume", 0)

        return [
            f'{indent}runner.execute_command("configureForVolume", {{',
            f'{indent}    "pipetteId": runner.pipette_ids["{pipette_var}"],',
            f'{indent}    "volume": {volume},',
            f"{indent}}})",
        ]

    def _generate_configure_nozzle_layout(self, cmd: ProtocolCommand) -> list[str]:
        """Generate configure nozzle layout code."""
        indent = self._indent
        pipette_var = cmd.pipette_var or "pipette"

        config_params = {}
        if cmd.params.get("style"):
            config_params["style"] = cmd.params["style"]
        if cmd.params.get("start"):
            config_params["primaryNozzle"] = cmd.params["start"]
        if cmd.params.get("end"):
            config_params["backLeftNozzle"] = cmd.params["end"]
        if cmd.params.get("frontRight"):
            config_params["frontRightNozzle"] = cmd.params["frontRight"]
        if cmd.params.get("backLeft"):
            config_params["backLeftNozzle"] = cmd.params["backLeft"]

        config_str = json.dumps(config_params)

        return [
            f'{indent}runner.execute_command("configureNozzleLayout", {{',
            f'{indent}    "pipetteId": runner.pipette_ids["{pipette_var}"],',
            f'{indent}    "configurationParams": {config_str},',
            f"{indent}}})",
        ]

    def _generate_temp_module_command(self, cmd: ProtocolCommand) -> list[str]:
        """Generate temperature module command code."""
        indent = self._indent
        module_var = cmd.module_var or "temp_module"
        cmd_type = cmd.command_type.value

        params = dict(cmd.params)
        params_str = json.dumps(params) if params else "{}"

        return [
            f'{indent}runner.execute_command("{cmd_type}", {{',
            f'{indent}    "moduleId": runner.module_ids["{module_var}"],',
            f'{indent}    **{params_str}',
            f"{indent}}})",
        ]

    def _generate_thermocycler_command(self, cmd: ProtocolCommand) -> list[str]:
        """Generate thermocycler command code."""
        indent = self._indent
        module_var = cmd.module_var or "thermocycler"
        cmd_type = cmd.command_type.value

        params = dict(cmd.params)
        params_str = json.dumps(params, indent=8) if params else "{}"

        return [
            f'{indent}runner.execute_command("{cmd_type}", {{',
            f'{indent}    "moduleId": runner.module_ids["{module_var}"],',
            f'{indent}    **{params_str}',
            f"{indent}}})",
        ]

    def _generate_heater_shaker_command(self, cmd: ProtocolCommand) -> list[str]:
        """Generate heater-shaker command code."""
        indent = self._indent
        module_var = cmd.module_var or "heater_shaker"
        cmd_type = cmd.command_type.value

        params = dict(cmd.params)
        params_str = json.dumps(params) if params else "{}"

        return [
            f'{indent}runner.execute_command("{cmd_type}", {{',
            f'{indent}    "moduleId": runner.module_ids["{module_var}"],',
            f'{indent}    **{params_str}',
            f"{indent}}})",
        ]

    def _generate_magnetic_module_command(self, cmd: ProtocolCommand) -> list[str]:
        """Generate magnetic module command code."""
        indent = self._indent
        module_var = cmd.module_var or "mag_module"
        cmd_type = cmd.command_type.value

        params = dict(cmd.params)
        params_str = json.dumps(params) if params else "{}"

        return [
            f'{indent}runner.execute_command("{cmd_type}", {{',
            f'{indent}    "moduleId": runner.module_ids["{module_var}"],',
            f'{indent}    **{params_str}',
            f"{indent}}})",
        ]

    def _generate_absorbance_reader_command(self, cmd: ProtocolCommand) -> list[str]:
        """Generate absorbance reader command code."""
        indent = self._indent
        module_var = cmd.module_var or "abs_reader"
        cmd_type = cmd.command_type.value

        params = dict(cmd.params)
        params_str = json.dumps(params, indent=8) if params else "{}"

        return [
            f'{indent}runner.execute_command("{cmd_type}", {{',
            f'{indent}    "moduleId": runner.module_ids["{module_var}"],',
            f'{indent}    **{params_str}',
            f"{indent}}})",
        ]

    def _generate_flex_stacker_command(self, cmd: ProtocolCommand) -> list[str]:
        """Generate flex stacker command code."""
        indent = self._indent
        module_var = cmd.module_var or "stacker"
        cmd_type = cmd.command_type.value

        return [
            f'{indent}runner.execute_command("{cmd_type}", {{',
            f'{indent}    "moduleId": runner.module_ids["{module_var}"],',
            f"{indent}}})",
        ]

    def _generate_generic_command(self, cmd: ProtocolCommand) -> list[str]:
        """Generate code for a generic command."""
        indent = self._indent
        cmd_type = cmd.command_type.value

        params = dict(cmd.params)

        # Add resource IDs
        if cmd.pipette_var:
            params["pipetteId"] = f'runner.pipette_ids["{cmd.pipette_var}"]'
        if cmd.labware_var:
            params["labwareId"] = f'runner.labware_ids["{cmd.labware_var}"]'
        if cmd.module_var:
            params["moduleId"] = f'runner.module_ids["{cmd.module_var}"]'
        if cmd.well_name:
            params["wellName"] = cmd.well_name

        params_str = json.dumps(params, indent=8)
        # Unescape the runner lookups
        params_str = params_str.replace(
            '"runner.pipette_ids', "runner.pipette_ids"
        ).replace('"]"', '"]')
        params_str = params_str.replace(
            '"runner.labware_ids', "runner.labware_ids"
        ).replace('"]"', '"]')
        params_str = params_str.replace(
            '"runner.module_ids', "runner.module_ids"
        ).replace('"]"', '"]')

        return [f'{indent}runner.execute_command("{cmd_type}", {params_str})']

    def _replace_id_placeholders(self, params_str: str) -> str:
        """Replace placeholder IDs with runtime lookups."""
        # This handles the case where the command mapper has used variable names
        # that need to be converted to runtime ID lookups
        for var_name in self.protocol.labware_id_map:
            params_str = params_str.replace(
                f'"{var_name}"', f'runner.labware_ids["{var_name}"]'
            )
        for var_name in self.protocol.pipette_id_map:
            params_str = params_str.replace(
                f'"{var_name}"', f'runner.pipette_ids["{var_name}"]'
            )
        for var_name in self.protocol.module_id_map:
            params_str = params_str.replace(
                f'"{var_name}"', f'runner.module_ids["{var_name}"]'
            )
        return params_str
