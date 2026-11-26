"""README.md's validation numbers must be the ones in data/validation/report.md, copied, not retyped."""

import importlib.util
import sys
from pathlib import Path

import pytest

_path = Path(__file__).resolve().parents[1] / "scripts" / "readme_validation.py"
_spec = importlib.util.spec_from_file_location("readme_validation", _path)
readme_validation = importlib.util.module_from_spec(_spec)
sys.modules["readme_validation"] = readme_validation
_spec.loader.exec_module(readme_validation)


def test_readme_validation_section_matches_the_report():
    readme = readme_validation.README.read_text(encoding="utf-8")
    report = readme_validation.REPORT.read_text(encoding="utf-8")
    assert readme_validation.update(readme, readme_validation.render(report)) == readme, (
        "README.md is out of date: run python apps/api/scripts/readme_validation.py"
    )


def test_every_quoted_line_exists_verbatim_in_the_report():
    report = readme_validation.REPORT.read_text(encoding="utf-8").splitlines()
    block = readme_validation.render("\n".join(report)).splitlines()
    quoted = [line.removeprefix("> ") for line in block if line.startswith(("|", "- ", "> "))]
    assert quoted and all(line in report for line in quoted)


def test_a_missing_metric_fails_loudly():
    report = readme_validation.REPORT.read_text(encoding="utf-8")
    broken = "\n".join(line for line in report.splitlines() if not line.startswith("| Brier (half B)"))
    with pytest.raises(ValueError, match="Brier"):
        readme_validation.render(broken)
