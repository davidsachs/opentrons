"""
Protocol comparison utilities.

Compares analysis results from original and translated protocols
to verify they produce identical low-level commands.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .runner import ProtocolAnalyzer, AnalysisResult


@dataclass
class CommandDifference:
    """Represents a difference between two commands."""

    index: int
    original: Optional[dict[str, Any]]
    translated: Optional[dict[str, Any]]
    reason: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ComparisonResult:
    """Result of comparing two protocols."""

    identical: bool
    original_analysis: AnalysisResult
    translated_analysis: AnalysisResult
    differences: list[CommandDifference] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def save_report(self, path: str | Path) -> None:
        """Save comparison report to file."""
        path = Path(path)

        report = {
            "identical": self.identical,
            "summary": self.summary,
            "original": {
                "status": self.original_analysis.status,
                "command_count": len(self.original_analysis.commands),
                "errors": self.original_analysis.errors,
            },
            "translated": {
                "status": self.translated_analysis.status,
                "command_count": len(self.translated_analysis.commands),
                "errors": self.translated_analysis.errors,
            },
            "differences": [
                {
                    "index": d.index,
                    "reason": d.reason,
                    "original": d.original,
                    "translated": d.translated,
                    "details": d.details,
                }
                for d in self.differences
            ],
        }

        with open(path, "w") as f:
            json.dump(report, f, indent=2)


class ProtocolComparator:
    """
    Compares original and translated protocols.

    Analyzes both protocols and compares their resulting command sequences
    to verify the translation preserves functionality.
    """

    def __init__(
        self,
        robot_ip: Optional[str] = None,
        use_local: bool = False,
    ) -> None:
        """
        Initialize the comparator.

        Args:
            robot_ip: IP address of robot for HTTP API analysis
            use_local: Use local CLI analyzer instead of robot
        """
        self.analyzer = ProtocolAnalyzer(
            robot_ip=robot_ip,
            use_local=use_local,
        )

    def compare(
        self,
        original_path: str | Path,
        translated_path: str | Path,
        runtime_params: Optional[dict[str, Any]] = None,
    ) -> ComparisonResult:
        """
        Compare two protocols.

        Args:
            original_path: Path to original Python API protocol
            translated_path: Path to translated HTTP API protocol
            runtime_params: Optional runtime parameter values

        Returns:
            ComparisonResult with differences (if any)
        """
        # Analyze both protocols
        original_result = self.analyzer.analyze(original_path, runtime_params)
        translated_result = self.analyzer.analyze(translated_path, runtime_params)

        # Check for analysis errors
        if original_result.status == "not-ok":
            return ComparisonResult(
                identical=False,
                original_analysis=original_result,
                translated_analysis=translated_result,
                differences=[
                    CommandDifference(
                        index=-1,
                        original=None,
                        translated=None,
                        reason="Original protocol analysis failed",
                        details={"errors": original_result.errors},
                    )
                ],
                summary={"error": "Original analysis failed"},
            )

        if translated_result.status == "not-ok":
            return ComparisonResult(
                identical=False,
                original_analysis=original_result,
                translated_analysis=translated_result,
                differences=[
                    CommandDifference(
                        index=-1,
                        original=None,
                        translated=None,
                        reason="Translated protocol analysis failed",
                        details={"errors": translated_result.errors},
                    )
                ],
                summary={"error": "Translated analysis failed"},
            )

        # Normalize commands for comparison
        original_commands = self._normalize_commands(original_result.commands)
        translated_commands = self._normalize_commands(translated_result.commands)

        # Compare commands
        differences = self._compare_command_sequences(
            original_commands, translated_commands
        )

        summary = {
            "original_commands": len(original_commands),
            "translated_commands": len(translated_commands),
            "difference_count": len(differences),
            "categories": self._categorize_differences(differences),
        }

        return ComparisonResult(
            identical=len(differences) == 0,
            original_analysis=original_result,
            translated_analysis=translated_result,
            differences=differences,
            summary=summary,
        )

    def compare_commands_only(
        self,
        original_commands: list[dict[str, Any]],
        translated_commands: list[dict[str, Any]],
    ) -> ComparisonResult:
        """
        Compare pre-analyzed command sequences.

        Useful when you've already run analysis separately.
        """
        original_normalized = self._normalize_commands(original_commands)
        translated_normalized = self._normalize_commands(translated_commands)

        differences = self._compare_command_sequences(
            original_normalized, translated_normalized
        )

        summary = {
            "original_commands": len(original_normalized),
            "translated_commands": len(translated_normalized),
            "difference_count": len(differences),
            "categories": self._categorize_differences(differences),
        }

        # Create dummy analysis results
        original_result = AnalysisResult(status="ok", commands=original_commands)
        translated_result = AnalysisResult(status="ok", commands=translated_commands)

        return ComparisonResult(
            identical=len(differences) == 0,
            original_analysis=original_result,
            translated_analysis=translated_result,
            differences=differences,
            summary=summary,
        )

    def _normalize_commands(
        self, commands: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Normalize commands for comparison.

        Removes runtime-specific data that shouldn't affect comparison:
        - Command IDs
        - Timestamps
        - Internal state tracking
        """
        normalized = []

        for cmd in commands:
            # Skip certain command types that are setup-only
            cmd_type = cmd.get("commandType", "")
            if cmd_type in ("home",):  # Some commands might be auto-added
                # Still include but mark for flexible comparison
                pass

            norm_cmd = {
                "commandType": cmd_type,
                "params": self._normalize_params(cmd.get("params", {})),
            }

            normalized.append(norm_cmd)

        return normalized

    def _normalize_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Normalize command parameters for comparison."""
        normalized = {}

        # Fields to ignore in comparison (runtime-specific)
        ignore_fields = {"key", "id"}

        # Fields that are IDs - we compare by value type but not exact value
        id_fields = {"pipetteId", "labwareId", "moduleId", "liquidId"}

        for key, value in params.items():
            if key in ignore_fields:
                continue

            if key in id_fields:
                # For IDs, we normalize to a consistent placeholder
                # This allows comparison of structure without exact ID matching
                normalized[key] = f"<{key}>"
                continue

            if isinstance(value, dict):
                normalized[key] = self._normalize_params(value)
            elif isinstance(value, list):
                normalized[key] = [
                    self._normalize_params(v) if isinstance(v, dict) else v
                    for v in value
                ]
            else:
                # Round floats for comparison
                if isinstance(value, float):
                    normalized[key] = round(value, 6)
                else:
                    normalized[key] = value

        return normalized

    def _compare_command_sequences(
        self,
        original: list[dict[str, Any]],
        translated: list[dict[str, Any]],
    ) -> list[CommandDifference]:
        """Compare two command sequences and find differences."""
        differences = []

        # Check length difference
        if len(original) != len(translated):
            differences.append(
                CommandDifference(
                    index=-1,
                    original=None,
                    translated=None,
                    reason="Different number of commands",
                    details={
                        "original_count": len(original),
                        "translated_count": len(translated),
                    },
                )
            )

        # Compare command by command
        max_len = max(len(original), len(translated))

        for i in range(max_len):
            orig_cmd = original[i] if i < len(original) else None
            trans_cmd = translated[i] if i < len(translated) else None

            if orig_cmd is None:
                differences.append(
                    CommandDifference(
                        index=i,
                        original=None,
                        translated=trans_cmd,
                        reason="Extra command in translated",
                    )
                )
            elif trans_cmd is None:
                differences.append(
                    CommandDifference(
                        index=i,
                        original=orig_cmd,
                        translated=None,
                        reason="Missing command in translated",
                    )
                )
            else:
                cmd_diff = self._compare_commands(i, orig_cmd, trans_cmd)
                if cmd_diff:
                    differences.append(cmd_diff)

        return differences

    def _compare_commands(
        self,
        index: int,
        original: dict[str, Any],
        translated: dict[str, Any],
    ) -> Optional[CommandDifference]:
        """Compare two individual commands."""
        # Check command type
        if original.get("commandType") != translated.get("commandType"):
            return CommandDifference(
                index=index,
                original=original,
                translated=translated,
                reason="Different command types",
                details={
                    "original_type": original.get("commandType"),
                    "translated_type": translated.get("commandType"),
                },
            )

        # Compare parameters
        orig_params = original.get("params", {})
        trans_params = translated.get("params", {})

        param_diffs = self._compare_params(orig_params, trans_params)

        if param_diffs:
            return CommandDifference(
                index=index,
                original=original,
                translated=translated,
                reason="Different parameters",
                details={"param_differences": param_diffs},
            )

        return None

    def _compare_params(
        self,
        original: dict[str, Any],
        translated: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Compare parameters and return differences."""
        differences = []

        all_keys = set(original.keys()) | set(translated.keys())

        for key in all_keys:
            orig_val = original.get(key)
            trans_val = translated.get(key)

            if orig_val != trans_val:
                # Check if it's a meaningful difference
                if self._is_meaningful_difference(key, orig_val, trans_val):
                    differences.append(
                        {
                            "key": key,
                            "original": orig_val,
                            "translated": trans_val,
                        }
                    )

        return differences

    def _is_meaningful_difference(
        self, key: str, original: Any, translated: Any
    ) -> bool:
        """Check if a difference is meaningful (not just formatting)."""
        # Both None or empty
        if (original is None or original == {}) and (
            translated is None or translated == {}
        ):
            return False

        # Floating point tolerance
        if isinstance(original, (int, float)) and isinstance(translated, (int, float)):
            if abs(float(original) - float(translated)) < 0.001:
                return False

        return True

    def _categorize_differences(
        self, differences: list[CommandDifference]
    ) -> dict[str, int]:
        """Categorize differences by type."""
        categories: dict[str, int] = {}

        for diff in differences:
            reason = diff.reason
            categories[reason] = categories.get(reason, 0) + 1

        return categories


def compare_protocols(
    original_path: str | Path,
    translated_path: str | Path,
    robot_ip: Optional[str] = None,
    use_local: bool = True,
) -> ComparisonResult:
    """
    Convenience function to compare two protocols.

    Args:
        original_path: Path to original Python API protocol
        translated_path: Path to translated HTTP API protocol
        robot_ip: Optional robot IP for HTTP analysis
        use_local: Use local analyzer (default True)

    Returns:
        ComparisonResult
    """
    comparator = ProtocolComparator(robot_ip=robot_ip, use_local=use_local)
    return comparator.compare(original_path, translated_path)
