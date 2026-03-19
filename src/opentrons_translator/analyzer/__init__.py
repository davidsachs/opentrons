"""Analyzer module - symlink to top-level analyzer."""

# Re-export from the top-level analyzer module
import sys
from pathlib import Path

# Add the analyzer directory to path
analyzer_path = Path(__file__).parent.parent.parent.parent / "analyzer"
sys.path.insert(0, str(analyzer_path.parent))

from analyzer.compare import ProtocolComparator, ComparisonResult
from analyzer.runner import ProtocolAnalyzer, AnalysisResult

__all__ = [
    "ProtocolComparator",
    "ComparisonResult",
    "ProtocolAnalyzer",
    "AnalysisResult",
]
