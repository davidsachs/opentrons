"""
Command-line interface for the Opentrons Protocol Translator.
"""

import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax

from .parser import ProtocolParser
from .generator import HTTPGenerator


console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli() -> None:
    """Opentrons Protocol Translator - Convert Python API to HTTP API protocols."""
    pass


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    help="Output file path (default: input_http.py)",
)
@click.option(
    "--preview",
    is_flag=True,
    help="Preview the generated code without writing to file",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed parsing information",
)
def translate(
    input_file: str,
    output: Optional[str],
    preview: bool,
    verbose: bool,
) -> None:
    """Translate a Python API protocol to HTTP API.

    INPUT_FILE: Path to the Python API protocol file.
    """
    input_path = Path(input_file)

    if not output:
        output = str(input_path.stem) + "_http.py"

    console.print(f"[bold blue]Translating:[/] {input_path}")

    try:
        # Parse the protocol
        parser = ProtocolParser()
        parsed = parser.parse_file(input_path)

        if verbose:
            _show_parsed_info(parsed)

        # Generate HTTP API code
        generator = HTTPGenerator(parsed)
        http_code = generator.generate()

        if preview:
            console.print("\n[bold green]Generated HTTP API Protocol:[/]\n")
            syntax = Syntax(http_code, "python", theme="monokai", line_numbers=True)
            console.print(syntax)
        else:
            output_path = Path(output)
            output_path.write_text(http_code)
            console.print(f"[bold green]✓[/] Written to: {output_path}")

        # Show summary
        console.print(f"\n[bold]Summary:[/]")
        console.print(f"  Labware:  {len(parsed.labware)}")
        console.print(f"  Pipettes: {len(parsed.pipettes)}")
        console.print(f"  Modules:  {len(parsed.modules)}")
        console.print(f"  Commands: {len(parsed.commands)}")

    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
        sys.exit(1)


@cli.command()
@click.argument("original", type=click.Path(exists=True))
@click.argument("translated", type=click.Path(exists=True))
@click.option(
    "--robot-ip",
    default="localhost",
    help="IP address of the Opentrons robot",
)
@click.option(
    "--local",
    is_flag=True,
    help="Use local analyzer instead of robot",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output comparison report to file",
)
def compare(
    original: str,
    translated: str,
    robot_ip: str,
    local: bool,
    output: Optional[str],
) -> None:
    """Compare analysis results of original and translated protocols.

    ORIGINAL: Path to the original Python API protocol.
    TRANSLATED: Path to the translated HTTP API protocol.
    """
    from .analyzer.compare import ProtocolComparator

    console.print("[bold blue]Comparing protocols...[/]")
    console.print(f"  Original:   {original}")
    console.print(f"  Translated: {translated}")

    try:
        comparator = ProtocolComparator(
            robot_ip=robot_ip if not local else None,
            use_local=local,
        )

        result = comparator.compare(original, translated)

        if result.identical:
            console.print("\n[bold green]✓ Protocols produce identical commands![/]")
        else:
            console.print("\n[bold red]✗ Protocols differ![/]")
            _show_differences(result)

        if output:
            result.save_report(output)
            console.print(f"\n[bold]Report saved to:[/] {output}")

    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        sys.exit(1)


@cli.command()
@click.argument("protocol_file", type=click.Path(exists=True))
@click.option(
    "--robot-ip",
    default="localhost",
    help="IP address of the Opentrons robot",
)
@click.option(
    "--local",
    is_flag=True,
    help="Use local analyzer",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output raw JSON analysis",
)
def analyze(
    protocol_file: str,
    robot_ip: str,
    local: bool,
    json_output: bool,
) -> None:
    """Analyze a protocol and show the resulting commands.

    PROTOCOL_FILE: Path to the protocol file to analyze.
    """
    from .analyzer.runner import ProtocolAnalyzer

    console.print(f"[bold blue]Analyzing:[/] {protocol_file}")

    try:
        analyzer = ProtocolAnalyzer(
            robot_ip=robot_ip if not local else None,
            use_local=local,
        )

        result = analyzer.analyze(protocol_file)

        if json_output:
            import json
            console.print(json.dumps(result, indent=2))
        else:
            _show_analysis_result(result)

    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        sys.exit(1)


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
def parse(input_file: str) -> None:
    """Parse a protocol and show its structure.

    INPUT_FILE: Path to the Python API protocol file.
    """
    input_path = Path(input_file)

    console.print(f"[bold blue]Parsing:[/] {input_path}")

    try:
        parser = ProtocolParser()
        parsed = parser.parse_file(input_path)
        _show_parsed_info(parsed)

    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        sys.exit(1)


def _show_parsed_info(parsed) -> None:
    """Display parsed protocol information."""
    console.print("\n[bold]Protocol Metadata:[/]")
    console.print(f"  Name:      {parsed.metadata.protocol_name or 'N/A'}")
    console.print(f"  API Level: {parsed.metadata.api_level}")
    console.print(f"  Robot:     {parsed.metadata.robot_type.value}")

    if parsed.labware:
        console.print("\n[bold]Labware:[/]")
        table = Table(show_header=True)
        table.add_column("Variable")
        table.add_column("Load Name")
        table.add_column("Location")

        for lw in parsed.labware:
            table.add_row(
                lw.variable_name,
                lw.load_name,
                lw.location.slot or "N/A",
            )
        console.print(table)

    if parsed.pipettes:
        console.print("\n[bold]Pipettes:[/]")
        table = Table(show_header=True)
        table.add_column("Variable")
        table.add_column("Instrument")
        table.add_column("Mount")

        for p in parsed.pipettes:
            table.add_row(
                p.variable_name,
                p.instrument_name,
                p.mount.value,
            )
        console.print(table)

    if parsed.modules:
        console.print("\n[bold]Modules:[/]")
        table = Table(show_header=True)
        table.add_column("Variable")
        table.add_column("Type")
        table.add_column("Location")

        for m in parsed.modules:
            table.add_row(
                m.variable_name,
                m.module_type.value,
                m.location,
            )
        console.print(table)

    if parsed.commands:
        console.print(f"\n[bold]Commands:[/] {len(parsed.commands)} total")

        # Show first 20 commands
        table = Table(show_header=True)
        table.add_column("#")
        table.add_column("Type")
        table.add_column("Details")

        for i, cmd in enumerate(parsed.commands[:20]):
            details = []
            if cmd.pipette_var:
                details.append(f"pipette={cmd.pipette_var}")
            if cmd.labware_var:
                details.append(f"labware={cmd.labware_var}")
            if cmd.well_name:
                details.append(f"well={cmd.well_name}")
            if "volume" in cmd.params:
                details.append(f"vol={cmd.params['volume']}")

            table.add_row(
                str(i + 1),
                cmd.command_type.value,
                ", ".join(details) if details else "-",
            )

        console.print(table)

        if len(parsed.commands) > 20:
            console.print(f"  ... and {len(parsed.commands) - 20} more commands")


def _show_differences(result) -> None:
    """Display differences between protocols."""
    console.print("\n[bold]Differences:[/]")

    for diff in result.differences[:10]:
        console.print(f"\n  [yellow]Command {diff.index}:[/]")
        console.print(f"    Original:   {diff.original}")
        console.print(f"    Translated: {diff.translated}")
        console.print(f"    Reason:     {diff.reason}")

    if len(result.differences) > 10:
        console.print(f"\n  ... and {len(result.differences) - 10} more differences")


def _show_analysis_result(result) -> None:
    """Display analysis result."""
    console.print("\n[bold]Analysis Result:[/]")

    if "errors" in result and result["errors"]:
        console.print(f"\n[bold red]Errors:[/]")
        for error in result["errors"]:
            console.print(f"  - {error}")

    if "commands" in result:
        console.print(f"\n[bold]Commands:[/] {len(result['commands'])} total")

        table = Table(show_header=True)
        table.add_column("#")
        table.add_column("Type")
        table.add_column("Status")

        for i, cmd in enumerate(result["commands"][:20]):
            table.add_row(
                str(i + 1),
                cmd.get("commandType", "unknown"),
                cmd.get("status", "unknown"),
            )

        console.print(table)

        if len(result["commands"]) > 20:
            console.print(f"  ... and {len(result['commands']) - 20} more commands")


# Entry points for setuptools
def translate_main() -> None:
    """Entry point for opentrons-translate command."""
    cli(["translate"] + sys.argv[1:])


def compare_main() -> None:
    """Entry point for opentrons-compare command."""
    cli(["compare"] + sys.argv[1:])


if __name__ == "__main__":
    cli()
