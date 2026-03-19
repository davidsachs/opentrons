#!/usr/bin/env python3
"""
Manual analyzer test using direct HTTP API calls (matching your curl examples).

This script demonstrates the exact workflow you described:
1. Upload original Python protocol to robot analyzer
2. Get the analysis ID from response
3. Fetch the detailed analysis results
4. Translate the protocol to HTTP version
5. Upload translated protocol to analyzer
6. Fetch its analysis results
7. Compare the two analysis results (normalized)

This is useful for understanding the low-level API interactions and debugging.
For production testing, use test_analyzer.py instead.

Usage:
    python test_analyzer_manual.py --protocol pickup_and_dip_labware.py --robot-ip 10.90.158.110
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

from src.opentrons_translator.parser import ProtocolParser
from src.opentrons_translator.generator import HTTPGenerator


console = Console()


def upload_protocol(robot_ip: str, protocol_path: Path, verbose: bool = False) -> tuple[str, str]:
    """
    Upload a protocol to the robot analyzer.

    Args:
        robot_ip: Robot IP address
        protocol_path: Path to protocol file
        verbose: Print detailed information

    Returns:
        Tuple of (protocol_id, analysis_id)
    """
    url = f"http://{robot_ip}:31950/protocols"

    console.print(f"\n[cyan]Uploading protocol:[/] {protocol_path.name}")
    console.print(f"[dim]POST {url}[/]")

    try:
        with open(protocol_path, "rb") as f:
            files = {"files": (protocol_path.name, f, "application/octet-stream")}
            headers = {"Opentrons-Version": "3"}

            response = requests.post(url, files=files, headers=headers, timeout=60)
            response.raise_for_status()

        data = response.json()

        if verbose:
            console.print(f"\n[dim]Response:[/]")
            syntax = Syntax(json.dumps(data, indent=2), "json", theme="monokai")
            console.print(syntax)

        protocol_id = data["data"]["id"]
        analysis_summaries = data["data"].get("analysisSummaries", [])

        if not analysis_summaries:
            console.print("[yellow]Warning:[/] No analysis summaries in response")
            return protocol_id, None

        analysis_id = analysis_summaries[0]["id"]
        analysis_status = analysis_summaries[0]["status"]

        console.print(f"[green]✓[/] Protocol uploaded")
        console.print(f"  Protocol ID: [yellow]{protocol_id}[/]")
        console.print(f"  Analysis ID: [yellow]{analysis_id}[/]")
        console.print(f"  Status: [cyan]{analysis_status}[/]")

        return protocol_id, analysis_id

    except requests.exceptions.RequestException as e:
        console.print(f"[red]✗ Upload failed:[/] {e}")
        raise
    except KeyError as e:
        console.print(f"[red]✗ Unexpected response format:[/] {e}")
        raise


def wait_for_analysis(
    robot_ip: str,
    protocol_id: str,
    analysis_id: str,
    timeout: int = 60,
    verbose: bool = False,
) -> str:
    """
    Wait for analysis to complete.

    Args:
        robot_ip: Robot IP address
        protocol_id: Protocol ID
        analysis_id: Analysis ID
        timeout: Maximum wait time in seconds
        verbose: Print detailed information

    Returns:
        Analysis status ("completed", "failed", etc.)
    """
    url = f"http://{robot_ip}:31950/protocols/{protocol_id}/analyses/{analysis_id}"

    console.print(f"\n[cyan]Waiting for analysis to complete...[/]")

    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            headers = {"Opentrons-Version": "3"}
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            data = response.json()
            status = data["data"]["status"]

            if status == "completed":
                console.print(f"[green]✓[/] Analysis completed")
                return status
            elif status in ("failed", "error"):
                console.print(f"[red]✗[/] Analysis failed: {status}")
                if verbose:
                    console.print(f"[dim]Error details:[/]")
                    syntax = Syntax(json.dumps(data.get("errors", []), indent=2), "json", theme="monokai")
                    console.print(syntax)
                return status
            else:
                console.print(f"  Status: [yellow]{status}[/]", end="\r")
                time.sleep(1)

        except requests.exceptions.RequestException as e:
            console.print(f"[red]✗ Request failed:[/] {e}")
            raise

    console.print(f"[red]✗[/] Analysis timed out after {timeout} seconds")
    return "timeout"


def get_analysis(
    robot_ip: str,
    protocol_id: str,
    analysis_id: str,
    verbose: bool = False,
) -> dict:
    """
    Get detailed analysis results.

    Args:
        robot_ip: Robot IP address
        protocol_id: Protocol ID
        analysis_id: Analysis ID
        verbose: Print detailed information

    Returns:
        Analysis data dictionary
    """
    url = f"http://{robot_ip}:31950/protocols/{protocol_id}/analyses/{analysis_id}"

    console.print(f"\n[cyan]Fetching analysis results[/]")
    console.print(f"[dim]GET {url}[/]")

    try:
        headers = {"Opentrons-Version": "3"}
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        data = response.json()["data"]

        console.print(f"[green]✓[/] Analysis retrieved")
        console.print(f"  Commands: {len(data.get('commands', []))}")
        console.print(f"  Labware: {len(data.get('labware', []))}")
        console.print(f"  Pipettes: {len(data.get('pipettes', []))}")
        console.print(f"  Modules: {len(data.get('modules', []))}")

        if verbose:
            console.print(f"\n[dim]First 3 commands:[/]")
            for i, cmd in enumerate(data.get("commands", [])[:3]):
                console.print(f"  {i+1}. {cmd.get('commandType', 'unknown')}")

        return data

    except requests.exceptions.RequestException as e:
        console.print(f"[red]✗ Request failed:[/] {e}")
        raise


def delete_protocol(robot_ip: str, protocol_id: str, verbose: bool = False) -> None:
    """
    Delete a protocol from the robot.

    Args:
        robot_ip: Robot IP address
        protocol_id: Protocol ID
        verbose: Print detailed information
    """
    url = f"http://{robot_ip}:31950/protocols/{protocol_id}"

    if verbose:
        console.print(f"\n[dim]Deleting protocol: {protocol_id}[/]")

    try:
        headers = {"Opentrons-Version": "3"}
        response = requests.delete(url, headers=headers, timeout=10)
        response.raise_for_status()

        if verbose:
            console.print(f"[green]✓[/] Protocol deleted")

    except requests.exceptions.RequestException:
        # Ignore cleanup errors
        pass


def normalize_command(cmd: dict) -> dict:
    """
    Normalize a command for comparison by removing runtime-specific data.

    Args:
        cmd: Command dictionary

    Returns:
        Normalized command dictionary
    """
    return {
        "commandType": cmd.get("commandType"),
        "params": normalize_params(cmd.get("params", {})),
    }


def normalize_params(params: dict) -> dict:
    """
    Normalize command parameters by removing IDs and runtime data.

    Args:
        params: Parameters dictionary

    Returns:
        Normalized parameters
    """
    normalized = {}

    # Fields to ignore
    ignore_fields = {"key", "id"}

    for key, value in params.items():
        if key in ignore_fields:
            continue

        # Replace IDs with placeholders
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
            # Round floats for comparison
            normalized[key] = round(value, 6)
        else:
            normalized[key] = value

    return normalized


def compare_commands(original: list[dict], translated: list[dict]) -> tuple[bool, list[dict]]:
    """
    Compare two command sequences.

    Args:
        original: Original command sequence
        translated: Translated command sequence

    Returns:
        Tuple of (is_identical, list_of_differences)
    """
    # Normalize both sequences
    orig_normalized = [normalize_command(cmd) for cmd in original]
    trans_normalized = [normalize_command(cmd) for cmd in translated]

    differences = []

    # Check length
    if len(orig_normalized) != len(trans_normalized):
        differences.append({
            "type": "length_mismatch",
            "original_count": len(orig_normalized),
            "translated_count": len(trans_normalized),
        })

    # Compare command by command
    max_len = max(len(orig_normalized), len(trans_normalized))

    for i in range(max_len):
        orig_cmd = orig_normalized[i] if i < len(orig_normalized) else None
        trans_cmd = trans_normalized[i] if i < len(trans_normalized) else None

        if orig_cmd is None:
            differences.append({
                "index": i,
                "type": "extra_in_translated",
                "translated": trans_cmd,
            })
        elif trans_cmd is None:
            differences.append({
                "index": i,
                "type": "missing_in_translated",
                "original": orig_cmd,
            })
        elif orig_cmd != trans_cmd:
            differences.append({
                "index": i,
                "type": "command_mismatch",
                "original": orig_cmd,
                "translated": trans_cmd,
            })

    return len(differences) == 0, differences


def main():
    parser = argparse.ArgumentParser(
        description="Manual analyzer test using direct HTTP API calls",
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
        required=True,
        help="IP address of the robot (e.g., 10.90.158.110)",
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

    if not args.protocol.exists():
        console.print(f"[red]Error:[/] Protocol file not found: {args.protocol}")
        sys.exit(1)

    # Print test header
    console.print(Panel.fit(
        f"[bold]Manual Analyzer Test[/]\n\n"
        f"Protocol: [green]{args.protocol}[/]\n"
        f"Robot: [cyan]{args.robot_ip}[/]",
        border_style="blue",
    ))

    protocol_ids_to_cleanup = []

    try:
        # Step 1: Upload and analyze original protocol
        console.print(Panel("[bold]Step 1: Analyze Original Protocol[/]", border_style="cyan"))

        orig_protocol_id, orig_analysis_id = upload_protocol(
            args.robot_ip,
            args.protocol,
            args.verbose,
        )
        protocol_ids_to_cleanup.append(orig_protocol_id)

        orig_status = wait_for_analysis(
            args.robot_ip,
            orig_protocol_id,
            orig_analysis_id,
            verbose=args.verbose,
        )

        if orig_status != "completed":
            console.print("[red]✗ Original protocol analysis failed[/]")
            sys.exit(1)

        orig_analysis = get_analysis(
            args.robot_ip,
            orig_protocol_id,
            orig_analysis_id,
            args.verbose,
        )

        # Step 2: Translate protocol
        console.print(Panel("[bold]Step 2: Translate Protocol[/]", border_style="cyan"))

        console.print(f"\n[cyan]Translating protocol...[/]")

        parser_obj = ProtocolParser()
        parsed = parser_obj.parse_file(args.protocol)

        generator = HTTPGenerator(parsed)
        http_code = generator.generate()

        translated_path = args.protocol.parent / f"{args.protocol.stem}_http.py"
        translated_path.write_text(http_code)

        console.print(f"[green]✓[/] Translation complete")
        console.print(f"  Output: {translated_path}")

        # Step 3: Upload and analyze translated protocol
        console.print(Panel("[bold]Step 3: Analyze Translated Protocol[/]", border_style="cyan"))

        trans_protocol_id, trans_analysis_id = upload_protocol(
            args.robot_ip,
            translated_path,
            args.verbose,
        )
        protocol_ids_to_cleanup.append(trans_protocol_id)

        trans_status = wait_for_analysis(
            args.robot_ip,
            trans_protocol_id,
            trans_analysis_id,
            verbose=args.verbose,
        )

        if trans_status != "completed":
            console.print("[red]✗ Translated protocol analysis failed[/]")
            sys.exit(1)

        trans_analysis = get_analysis(
            args.robot_ip,
            trans_protocol_id,
            trans_analysis_id,
            args.verbose,
        )

        # Step 4: Compare analyses
        console.print(Panel("[bold]Step 4: Compare Results[/]", border_style="cyan"))

        orig_commands = orig_analysis.get("commands", [])
        trans_commands = trans_analysis.get("commands", [])

        is_identical, differences = compare_commands(orig_commands, trans_commands)

        # Step 5: Save results
        args.output.mkdir(parents=True, exist_ok=True)

        # Save full analyses
        orig_file = args.output / f"{args.protocol.stem}_original_analysis.json"
        trans_file = args.output / f"{args.protocol.stem}_translated_analysis.json"
        comparison_file = args.output / f"{args.protocol.stem}_comparison.json"

        with open(orig_file, "w") as f:
            json.dump(orig_analysis, f, indent=2)

        with open(trans_file, "w") as f:
            json.dump(trans_analysis, f, indent=2)

        comparison_data = {
            "identical": is_identical,
            "original_command_count": len(orig_commands),
            "translated_command_count": len(trans_commands),
            "difference_count": len(differences),
            "differences": differences,
        }

        with open(comparison_file, "w") as f:
            json.dump(comparison_data, f, indent=2)

        console.print(f"\n[green]✓[/] Results saved:")
        console.print(f"  Original: {orig_file}")
        console.print(f"  Translated: {trans_file}")
        console.print(f"  Comparison: {comparison_file}")

        # Step 6: Display results
        if is_identical:
            console.print(Panel(
                "[bold green]✓ SUCCESS: Protocols produce identical commands![/]",
                border_style="green",
            ))
            sys.exit(0)
        else:
            console.print(Panel(
                f"[bold red]✗ FAILURE: Found {len(differences)} differences[/]",
                border_style="red",
            ))

            if args.verbose:
                console.print(f"\n[bold]First 5 differences:[/]")
                for diff in differences[:5]:
                    console.print(f"\n{json.dumps(diff, indent=2)}")

            console.print(f"\nSee full details in: {comparison_file}")
            sys.exit(1)

    except KeyboardInterrupt:
        console.print("\n[yellow]Test interrupted by user[/]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[red]Test failed:[/] {e}")
        if args.verbose:
            import traceback
            console.print(traceback.format_exc())
        sys.exit(1)
    finally:
        # Cleanup uploaded protocols
        console.print(f"\n[dim]Cleaning up...[/]")
        for protocol_id in protocol_ids_to_cleanup:
            delete_protocol(args.robot_ip, protocol_id, args.verbose)


if __name__ == "__main__":
    main()
