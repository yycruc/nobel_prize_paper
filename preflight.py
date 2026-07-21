"""Static preflight checks for the Nobel key-paper evidence-chain code package.

This tool performs no network access and does not modify analytical outputs.
"""

from __future__ import annotations

import importlib.util
import py_compile
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "03_scripts"
REQUIRED_DIRS = [
    ROOT / "03_scripts",
    ROOT / "docs",
    ROOT / "02_full_collection" / "01_raw_sources" / "public_datasets",
    ROOT / "02_full_collection" / "01_raw_sources" / "nobel_api",
    ROOT / "02_full_collection" / "01_raw_sources" / "nobel_official_pages",
    ROOT / "02_full_collection" / "02_candidate_key_papers",
    ROOT / "02_full_collection" / "03_matched_metadata",
    ROOT / "02_full_collection" / "05_outputs",
]
EXTERNAL_PACKAGES = ("openpyxl", "docx", "pypdf")


def main() -> int:
    errors: list[str] = []
    python_files = sorted(SCRIPTS.glob("*.py"))
    for path in REQUIRED_DIRS:
        if not path.is_dir():
            errors.append(f"missing directory: {path.relative_to(ROOT)}")
    if not python_files:
        errors.append("no Python scripts found in 03_scripts")
    for path in python_files:
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(f"syntax error: {path.name}: {exc.msg}")
    missing_packages = [name for name in EXTERNAL_PACKAGES if importlib.util.find_spec(name) is None]
    if missing_packages:
        errors.append("missing optional runtime packages: " + ", ".join(missing_packages))

    print(f"Python: {sys.version.split()[0]}")
    print(f"Python scripts checked: {len(python_files)}")
    if errors:
        print("PRECHECK FAILED")
        for item in errors:
            print(f"- {item}")
        return 1
    print("PRECHECK PASSED")
    print("Note: this check does not test network access, external source files, API limits, or manual-review decisions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
