"""
AST-based parser for Opentrons Python API protocols.

This parser uses Python's AST module to analyze protocol source code
and extract the structure needed for HTTP API translation.
"""

import ast
import re
from pathlib import Path
from typing import Any, Optional

from .protocol_model import (
    ParsedProtocol,
    ProtocolMetadata,
    ProtocolCommand,
    LoadedLabware,
    LoadedPipette,
    LoadedModule,
    DefinedLiquid,
    RuntimeParameter,
    CommandType,
    ModuleType,
    PipetteMount,
    RobotType,
    DeckLocation,
    WellLocation,
)


class ProtocolParser:
    """
    Parser for Opentrons Python API protocols.

    Parses protocol source code and extracts:
    - Metadata and requirements
    - Loaded labware, pipettes, and modules
    - Protocol commands in execution order
    - Runtime parameters
    """

    # Map Python API module names to ModuleType enum
    MODULE_TYPE_MAP = {
        "temperature module": ModuleType.TEMPERATURE,
        "temperature module gen2": ModuleType.TEMPERATURE,
        "temperatureModuleV1": ModuleType.TEMPERATURE_V1,
        "temperatureModuleV2": ModuleType.TEMPERATURE,
        "thermocycler": ModuleType.THERMOCYCLER,
        "thermocycler module": ModuleType.THERMOCYCLER,
        "thermocycler module gen2": ModuleType.THERMOCYCLER,
        "thermocyclerModuleV1": ModuleType.THERMOCYCLER_V1,
        "thermocyclerModuleV2": ModuleType.THERMOCYCLER,
        "heater-shaker": ModuleType.HEATER_SHAKER,
        "heaterShakerModuleV1": ModuleType.HEATER_SHAKER,
        "magnetic module": ModuleType.MAGNETIC_MODULE,
        "magnetic module gen2": ModuleType.MAGNETIC_MODULE,
        "magneticModuleV1": ModuleType.MAGNETIC_MODULE_V1,
        "magneticModuleV2": ModuleType.MAGNETIC_MODULE,
        "magnetic block": ModuleType.MAGNETIC_BLOCK,
        "magneticBlockV1": ModuleType.MAGNETIC_BLOCK,
        "absorbance plate reader": ModuleType.ABSORBANCE_READER,
        "absorbanceReaderV1": ModuleType.ABSORBANCE_READER,
        "flex stacker": ModuleType.FLEX_STACKER,
        "flexStackerModuleV1": ModuleType.FLEX_STACKER,
    }

    # Map Python API method names to CommandType
    PIPETTE_METHOD_MAP = {
        "pick_up_tip": CommandType.PICK_UP_TIP,
        "drop_tip": CommandType.DROP_TIP,
        "return_tip": CommandType.DROP_TIP,  # Returns to original location
        "aspirate": CommandType.ASPIRATE,
        "dispense": CommandType.DISPENSE,
        "blow_out": CommandType.BLOW_OUT,
        "touch_tip": CommandType.TOUCH_TIP,
        "air_gap": CommandType.AIR_GAP,
        "mix": CommandType.MIX,
        "transfer": CommandType.TRANSFER,
        "distribute": CommandType.DISTRIBUTE,
        "consolidate": CommandType.CONSOLIDATE,
        "move_to": CommandType.MOVE_TO_WELL,
        "home": CommandType.HOME,
        "home_plunger": CommandType.HOME,
        "prepare_to_aspirate": CommandType.PREPARE_TO_ASPIRATE,
        "configure_for_volume": CommandType.CONFIGURE_FOR_VOLUME,
        "configure_nozzle_layout": CommandType.CONFIGURE_NOZZLE_LAYOUT,
    }

    CONTEXT_METHOD_MAP = {
        "load_labware": CommandType.LOAD_LABWARE,
        "load_labware_from_definition": CommandType.LOAD_LABWARE,
        "load_adapter": CommandType.LOAD_ADAPTER,
        "load_adapter_from_definition": CommandType.LOAD_ADAPTER,
        "load_instrument": CommandType.LOAD_PIPETTE,
        "load_module": CommandType.LOAD_MODULE,
        "load_trash_bin": CommandType.LOAD_TRASH_BIN,
        "load_waste_chute": CommandType.LOAD_WASTE_CHUTE,
        "move_labware": CommandType.MOVE_LABWARE,
        "load_lid_stack": CommandType.LOAD_LID_STACK,
        "move_lid": CommandType.MOVE_LID,
        "define_liquid": CommandType.DEFINE_LIQUID,
        "home": CommandType.HOME,
        "pause": CommandType.PAUSE,
        "delay": CommandType.DELAY,
        "comment": CommandType.COMMENT,
        "set_rail_lights": CommandType.SET_RAIL_LIGHTS,
    }

    TEMP_MODULE_METHOD_MAP = {
        "set_temperature": CommandType.TEMP_SET_TEMPERATURE,
        "start_set_temperature": CommandType.TEMP_SET_TEMPERATURE,
        "await_temperature": CommandType.TEMP_WAIT_FOR_TEMPERATURE,
        "wait_for_temperature": CommandType.TEMP_WAIT_FOR_TEMPERATURE,
        "deactivate": CommandType.TEMP_DEACTIVATE,
    }

    TC_METHOD_MAP = {
        "open_lid": CommandType.TC_OPEN_LID,
        "close_lid": CommandType.TC_CLOSE_LID,
        "set_block_temperature": CommandType.TC_SET_TARGET_BLOCK_TEMPERATURE,
        "set_lid_temperature": CommandType.TC_SET_TARGET_LID_TEMPERATURE,
        "wait_for_block_temperature": CommandType.TC_WAIT_FOR_BLOCK_TEMPERATURE,
        "wait_for_lid_temperature": CommandType.TC_WAIT_FOR_LID_TEMPERATURE,
        "execute_profile": CommandType.TC_RUN_PROFILE,
        "run_profile": CommandType.TC_RUN_PROFILE,
        "deactivate_lid": CommandType.TC_DEACTIVATE_LID,
        "deactivate_block": CommandType.TC_DEACTIVATE_BLOCK,
        "deactivate": CommandType.TC_DEACTIVATE_BLOCK,
    }

    HS_METHOD_MAP = {
        "set_target_temperature": CommandType.HS_SET_TARGET_TEMPERATURE,
        "wait_for_temperature": CommandType.HS_WAIT_FOR_TEMPERATURE,
        "set_and_wait_for_shake_speed": CommandType.HS_SET_AND_WAIT_FOR_SHAKE_SPEED,
        "deactivate_heater": CommandType.HS_DEACTIVATE_HEATER,
        "deactivate_shaker": CommandType.HS_DEACTIVATE_SHAKER,
        "open_labware_latch": CommandType.HS_OPEN_LABWARE_LATCH,
        "close_labware_latch": CommandType.HS_CLOSE_LABWARE_LATCH,
    }

    MAG_METHOD_MAP = {
        "engage": CommandType.MAG_ENGAGE,
        "disengage": CommandType.MAG_DISENGAGE,
    }

    ABS_METHOD_MAP = {
        "initialize": CommandType.ABS_INITIALIZE,
        "open_lid": CommandType.ABS_OPEN_LID,
        "close_lid": CommandType.ABS_CLOSE_LID,
        "read": CommandType.ABS_READ,
    }

    STACKER_METHOD_MAP = {
        "store": CommandType.STACKER_STORE,
        "retrieve": CommandType.STACKER_RETRIEVE,
    }

    def __init__(self) -> None:
        self._source_lines: list[str] = []
        self._variables: dict[str, Any] = {}  # Track variable assignments
        self._protocol_context_var: Optional[str] = None
        self._parsed: Optional[ParsedProtocol] = None

    def parse_file(self, file_path: str | Path) -> ParsedProtocol:
        """Parse a protocol file."""
        file_path = Path(file_path)
        source_code = file_path.read_text()
        return self.parse_source(source_code, str(file_path))

    def parse_source(self, source_code: str, source_file: Optional[str] = None) -> ParsedProtocol:
        """Parse protocol source code."""
        self._source_lines = source_code.splitlines()
        self._variables = {}
        self._protocol_context_var = None

        tree = ast.parse(source_code)

        self._parsed = ParsedProtocol(
            metadata=ProtocolMetadata(),
            source_file=source_file,
            source_code=source_code,
        )

        # First pass: extract metadata, requirements, and find run function
        self._extract_module_level(tree)

        # Second pass: parse run function body
        run_func = self._find_run_function(tree)
        if run_func:
            self._parse_run_function(run_func)

        # Also look for add_parameters function
        params_func = self._find_add_parameters_function(tree)
        if params_func:
            self._parse_parameters_function(params_func)

        return self._parsed

    def _extract_module_level(self, tree: ast.Module) -> None:
        """Extract module-level metadata and requirements."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if target.id == "metadata":
                            self._parse_metadata(node.value)
                        elif target.id == "requirements":
                            self._parse_requirements(node.value)

    def _parse_metadata(self, node: ast.expr) -> None:
        """Parse metadata dictionary."""
        if isinstance(node, ast.Dict):
            metadata_dict = self._eval_dict(node)
            self._parsed.metadata.protocol_name = metadata_dict.get("protocolName")
            self._parsed.metadata.author = metadata_dict.get("author")
            self._parsed.metadata.description = metadata_dict.get("description")
            self._parsed.metadata.api_level = metadata_dict.get("apiLevel", "2.19")

    def _parse_requirements(self, node: ast.expr) -> None:
        """Parse requirements dictionary."""
        if isinstance(node, ast.Dict):
            req_dict = self._eval_dict(node)
            self._parsed.requirements = req_dict

            # Extract robot type
            robot_type = req_dict.get("robotType", "OT-3 Standard")
            if "OT-3" in robot_type or "Flex" in robot_type.lower():
                self._parsed.metadata.robot_type = RobotType.FLEX
            else:
                self._parsed.metadata.robot_type = RobotType.OT2

    def _eval_dict(self, node: ast.Dict) -> dict[str, Any]:
        """Safely evaluate a dictionary literal."""
        result = {}
        for key, value in zip(node.keys, node.values):
            if key is not None and isinstance(key, ast.Constant):
                result[key.value] = self._eval_value(value)
        return result

    def _eval_value(self, node: ast.expr) -> Any:
        """Safely evaluate a literal value."""
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.List):
            return [self._eval_value(elt) for elt in node.elts]
        elif isinstance(node, ast.Dict):
            return self._eval_dict(node)
        elif isinstance(node, ast.Tuple):
            return tuple(self._eval_value(elt) for elt in node.elts)
        elif isinstance(node, ast.Name):
            # Could be True, False, None, or a variable reference
            if node.id in ("True", "False", "None"):
                return {"True": True, "False": False, "None": None}[node.id]
            return f"${node.id}"  # Mark as variable reference
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -self._eval_value(node.operand)
        elif isinstance(node, ast.BinOp):
            # Handle simple arithmetic
            left = self._eval_value(node.left)
            right = self._eval_value(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            elif isinstance(node.op, ast.Sub):
                return left - right
            elif isinstance(node.op, ast.Mult):
                return left * right
            elif isinstance(node.op, ast.Div):
                return left / right
        elif isinstance(node, ast.Attribute):
            # Handle attribute access like Mount.LEFT
            if isinstance(node.value, ast.Name):
                return f"${node.value.id}.{node.attr}"
        return None

    def _find_run_function(self, tree: ast.Module) -> Optional[ast.FunctionDef]:
        """Find the run function in the protocol."""
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == "run":
                return node
        return None

    def _find_add_parameters_function(self, tree: ast.Module) -> Optional[ast.FunctionDef]:
        """Find the add_parameters function if present."""
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == "add_parameters":
                return node
        return None

    def _parse_run_function(self, func: ast.FunctionDef) -> None:
        """Parse the run function body."""
        # Find the protocol context parameter name
        if func.args.args:
            self._protocol_context_var = func.args.args[0].arg

        # Process each statement in the function body
        for stmt in func.body:
            self._parse_statement(stmt)

    def _parse_statement(self, stmt: ast.stmt) -> None:
        """Parse a statement in the run function."""
        if isinstance(stmt, ast.Assign):
            self._parse_assignment(stmt)
        elif isinstance(stmt, ast.Expr):
            if isinstance(stmt.value, ast.Call):
                self._parse_call(stmt.value, stmt.lineno)
        elif isinstance(stmt, ast.For):
            self._parse_for_loop(stmt)
        elif isinstance(stmt, ast.If):
            self._parse_if_statement(stmt)
        elif isinstance(stmt, ast.With):
            self._parse_with_statement(stmt)
        elif isinstance(stmt, ast.AugAssign):
            # Handle things like volume += 10
            pass

    def _parse_assignment(self, stmt: ast.Assign) -> None:
        """Parse an assignment statement."""
        if len(stmt.targets) != 1:
            return

        target = stmt.targets[0]
        if not isinstance(target, ast.Name):
            return

        var_name = target.id
        value = stmt.value

        if isinstance(value, ast.Call):
            # Check if it's a protocol context method call
            call_info = self._get_call_info(value)
            if call_info:
                obj_var, method_name, args, kwargs = call_info
                self._handle_method_call(
                    var_name, obj_var, method_name, args, kwargs, stmt.lineno
                )
        elif isinstance(value, ast.Subscript):
            # Handle well access like plate["A1"]
            self._variables[var_name] = ("well_ref", value)

    def _parse_call(self, call: ast.Call, lineno: int) -> None:
        """Parse a standalone method call (no assignment)."""
        call_info = self._get_call_info(call)
        if call_info:
            obj_var, method_name, args, kwargs = call_info
            self._handle_method_call(None, obj_var, method_name, args, kwargs, lineno)

    def _get_call_info(
        self, call: ast.Call
    ) -> Optional[tuple[Optional[str], str, list[Any], dict[str, Any]]]:
        """Extract call information from an AST Call node."""
        if isinstance(call.func, ast.Attribute):
            # Method call like pipette.aspirate()
            if isinstance(call.func.value, ast.Name):
                obj_var = call.func.value.id
            elif isinstance(call.func.value, ast.Subscript):
                # Handle chained access like plate["A1"].top()
                obj_var = self._get_subscript_var(call.func.value)
            elif isinstance(call.func.value, ast.Attribute):
                # Handle chained attribute access
                obj_var = self._get_chained_attr(call.func.value)
            elif isinstance(call.func.value, ast.Call):
                # Handle chained calls like plate.wells()[0]
                obj_var = None
            else:
                return None

            method_name = call.func.attr
            args = [self._eval_value(arg) for arg in call.args]
            kwargs = {kw.arg: self._eval_value(kw.value) for kw in call.keywords if kw.arg}
            return obj_var, method_name, args, kwargs

        elif isinstance(call.func, ast.Name):
            # Direct function call
            return None, call.func.id, [], {}

        return None

    def _get_subscript_var(self, node: ast.Subscript) -> str:
        """Get variable name from subscript like plate["A1"]."""
        if isinstance(node.value, ast.Name):
            well = self._eval_value(node.slice)
            return f"{node.value.id}[{well}]"
        return "unknown"

    def _get_chained_attr(self, node: ast.Attribute) -> str:
        """Get chained attribute access like module.labware."""
        parts = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return ".".join(reversed(parts))

    def _handle_method_call(
        self,
        var_name: Optional[str],
        obj_var: Optional[str],
        method_name: str,
        args: list[Any],
        kwargs: dict[str, Any],
        lineno: int,
    ) -> None:
        """Handle a method call and create appropriate commands/resources."""
        source_code = self._source_lines[lineno - 1] if lineno <= len(self._source_lines) else ""

        # Check if it's a protocol context method
        if obj_var == self._protocol_context_var:
            self._handle_context_method(var_name, method_name, args, kwargs, lineno, source_code)
        # Check if it's a pipette method
        elif obj_var and self._is_pipette_var(obj_var):
            self._handle_pipette_method(obj_var, method_name, args, kwargs, lineno, source_code)
        # Check if it's a module method
        elif obj_var and self._is_module_var(obj_var):
            self._handle_module_method(obj_var, method_name, args, kwargs, lineno, source_code)
        # Check if it's a labware method (like load_liquid)
        elif obj_var and self._is_labware_var(obj_var):
            self._handle_labware_method(
                var_name, obj_var, method_name, args, kwargs, lineno, source_code
            )
        # Check for well methods
        elif obj_var and "[" in obj_var:
            self._handle_well_method(obj_var, method_name, args, kwargs, lineno, source_code)

    def _is_pipette_var(self, var_name: str) -> bool:
        """Check if a variable refers to a pipette."""
        return any(p.variable_name == var_name for p in self._parsed.pipettes)

    def _is_module_var(self, var_name: str) -> bool:
        """Check if a variable refers to a module."""
        base_var = var_name.split(".")[0]
        return any(m.variable_name == base_var for m in self._parsed.modules)

    def _is_labware_var(self, var_name: str) -> bool:
        """Check if a variable refers to labware."""
        base_var = var_name.split("[")[0]
        return any(lw.variable_name == base_var for lw in self._parsed.labware)

    def _handle_context_method(
        self,
        var_name: Optional[str],
        method_name: str,
        args: list[Any],
        kwargs: dict[str, Any],
        lineno: int,
        source_code: str,
    ) -> None:
        """Handle a ProtocolContext method call."""
        if method_name == "load_labware":
            self._handle_load_labware(var_name, args, kwargs, lineno, source_code)
        elif method_name == "load_adapter":
            self._handle_load_adapter(var_name, args, kwargs, lineno, source_code)
        elif method_name == "load_instrument":
            self._handle_load_instrument(var_name, args, kwargs, lineno, source_code)
        elif method_name == "load_module":
            self._handle_load_module(var_name, args, kwargs, lineno, source_code)
        elif method_name == "load_trash_bin":
            self._handle_load_trash_bin(var_name, args, kwargs, lineno, source_code)
        elif method_name == "load_waste_chute":
            self._handle_load_waste_chute(var_name, args, kwargs, lineno, source_code)
        elif method_name == "define_liquid":
            self._handle_define_liquid(var_name, args, kwargs, lineno, source_code)
        elif method_name == "move_labware":
            self._handle_move_labware(args, kwargs, lineno, source_code)
        elif method_name == "home":
            self._add_command(CommandType.HOME, {}, lineno, source_code)
        elif method_name == "pause":
            msg = args[0] if args else kwargs.get("msg", "")
            self._add_command(CommandType.PAUSE, {"message": msg}, lineno, source_code)
        elif method_name == "delay":
            seconds = kwargs.get("seconds", args[0] if args else 0)
            minutes = kwargs.get("minutes", args[1] if len(args) > 1 else 0)
            total_seconds = float(seconds) + float(minutes) * 60
            self._add_command(
                CommandType.DELAY, {"seconds": total_seconds}, lineno, source_code
            )
        elif method_name == "comment":
            msg = args[0] if args else kwargs.get("msg", "")
            self._add_command(CommandType.COMMENT, {"message": msg}, lineno, source_code)
        elif method_name == "set_rail_lights":
            on = args[0] if args else kwargs.get("on", True)
            self._add_command(CommandType.SET_RAIL_LIGHTS, {"on": on}, lineno, source_code)

    def _handle_load_labware(
        self,
        var_name: Optional[str],
        args: list[Any],
        kwargs: dict[str, Any],
        lineno: int,
        source_code: str,
    ) -> None:
        """Handle load_labware call."""
        load_name = args[0] if args else kwargs.get("load_name")
        location = args[1] if len(args) > 1 else kwargs.get("location")
        label = kwargs.get("label")
        namespace = kwargs.get("namespace", "opentrons")
        version = kwargs.get("version", 1)
        adapter = kwargs.get("adapter")

        deck_location = self._parse_location(location)
        if adapter:
            deck_location.adapter_id = f"${adapter}" if isinstance(adapter, str) else None

        labware = LoadedLabware(
            variable_name=var_name or f"labware_{len(self._parsed.labware)}",
            load_name=load_name,
            location=deck_location,
            label=label,
            namespace=namespace,
            version=version if isinstance(version, int) else 1,
        )
        self._parsed.labware.append(labware)

        # Also add as command
        self._add_command(
            CommandType.LOAD_LABWARE,
            {
                "loadName": load_name,
                "location": location,
                "label": label,
                "namespace": namespace,
                "version": version,
            },
            lineno,
            source_code,
            labware_var=var_name,
        )

    def _handle_load_adapter(
        self,
        var_name: Optional[str],
        args: list[Any],
        kwargs: dict[str, Any],
        lineno: int,
        source_code: str,
    ) -> None:
        """Handle load_adapter call."""
        load_name = args[0] if args else kwargs.get("load_name")
        location = args[1] if len(args) > 1 else kwargs.get("location")

        deck_location = self._parse_location(location)

        labware = LoadedLabware(
            variable_name=var_name or f"adapter_{len(self._parsed.labware)}",
            load_name=load_name,
            location=deck_location,
        )
        self._parsed.labware.append(labware)

        self._add_command(
            CommandType.LOAD_ADAPTER,
            {"loadName": load_name, "location": location},
            lineno,
            source_code,
            labware_var=var_name,
        )

    def _handle_load_instrument(
        self,
        var_name: Optional[str],
        args: list[Any],
        kwargs: dict[str, Any],
        lineno: int,
        source_code: str,
    ) -> None:
        """Handle load_instrument call."""
        instrument_name = args[0] if args else kwargs.get("instrument_name")
        mount = args[1] if len(args) > 1 else kwargs.get("mount")
        tip_racks = kwargs.get("tip_racks", [])
        liquid_presence_detection = kwargs.get("liquid_presence_detection", False)

        # Convert mount string to enum
        if isinstance(mount, str):
            if "left" in mount.lower():
                mount_enum = PipetteMount.LEFT
            elif "right" in mount.lower():
                mount_enum = PipetteMount.RIGHT
            else:
                mount_enum = PipetteMount.LEFT
        else:
            mount_enum = PipetteMount.LEFT

        # Handle tip rack references
        tip_rack_vars = []
        if isinstance(tip_racks, list):
            for tr in tip_racks:
                if isinstance(tr, str) and tr.startswith("$"):
                    tip_rack_vars.append(tr[1:])

        pipette = LoadedPipette(
            variable_name=var_name or f"pipette_{len(self._parsed.pipettes)}",
            instrument_name=instrument_name,
            mount=mount_enum,
            tip_racks=tip_rack_vars,
            liquid_presence_detection=bool(liquid_presence_detection),
        )
        self._parsed.pipettes.append(pipette)

        self._add_command(
            CommandType.LOAD_PIPETTE,
            {
                "instrumentName": instrument_name,
                "mount": mount_enum.value,
                "tipRacks": tip_rack_vars,
            },
            lineno,
            source_code,
            pipette_var=var_name,
        )

    def _handle_load_module(
        self,
        var_name: Optional[str],
        args: list[Any],
        kwargs: dict[str, Any],
        lineno: int,
        source_code: str,
    ) -> None:
        """Handle load_module call."""
        module_name = args[0] if args else kwargs.get("module_name")
        location = args[1] if len(args) > 1 else kwargs.get("location")
        configuration = kwargs.get("configuration")

        module_type = self.MODULE_TYPE_MAP.get(
            module_name.lower() if module_name else "", ModuleType.TEMPERATURE
        )

        module = LoadedModule(
            variable_name=var_name or f"module_{len(self._parsed.modules)}",
            module_type=module_type,
            location=str(location) if location else "",
            configuration=configuration,
        )
        self._parsed.modules.append(module)

        self._add_command(
            CommandType.LOAD_MODULE,
            {
                "moduleModel": module_type.value,
                "location": {"slotName": str(location)},
            },
            lineno,
            source_code,
            module_var=var_name,
        )

    def _handle_load_trash_bin(
        self,
        var_name: Optional[str],
        args: list[Any],
        kwargs: dict[str, Any],
        lineno: int,
        source_code: str,
    ) -> None:
        """Handle load_trash_bin call."""
        location = args[0] if args else kwargs.get("location")

        self._add_command(
            CommandType.LOAD_TRASH_BIN,
            {"location": {"slotName": str(location)}},
            lineno,
            source_code,
        )

    def _handle_load_waste_chute(
        self,
        var_name: Optional[str],
        args: list[Any],
        kwargs: dict[str, Any],
        lineno: int,
        source_code: str,
    ) -> None:
        """Handle load_waste_chute call."""
        self._add_command(
            CommandType.LOAD_WASTE_CHUTE,
            {},
            lineno,
            source_code,
        )

    def _handle_define_liquid(
        self,
        var_name: Optional[str],
        args: list[Any],
        kwargs: dict[str, Any],
        lineno: int,
        source_code: str,
    ) -> None:
        """Handle define_liquid call."""
        name = args[0] if args else kwargs.get("name")
        description = kwargs.get("description")
        display_color = kwargs.get("display_color")

        liquid = DefinedLiquid(
            variable_name=var_name or f"liquid_{len(self._parsed.liquids)}",
            name=name,
            description=description,
            display_color=display_color,
        )
        self._parsed.liquids.append(liquid)

    def _handle_move_labware(
        self,
        args: list[Any],
        kwargs: dict[str, Any],
        lineno: int,
        source_code: str,
    ) -> None:
        """Handle move_labware call."""
        labware = args[0] if args else kwargs.get("labware")
        new_location = args[1] if len(args) > 1 else kwargs.get("new_location")
        use_gripper = kwargs.get("use_gripper", False)

        self._add_command(
            CommandType.MOVE_LABWARE,
            {
                "labwareId": f"${labware}" if isinstance(labware, str) else None,
                "newLocation": new_location,
                "strategy": "usingGripper" if use_gripper else "manualMoveWithPause",
            },
            lineno,
            source_code,
            labware_var=labware if isinstance(labware, str) else None,
        )

    def _handle_pipette_method(
        self,
        pipette_var: str,
        method_name: str,
        args: list[Any],
        kwargs: dict[str, Any],
        lineno: int,
        source_code: str,
    ) -> None:
        """Handle a pipette method call."""
        if method_name == "pick_up_tip":
            self._handle_pick_up_tip(pipette_var, args, kwargs, lineno, source_code)
        elif method_name == "drop_tip":
            self._handle_drop_tip(pipette_var, args, kwargs, lineno, source_code)
        elif method_name == "return_tip":
            self._handle_return_tip(pipette_var, args, kwargs, lineno, source_code)
        elif method_name == "aspirate":
            self._handle_aspirate(pipette_var, args, kwargs, lineno, source_code)
        elif method_name == "dispense":
            self._handle_dispense(pipette_var, args, kwargs, lineno, source_code)
        elif method_name == "blow_out":
            self._handle_blow_out(pipette_var, args, kwargs, lineno, source_code)
        elif method_name == "touch_tip":
            self._handle_touch_tip(pipette_var, args, kwargs, lineno, source_code)
        elif method_name == "air_gap":
            self._handle_air_gap(pipette_var, args, kwargs, lineno, source_code)
        elif method_name == "mix":
            self._handle_mix(pipette_var, args, kwargs, lineno, source_code)
        elif method_name == "transfer":
            self._handle_transfer(pipette_var, args, kwargs, lineno, source_code)
        elif method_name == "distribute":
            self._handle_distribute(pipette_var, args, kwargs, lineno, source_code)
        elif method_name == "consolidate":
            self._handle_consolidate(pipette_var, args, kwargs, lineno, source_code)
        elif method_name == "move_to":
            self._handle_move_to(pipette_var, args, kwargs, lineno, source_code)
        elif method_name == "home":
            self._add_command(CommandType.HOME, {}, lineno, source_code, pipette_var=pipette_var)
        elif method_name == "configure_for_volume":
            volume = args[0] if args else kwargs.get("volume")
            self._add_command(
                CommandType.CONFIGURE_FOR_VOLUME,
                {"volume": volume},
                lineno,
                source_code,
                pipette_var=pipette_var,
            )
        elif method_name == "configure_nozzle_layout":
            style = kwargs.get("style")
            start = kwargs.get("start")
            end = kwargs.get("end")
            front_right = kwargs.get("front_right")
            back_left = kwargs.get("back_left")
            self._add_command(
                CommandType.CONFIGURE_NOZZLE_LAYOUT,
                {
                    "style": style,
                    "start": start,
                    "end": end,
                    "frontRight": front_right,
                    "backLeft": back_left,
                },
                lineno,
                source_code,
                pipette_var=pipette_var,
            )

    def _handle_pick_up_tip(
        self,
        pipette_var: str,
        args: list[Any],
        kwargs: dict[str, Any],
        lineno: int,
        source_code: str,
    ) -> None:
        """Handle pick_up_tip call."""
        location = args[0] if args else kwargs.get("location")
        presses = kwargs.get("presses")
        increment = kwargs.get("increment")

        params = {}
        if presses is not None:
            params["presses"] = presses
        if increment is not None:
            params["increment"] = increment

        labware_var, well_name = self._parse_well_location(location)

        self._add_command(
            CommandType.PICK_UP_TIP,
            params,
            lineno,
            source_code,
            pipette_var=pipette_var,
            labware_var=labware_var,
            well_name=well_name,
        )

    def _handle_drop_tip(
        self,
        pipette_var: str,
        args: list[Any],
        kwargs: dict[str, Any],
        lineno: int,
        source_code: str,
    ) -> None:
        """Handle drop_tip call."""
        location = args[0] if args else kwargs.get("location")
        home_after = kwargs.get("home_after")

        params = {}
        if home_after is not None:
            params["homeAfter"] = home_after

        if location:
            labware_var, well_name = self._parse_well_location(location)
            self._add_command(
                CommandType.DROP_TIP,
                params,
                lineno,
                source_code,
                pipette_var=pipette_var,
                labware_var=labware_var,
                well_name=well_name,
            )
        else:
            self._add_command(
                CommandType.DROP_TIP_IN_PLACE,
                params,
                lineno,
                source_code,
                pipette_var=pipette_var,
            )

    def _handle_return_tip(
        self,
        pipette_var: str,
        args: list[Any],
        kwargs: dict[str, Any],
        lineno: int,
        source_code: str,
    ) -> None:
        """Handle return_tip call (drops tip to original location)."""
        self._add_command(
            CommandType.DROP_TIP,
            {"returnToOrigin": True},
            lineno,
            source_code,
            pipette_var=pipette_var,
        )

    def _handle_aspirate(
        self,
        pipette_var: str,
        args: list[Any],
        kwargs: dict[str, Any],
        lineno: int,
        source_code: str,
    ) -> None:
        """Handle aspirate call."""
        volume = args[0] if args else kwargs.get("volume")
        location = args[1] if len(args) > 1 else kwargs.get("location")
        rate = kwargs.get("rate", 1.0)
        flow_rate = kwargs.get("flow_rate")

        params = {"volume": volume}
        if flow_rate:
            params["flowRate"] = flow_rate
        elif rate != 1.0:
            params["rate"] = rate

        labware_var, well_name = self._parse_well_location(location)
        well_location = self._parse_well_position(location)
        if well_location:
            params["wellLocation"] = well_location

        if location:
            self._add_command(
                CommandType.ASPIRATE,
                params,
                lineno,
                source_code,
                pipette_var=pipette_var,
                labware_var=labware_var,
                well_name=well_name,
            )
        else:
            self._add_command(
                CommandType.ASPIRATE_IN_PLACE,
                params,
                lineno,
                source_code,
                pipette_var=pipette_var,
            )

    def _handle_dispense(
        self,
        pipette_var: str,
        args: list[Any],
        kwargs: dict[str, Any],
        lineno: int,
        source_code: str,
    ) -> None:
        """Handle dispense call."""
        volume = args[0] if args else kwargs.get("volume")
        location = args[1] if len(args) > 1 else kwargs.get("location")
        rate = kwargs.get("rate", 1.0)
        flow_rate = kwargs.get("flow_rate")
        push_out = kwargs.get("push_out")

        params = {}
        if volume:
            params["volume"] = volume
        if flow_rate:
            params["flowRate"] = flow_rate
        elif rate != 1.0:
            params["rate"] = rate
        if push_out is not None:
            params["pushOut"] = push_out

        labware_var, well_name = self._parse_well_location(location)
        well_location = self._parse_well_position(location)
        if well_location:
            params["wellLocation"] = well_location

        if location:
            self._add_command(
                CommandType.DISPENSE,
                params,
                lineno,
                source_code,
                pipette_var=pipette_var,
                labware_var=labware_var,
                well_name=well_name,
            )
        else:
            self._add_command(
                CommandType.DISPENSE_IN_PLACE,
                params,
                lineno,
                source_code,
                pipette_var=pipette_var,
            )

    def _handle_blow_out(
        self,
        pipette_var: str,
        args: list[Any],
        kwargs: dict[str, Any],
        lineno: int,
        source_code: str,
    ) -> None:
        """Handle blow_out call."""
        location = args[0] if args else kwargs.get("location")

        labware_var, well_name = self._parse_well_location(location)

        if location:
            self._add_command(
                CommandType.BLOW_OUT,
                {},
                lineno,
                source_code,
                pipette_var=pipette_var,
                labware_var=labware_var,
                well_name=well_name,
            )
        else:
            self._add_command(
                CommandType.BLOW_OUT_IN_PLACE,
                {},
                lineno,
                source_code,
                pipette_var=pipette_var,
            )

    def _handle_touch_tip(
        self,
        pipette_var: str,
        args: list[Any],
        kwargs: dict[str, Any],
        lineno: int,
        source_code: str,
    ) -> None:
        """Handle touch_tip call."""
        location = args[0] if args else kwargs.get("location")
        radius = kwargs.get("radius", 1.0)
        v_offset = kwargs.get("v_offset", 0)
        speed = kwargs.get("speed")

        params = {"radius": radius}
        if v_offset:
            params["offset"] = {"z": v_offset}
        if speed:
            params["speed"] = speed

        labware_var, well_name = self._parse_well_location(location)

        self._add_command(
            CommandType.TOUCH_TIP,
            params,
            lineno,
            source_code,
            pipette_var=pipette_var,
            labware_var=labware_var,
            well_name=well_name,
        )

    def _handle_air_gap(
        self,
        pipette_var: str,
        args: list[Any],
        kwargs: dict[str, Any],
        lineno: int,
        source_code: str,
    ) -> None:
        """Handle air_gap call."""
        volume = args[0] if args else kwargs.get("volume")
        height = kwargs.get("height")

        params = {}
        if volume:
            params["volume"] = volume
        if height:
            params["height"] = height

        self._add_command(
            CommandType.AIR_GAP,
            params,
            lineno,
            source_code,
            pipette_var=pipette_var,
        )

    def _handle_mix(
        self,
        pipette_var: str,
        args: list[Any],
        kwargs: dict[str, Any],
        lineno: int,
        source_code: str,
    ) -> None:
        """Handle mix call - expands to multiple aspirate/dispense."""
        repetitions = args[0] if args else kwargs.get("repetitions", 1)
        volume = args[1] if len(args) > 1 else kwargs.get("volume")
        location = args[2] if len(args) > 2 else kwargs.get("location")
        rate = kwargs.get("rate", 1.0)

        labware_var, well_name = self._parse_well_location(location)

        # Create a mix command that will be expanded
        self._add_command(
            CommandType.MIX,
            {
                "repetitions": repetitions,
                "volume": volume,
                "rate": rate,
            },
            lineno,
            source_code,
            pipette_var=pipette_var,
            labware_var=labware_var,
            well_name=well_name,
        )

    def _handle_transfer(
        self,
        pipette_var: str,
        args: list[Any],
        kwargs: dict[str, Any],
        lineno: int,
        source_code: str,
    ) -> None:
        """Handle transfer call - complex command."""
        volume = args[0] if args else kwargs.get("volume")
        source = args[1] if len(args) > 1 else kwargs.get("source")
        dest = args[2] if len(args) > 2 else kwargs.get("dest")

        self._add_command(
            CommandType.TRANSFER,
            {
                "volume": volume,
                "source": source,
                "dest": dest,
                "new_tip": kwargs.get("new_tip", "once"),
                "trash": kwargs.get("trash", True),
                "touch_tip": kwargs.get("touch_tip", False),
                "blow_out": kwargs.get("blow_out", False),
                "mix_before": kwargs.get("mix_before"),
                "mix_after": kwargs.get("mix_after"),
                "air_gap": kwargs.get("air_gap", 0),
                "disposal_volume": kwargs.get("disposal_volume", 0),
            },
            lineno,
            source_code,
            pipette_var=pipette_var,
        )

    def _handle_distribute(
        self,
        pipette_var: str,
        args: list[Any],
        kwargs: dict[str, Any],
        lineno: int,
        source_code: str,
    ) -> None:
        """Handle distribute call - complex command."""
        volume = args[0] if args else kwargs.get("volume")
        source = args[1] if len(args) > 1 else kwargs.get("source")
        dest = args[2] if len(args) > 2 else kwargs.get("dest")

        self._add_command(
            CommandType.DISTRIBUTE,
            {
                "volume": volume,
                "source": source,
                "dest": dest,
                "new_tip": kwargs.get("new_tip", "once"),
                "trash": kwargs.get("trash", True),
                "touch_tip": kwargs.get("touch_tip", False),
                "blow_out": kwargs.get("blow_out", False),
                "air_gap": kwargs.get("air_gap", 0),
                "disposal_volume": kwargs.get("disposal_volume", 0),
            },
            lineno,
            source_code,
            pipette_var=pipette_var,
        )

    def _handle_consolidate(
        self,
        pipette_var: str,
        args: list[Any],
        kwargs: dict[str, Any],
        lineno: int,
        source_code: str,
    ) -> None:
        """Handle consolidate call - complex command."""
        volume = args[0] if args else kwargs.get("volume")
        source = args[1] if len(args) > 1 else kwargs.get("source")
        dest = args[2] if len(args) > 2 else kwargs.get("dest")

        self._add_command(
            CommandType.CONSOLIDATE,
            {
                "volume": volume,
                "source": source,
                "dest": dest,
                "new_tip": kwargs.get("new_tip", "once"),
                "trash": kwargs.get("trash", True),
                "touch_tip": kwargs.get("touch_tip", False),
                "blow_out": kwargs.get("blow_out", False),
                "air_gap": kwargs.get("air_gap", 0),
            },
            lineno,
            source_code,
            pipette_var=pipette_var,
        )

    def _handle_move_to(
        self,
        pipette_var: str,
        args: list[Any],
        kwargs: dict[str, Any],
        lineno: int,
        source_code: str,
    ) -> None:
        """Handle move_to call."""
        location = args[0] if args else kwargs.get("location")
        force_direct = kwargs.get("force_direct", False)
        minimum_z_height = kwargs.get("minimum_z_height")
        speed = kwargs.get("speed")

        params = {"forceDirect": force_direct}
        if minimum_z_height:
            params["minimumZHeight"] = minimum_z_height
        if speed:
            params["speed"] = speed

        labware_var, well_name = self._parse_well_location(location)

        self._add_command(
            CommandType.MOVE_TO_WELL,
            params,
            lineno,
            source_code,
            pipette_var=pipette_var,
            labware_var=labware_var,
            well_name=well_name,
        )

    def _handle_module_method(
        self,
        module_var: str,
        method_name: str,
        args: list[Any],
        kwargs: dict[str, Any],
        lineno: int,
        source_code: str,
    ) -> None:
        """Handle a module method call."""
        # Get the base module variable (before any .labware access)
        base_var = module_var.split(".")[0]
        module = self._parsed.get_module_by_var(base_var)
        if not module:
            return

        # Determine which module type and route to appropriate handler
        if module.module_type in (ModuleType.TEMPERATURE, ModuleType.TEMPERATURE_V1):
            self._handle_temp_module_method(
                base_var, method_name, args, kwargs, lineno, source_code
            )
        elif module.module_type in (ModuleType.THERMOCYCLER, ModuleType.THERMOCYCLER_V1):
            self._handle_thermocycler_method(
                base_var, method_name, args, kwargs, lineno, source_code
            )
        elif module.module_type == ModuleType.HEATER_SHAKER:
            self._handle_heater_shaker_method(
                base_var, method_name, args, kwargs, lineno, source_code
            )
        elif module.module_type in (
            ModuleType.MAGNETIC_MODULE,
            ModuleType.MAGNETIC_MODULE_V1,
            ModuleType.MAGNETIC_BLOCK,
        ):
            self._handle_magnetic_module_method(
                base_var, method_name, args, kwargs, lineno, source_code
            )
        elif module.module_type == ModuleType.ABSORBANCE_READER:
            self._handle_absorbance_reader_method(
                base_var, method_name, args, kwargs, lineno, source_code
            )
        elif module.module_type == ModuleType.FLEX_STACKER:
            self._handle_flex_stacker_method(
                base_var, method_name, args, kwargs, lineno, source_code
            )

    def _handle_temp_module_method(
        self,
        module_var: str,
        method_name: str,
        args: list[Any],
        kwargs: dict[str, Any],
        lineno: int,
        source_code: str,
    ) -> None:
        """Handle Temperature Module method calls."""
        cmd_type = self.TEMP_MODULE_METHOD_MAP.get(method_name)
        if not cmd_type:
            return

        params = {}
        if method_name in ("set_temperature", "start_set_temperature"):
            celsius = args[0] if args else kwargs.get("celsius")
            params["celsius"] = celsius
        elif method_name in ("await_temperature", "wait_for_temperature"):
            celsius = args[0] if args else kwargs.get("celsius")
            if celsius:
                params["celsius"] = celsius

        self._add_command(cmd_type, params, lineno, source_code, module_var=module_var)

    def _handle_thermocycler_method(
        self,
        module_var: str,
        method_name: str,
        args: list[Any],
        kwargs: dict[str, Any],
        lineno: int,
        source_code: str,
    ) -> None:
        """Handle Thermocycler method calls."""
        cmd_type = self.TC_METHOD_MAP.get(method_name)
        if not cmd_type:
            return

        params = {}
        if method_name == "set_block_temperature":
            temperature = args[0] if args else kwargs.get("temperature")
            hold_time_seconds = kwargs.get("hold_time_seconds")
            hold_time_minutes = kwargs.get("hold_time_minutes")
            block_max_volume = kwargs.get("block_max_volume")

            params["celsius"] = temperature
            if hold_time_seconds:
                params["holdTimeSeconds"] = hold_time_seconds
            if hold_time_minutes:
                params["holdTimeSeconds"] = (
                    params.get("holdTimeSeconds", 0) + hold_time_minutes * 60
                )
            if block_max_volume:
                params["blockMaxVolumeUl"] = block_max_volume

        elif method_name == "set_lid_temperature":
            temperature = args[0] if args else kwargs.get("temperature")
            params["celsius"] = temperature

        elif method_name in ("execute_profile", "run_profile"):
            steps = kwargs.get("steps", [])
            repetitions = kwargs.get("repetitions", 1)
            block_max_volume = kwargs.get("block_max_volume")

            params["profile"] = steps
            params["blockMaxVolumeUl"] = block_max_volume

        self._add_command(cmd_type, params, lineno, source_code, module_var=module_var)

    def _handle_heater_shaker_method(
        self,
        module_var: str,
        method_name: str,
        args: list[Any],
        kwargs: dict[str, Any],
        lineno: int,
        source_code: str,
    ) -> None:
        """Handle Heater-Shaker method calls."""
        cmd_type = self.HS_METHOD_MAP.get(method_name)
        if not cmd_type:
            return

        params = {}
        if method_name == "set_target_temperature":
            celsius = args[0] if args else kwargs.get("celsius")
            params["celsius"] = celsius
        elif method_name == "set_and_wait_for_shake_speed":
            rpm = args[0] if args else kwargs.get("rpm")
            params["rpm"] = rpm

        self._add_command(cmd_type, params, lineno, source_code, module_var=module_var)

    def _handle_magnetic_module_method(
        self,
        module_var: str,
        method_name: str,
        args: list[Any],
        kwargs: dict[str, Any],
        lineno: int,
        source_code: str,
    ) -> None:
        """Handle Magnetic Module method calls."""
        cmd_type = self.MAG_METHOD_MAP.get(method_name)
        if not cmd_type:
            return

        params = {}
        if method_name == "engage":
            height = kwargs.get("height") or kwargs.get("height_from_base")
            if height:
                params["height"] = height

        self._add_command(cmd_type, params, lineno, source_code, module_var=module_var)

    def _handle_absorbance_reader_method(
        self,
        module_var: str,
        method_name: str,
        args: list[Any],
        kwargs: dict[str, Any],
        lineno: int,
        source_code: str,
    ) -> None:
        """Handle Absorbance Reader method calls."""
        cmd_type = self.ABS_METHOD_MAP.get(method_name)
        if not cmd_type:
            return

        params = {}
        if method_name == "initialize":
            mode = kwargs.get("mode", "single")
            wavelengths = kwargs.get("wavelengths", [])
            reference_wavelength = kwargs.get("reference_wavelength")

            params["measureMode"] = mode
            params["sampleWavelengths"] = wavelengths
            if reference_wavelength:
                params["referenceWavelength"] = reference_wavelength

        elif method_name == "read":
            export_filename = kwargs.get("export_filename")
            if export_filename:
                params["fileName"] = export_filename

        self._add_command(cmd_type, params, lineno, source_code, module_var=module_var)

    def _handle_flex_stacker_method(
        self,
        module_var: str,
        method_name: str,
        args: list[Any],
        kwargs: dict[str, Any],
        lineno: int,
        source_code: str,
    ) -> None:
        """Handle Flex Stacker method calls."""
        cmd_type = self.STACKER_METHOD_MAP.get(method_name)
        if not cmd_type:
            return

        self._add_command(cmd_type, {}, lineno, source_code, module_var=module_var)

    def _handle_labware_method(
        self,
        var_name: Optional[str],
        labware_var: str,
        method_name: str,
        args: list[Any],
        kwargs: dict[str, Any],
        lineno: int,
        source_code: str,
    ) -> None:
        """Handle labware method calls like load_liquid."""
        if method_name == "load_liquid":
            liquid = kwargs.get("liquid")
            volume = kwargs.get("volume")

            self._add_command(
                CommandType.LOAD_LIQUID,
                {
                    "liquidId": f"${liquid}" if isinstance(liquid, str) else None,
                    "volumeByWell": volume,
                },
                lineno,
                source_code,
                labware_var=labware_var,
            )
        elif method_name == "load_labware":
            # Module's load_labware method
            self._handle_load_labware(var_name, args, kwargs, lineno, source_code)

    def _handle_well_method(
        self,
        well_ref: str,
        method_name: str,
        args: list[Any],
        kwargs: dict[str, Any],
        lineno: int,
        source_code: str,
    ) -> None:
        """Handle well method calls like well.load_liquid()."""
        if method_name == "load_liquid":
            # Parse the well reference to get labware and well
            match = re.match(r"(\w+)\[([^\]]+)\]", well_ref)
            if match:
                labware_var = match.group(1)
                well_name = match.group(2).strip("'\"")

                liquid = kwargs.get("liquid")
                volume = kwargs.get("volume")

                self._add_command(
                    CommandType.LOAD_LIQUID,
                    {
                        "liquidId": f"${liquid}" if isinstance(liquid, str) else None,
                        "volume": volume,
                        "wellName": well_name,
                    },
                    lineno,
                    source_code,
                    labware_var=labware_var,
                )

    def _parse_for_loop(self, stmt: ast.For) -> None:
        """Parse a for loop and expand its body."""
        # Try to evaluate the iteration range
        iter_values = self._get_iteration_values(stmt.iter)

        if iter_values is not None:
            # Unroll the loop if we know the iteration values
            target_name = stmt.target.id if isinstance(stmt.target, ast.Name) else None
            for value in iter_values:
                if target_name:
                    self._variables[target_name] = value
                for body_stmt in stmt.body:
                    self._parse_statement(body_stmt)
        else:
            # Can't unroll, just parse the body once as a template
            for body_stmt in stmt.body:
                self._parse_statement(body_stmt)

    def _get_iteration_values(self, iter_node: ast.expr) -> Optional[list[Any]]:
        """Try to get iteration values from a for loop iterator."""
        if isinstance(iter_node, ast.Call):
            if isinstance(iter_node.func, ast.Name):
                if iter_node.func.id == "range":
                    args = [self._eval_value(a) for a in iter_node.args]
                    if len(args) == 1:
                        return list(range(args[0]))
                    elif len(args) == 2:
                        return list(range(args[0], args[1]))
                    elif len(args) == 3:
                        return list(range(args[0], args[1], args[2]))
            elif isinstance(iter_node.func, ast.Attribute):
                # Handle things like plate.wells(), plate.rows(), etc.
                if iter_node.func.attr == "wells":
                    return [f"A{i}" for i in range(1, 13)] + [
                        f"{chr(65+r)}{c}" for r in range(1, 8) for c in range(1, 13)
                    ]
                elif iter_node.func.attr == "columns":
                    return [[f"{chr(65+r)}{c}" for r in range(8)] for c in range(1, 13)]
                elif iter_node.func.attr == "rows":
                    return [[f"{chr(65+r)}{c}" for c in range(1, 13)] for r in range(8)]
        elif isinstance(iter_node, ast.List):
            return [self._eval_value(elt) for elt in iter_node.elts]

        return None

    def _parse_if_statement(self, stmt: ast.If) -> None:
        """Parse an if statement - include both branches as potential commands."""
        for body_stmt in stmt.body:
            self._parse_statement(body_stmt)
        for else_stmt in stmt.orelse:
            self._parse_statement(else_stmt)

    def _parse_with_statement(self, stmt: ast.With) -> None:
        """Parse a with statement."""
        for body_stmt in stmt.body:
            self._parse_statement(body_stmt)

    def _parse_parameters_function(self, func: ast.FunctionDef) -> None:
        """Parse the add_parameters function."""
        # Find the parameters object
        params_var = func.args.args[0].arg if func.args.args else "parameters"

        for stmt in func.body:
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                call = stmt.value
                if isinstance(call.func, ast.Attribute):
                    if isinstance(call.func.value, ast.Name):
                        if call.func.value.id == params_var:
                            method_name = call.func.attr
                            self._parse_parameter_definition(method_name, call)

    def _parse_parameter_definition(self, method_name: str, call: ast.Call) -> None:
        """Parse a runtime parameter definition."""
        kwargs = {kw.arg: self._eval_value(kw.value) for kw in call.keywords if kw.arg}

        param_type_map = {
            "add_int": "int",
            "add_float": "float",
            "add_bool": "bool",
            "add_str": "str",
            "add_csv_file": "csv_file",
        }

        param_type = param_type_map.get(method_name)
        if not param_type:
            return

        param = RuntimeParameter(
            variable_name=kwargs.get("variable_name", ""),
            param_type=param_type,
            display_name=kwargs.get("display_name", ""),
            default=kwargs.get("default"),
            description=kwargs.get("description"),
            min_value=kwargs.get("minimum"),
            max_value=kwargs.get("maximum"),
            choices=kwargs.get("choices"),
        )
        self._parsed.runtime_parameters.append(param)

    def _parse_location(self, location: Any) -> DeckLocation:
        """Parse a location value to DeckLocation."""
        if isinstance(location, str):
            # Could be a slot name or variable reference
            if location.startswith("$"):
                return DeckLocation(slot="", labware_id=location[1:])
            return DeckLocation(slot=location)
        elif isinstance(location, int):
            return DeckLocation(slot=str(location))
        elif isinstance(location, dict):
            return DeckLocation(
                slot=location.get("slot", location.get("slotName", "")),
                module_id=location.get("moduleId"),
                adapter_id=location.get("adapterId"),
            )
        return DeckLocation(slot="")

    def _parse_well_location(self, location: Any) -> tuple[Optional[str], Optional[str]]:
        """Parse a well location to (labware_var, well_name)."""
        if location is None:
            return None, None

        if isinstance(location, str):
            # Handle string like "plate[A1]" or "$plate[A1]"
            match = re.match(r"\$?(\w+)\[([^\]]+)\]", location)
            if match:
                return match.group(1), match.group(2).strip("'\"")

            # Handle variable reference "$plate"
            if location.startswith("$"):
                return location[1:], None

        return None, None

    def _parse_well_position(self, location: Any) -> Optional[dict[str, Any]]:
        """Parse well position modifiers like .top(), .bottom()."""
        # This would need more sophisticated parsing of chained method calls
        # For now, return None (default position)
        return None

    def _add_command(
        self,
        command_type: CommandType,
        params: dict[str, Any],
        lineno: int,
        source_code: str,
        pipette_var: Optional[str] = None,
        labware_var: Optional[str] = None,
        module_var: Optional[str] = None,
        well_name: Optional[str] = None,
    ) -> None:
        """Add a command to the parsed protocol."""
        cmd = ProtocolCommand(
            command_type=command_type,
            params=params,
            source_line=lineno,
            source_code=source_code,
            pipette_var=pipette_var,
            labware_var=labware_var,
            module_var=module_var,
            well_name=well_name,
        )
        self._parsed.commands.append(cmd)
