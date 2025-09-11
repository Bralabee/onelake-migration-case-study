"""Console script entrypoints (transitional).

Phase 1: still executes legacy script files via runpy.
Future phase: will import internal modules from src/onelake_migration/*
and deprecate direct script execution.
"""
from __future__ import annotations
import runpy
import sys
from pathlib import Path

try:
    from onelake_migration.orchestration.orchestrator import main as orchestrator_main  # type: ignore
except Exception:  # module may not be on path yet during initial install
    orchestrator_main = None

ROOT = Path(__file__).resolve().parent.parent.parent  # project root (legacy src_pkg path)

# Map to original script paths
_DOWNLOADER = ROOT / "src" / "sharepoint" / "dll_pdf_fabric_turbo.py"
_MIGRATOR = ROOT / "src" / "fabric" / "onelake_migrator_turbo_fixed.py"
_ORCHESTRATOR = None  # Deprecated wrapper removed; prefer module path orchestrator

def _exec_script(path: Path):
    if not path.exists():
        print(f"Script not found: {path}", file=sys.stderr)
        raise SystemExit(2)
    # Emulate running as __main__
    runpy.run_path(str(path), run_name="__main__")

def download_main():  # onelake-download
    _exec_script(_DOWNLOADER)

def migrate_main():  # onelake-migrate
    _exec_script(_MIGRATOR)

def orchestrate_main():  # onelake-orchestrate
    if orchestrator_main:
        raise SystemExit(orchestrator_main())
    print("orchestrator module not importable; please run: python -m onelake_migration.orchestration.orchestrator", file=sys.stderr)
    raise SystemExit(2)
