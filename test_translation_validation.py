#!/usr/bin/env python3
"""
Translation Validation Test

This script validates that the Python-to-HTTP translation correctly preserves
the protocol's command sequence by comparing:
1. The commands extracted from the original Python protocol
2. The commands that would be executed by the translated HTTP script

Since the HTTP script cannot be analyzed by the Opentrons analyzer (it's not
a standard protocol format), we instead compare the command sequences directly
from the parsed protocol and the generated code.
"""

import argparse
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.opentrons_translator.parser import ProtocolParser
from src.opentrons_translator.generator import HTTPGenerator
from analyzer.runner import ProtocolAnalyzer


console = Console()


def extract_commands_from_protocol(protocol_path: Path, use_local: bool = True, robot_ip: str = None) -> list:
    """
    Extract commands from original Python protocol using analyzer.

    Args:
        protocol_path: Path to Python protocol
        use_local: Use local analyzer
        robot_ip: Robot IP if using HTTP analyzer

    Returns:
        List of normalized commands
    """
    console.print(f"\n[cyan]Extracting commands from original protocol...[/]")

    analyzer = ProtocolAnalyzer(
        robot_ip=robot_ip,
        use_local=use_local,
    )

    result = analyzer.analyze(protocol_path)

    if result.status != "ok":
        console.print(f"[red]✗ Analysis failed: {result.status}[/]")
        for error in result.errors:
            console.print(f"  Error: {error}")
        return []

    console.print(f"[green]✓ Extracted {len(result.commands)} commands[/]")

    # Normalize commands
    normalized = []
    for cmd in result.commands:
        normalized.append({
            "commandType": cmd.get("commandType"),
            "params": normalize_params(cmd.get("params", {})),
        })

    return normalized


def extract_commands_from_parsed(protocol_path: Path) -> list:
    """
    Extract commands from the parsed protocol (before HTTP generation).

    Args:
        protocol_path: Path to Python protocol

    Returns:
        List of command dictionaries
    """
    console.print(f"\n[cyan]Parsing protocol to extract command sequence...[/]")

    parser = ProtocolParser()
    parsed = parser.parse_file(protocol_path)

    console.print(f"[green]✓ Parsed {len(parsed.commands)} commands[/]")

    commands = []
    for cmd in parsed.commands:
        cmd_dict = {
            "commandType": cmd.command_type.value if hasattr(cmd.command_type, 'value') else cmd.command_type,
            "params": {},
        }

        # Extract relevant parameters
        if cmd.pipette_var:
            cmd_dict["params"]["pipette"] = cmd.pipette_var
        if cmd.labware_var:
            cmd_dict["params"]["labware"] = cmd.labware_var
        if cmd.well_name:
            cmd_dict["params"]["well"] = cmd.well_name
        if cmd.volume is not None:
            cmd_dict["params"]["volume"] = cmd.volume
        if cmd.flow_rate is not None:
            cmd_dict["params"]["flowRate"] = cmd.flow_rate
        if cmd.module_var:
            cmd_dict["params"]["module"] = cmd.module_var

        # Add any other parameters from the command
        for key, value in vars(cmd).items():
            if key not in ['command_type', 'pipette_var', 'labware_var', 'well_name',
                          'volume', 'flow_rate', 'module_var', 'line_number'] and value is not None:
                cmd_dict["params"][key] = value

        commands.append(cmd_dict)

    return commands


def normalize_params(params: dict) -> dict:
    """Normalize parameters by removing IDs and runtime data."""
    normalized = {}

    ignore_fields = {"key", "id"}

    for key, value in params.items():
        if key in ignore_fields:
            continue

        if key.endswith("Id"):
            normalized[key] = f"<{key}>"
        elif isinstance(value, dict):
            normalized[key] = normalize_params(value)
        elif isinstance(value, list):
            normalized[key] = [
                normalize_params(v) if isinstance(v, dict) else v
                for v in value
            ]
        elif isinstance(value, float):
            normalized[key] = round(value, 6)
        else:
            normalized[key] = value

    return normalized


def compare_command_sequences(analyzer_commands: list, parsed_commands: list) -> tuple[bool, list]:
    """
    Compare two command sequences.

    Args:
        analyzer_commands: Commands from analyzer (normalized)
        parsed_commands: Commands from parser

    Returns:
        Tuple of (is_identical, list_of_differences)
    """
    console.print(f"\n[cyan]Comparing command sequences...[/]")
    console.print(f"  Analyzer commands: {len(analyzer_commands)}")
    console.print(f"  Parsed commands: {len(parsed_commands)}")

    differences = []

    # Check if counts match
    if len(analyzer_commands) != len(parsed_commands):
        differences.append({
            "type": "count_mismatch",
            "analyzer_count": len(analyzer_commands),
            "parsed_count": len(parsed_commands),
        })

    # Compare command types
    analyzer_types = [cmd.get("commandType") for cmd in analyzer_commands]
    parsed_types = [cmd.get("commandType") for cmd in parsed_commands]

    if analyzer_types != parsed_types:
        differences.append({
            "type": "command_type_sequence_mismatch",
            "analyzer_types": analyzer_types,
            "parsed_types": parsed_types,
        })

    return len(differences) == 0, differences


def main():
    parser = argparse.ArgumentParser(
        description="Validate Python-to-HTTP translation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--protocol",
        type=Path,
        required=True,
        help="Path to the Python protocol to test",
    )

    parser.add_argument(
        "--robot-ip",
        type=str,
        help="IP address of the robot for analyzer (e.g., 10.90.158.110)",
    )

    parser.add_argument(
        "--local",
        action="store_true",
        help="Use local analyzer instead of robot HTTP API",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("test_results"),
        help="Directory for output files (default: test_results/)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed information",
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.local and not args.robot_ip:
        console.print("[red]Error: Must specify either --robot-ip or --local[/]")
        parser.print_help()
        sys.exit(1)

    if not args.protocol.exists():
        console.print(f"[red]Error: Protocol file not found: {args.protocol}[/]")
        sys.exit(1)

    # Print test configuration
    console.print(Panel.fit(
        f"[bold]Translation Validation Test[/]\n\n"
        f"Protocol: [green]{args.protocol}[/]\n"
        f"Analyzer: [cyan]{'Local CLI' if args.local else f'Robot at {args.robot_ip}'}[/]\n"
        f"Output: [yellow]{args.output}[/]",
        border_style="blue",
    ))

    try:
        # Step 1: Analyze original protocol
        console.print(Panel("[bold]Step 1: Analyze Original Protocol[/]", border_style="cyan"))

        analyzer_commands = extract_commands_from_protocol(
            args.protocol,
            use_local=args.local,
            robot_ip=args.robot_ip,
        )

        if not analyzer_commands:
            console.print("[red]✗ Failed to extract commands from protocol[/]")
            sys.exit(1)

        # Step 2: Parse protocol and extract commands
        console.print(Panel("[bold]Step 2: Parse Protocol[/]", border_style="cyan"))

        parsed_commands = extract_commands_from_parsed(args.protocol)

        # Step 3: Generate HTTP code (to verify it's valid)
        console.print(Panel("[bold]Step 3: Generate HTTP Code[/]", border_style="cyan"))

        console.print(f"\n[cyan]Generating HTTP API code...[/]")

        parser_obj = ProtocolParser()
        parsed = parser_obj.parse_file(args.protocol)

        generator = HTTPGenerator(parsed)
        http_code = generator.generate()

        # Verify it's valid Python
        try:
            compile(http_code, "<string>", "exec")
            console.print(f"[green]✓ Generated valid HTTP code ({len(http_code)} characters)[/]")
        except SyntaxError as e:
            console.print(f"[red]✗ Generated code has syntax errors: {e}[/]")
            sys.exit(1)

        # Step 4: Compare
        console.print(Panel("[bold]Step 4: Compare Command Sequences[/]", border_style="cyan"))

        is_identical, differences = compare_command_sequences(analyzer_commands, parsed_commands)

        # Step 5: Save results
        args.output.mkdir(parents=True, exist_ok=True)

        result_data = {
            "identical": is_identical,
            "protocol": str(args.protocol),
            "analyzer_command_count": len(analyzer_commands),
            "parsed_command_count": len(parsed_commands),
            "differences": differences,
            "analyzer_commands": analyzer_commands if args.verbose else analyzer_commands[:10],
            "parsed_commands": parsed_commands if args.verbose else parsed_commands[:10],
        }

        result_file = args.output / f"{args.protocol.stem}_validation_result.json"
        with open(result_file, "w") as f:
            json.dump(result_data, f, indent=2)

        console.print(f"\n[green]✓ Results saved to: {result_file}[/]")

        # Save HTTP code
        http_file = args.output / f"{args.protocol.stem}_http.py"
        with open(http_file, "w") as f:
            f.write(http_code)
        console.print(f"[green]✓ HTTP code saved to: {http_file}[/]")

        # Step 6: Display results
        if is_identical:
            console.print(Panel(
                "[bold green]✓ SUCCESS: Parser correctly extracted all commands![/]",
                border_style="green",
            ))

            # Show command type summary
            table = Table(title="Command Summary")
            table.add_column("Command Type", style="cyan")
            table.add_column("Count", justify="right", style="magenta")

            from collections import Counter
            cmd_types = Counter(cmd.get("commandType") for cmd in analyzer_commands)
            for cmd_type, count in cmd_types.most_common():
                table.add_row(cmd_type, str(count))

            console.print(table)

            console.print("\n[bold green]Test PASSED ✓[/]")
            sys.exit(0)
        else:
            console.print(Panel(
                f"[bold red]✗ FAILURE: Found {len(differences)} differences[/]",
                border_style="red",
            ))

            for diff in differences:
                console.print(f"\n{json.dumps(diff, indent=2)}")

            console.print(f"\n[bold red]Test FAILED ✗[/]")
            console.print(f"See details in: {result_file}")
            sys.exit(1)

    except KeyboardInterrupt:
        console.print("\n[yellow]Test interrupted by user[/]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[red]Test failed: {e}[/]")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
