"""Console script entrypoints.

These provide stable CLI commands via `pyproject.toml`:
- `onelake-download`
- `onelake-migrate`
- `onelake-orchestrate`

Today, downloader and migrator still live as script-style modules under `src/sharepoint/*`
and `src/fabric/*`. The orchestrator is importable as
`onelake_migration.orchestration.orchestrator`.

This module intentionally keeps the CLI thin while the codebase transitions to a
fully importable package structure.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DOWNLOADER = PROJECT_ROOT / "src" / "sharepoint" / "dll_pdf_fabric_turbo.py"
_MIGRATOR = PROJECT_ROOT / "src" / "fabric" / "onelake_migrator_turbo_fixed.py"


def _exec_script(path: Path) -> None:
    if not path.exists():
        print(f"Script not found: {path}", file=sys.stderr)
        raise SystemExit(2)
    runpy.run_path(str(path), run_name="__main__")


def download_main() -> None:
    """Entry point for `onelake-download`."""
    _exec_script(_DOWNLOADER)


def migrate_main() -> None:
    """Entry point for `onelake-migrate`."""
    _exec_script(_MIGRATOR)


def orchestrate_main() -> None:
    """Entry point for `onelake-orchestrate`."""
    try:
        from onelake_migration.orchestration.orchestrator import main as orchestrator_main

        raise SystemExit(orchestrator_main())
    except Exception:
        print(
            "orchestrator module not importable; please run: python -m onelake_migration.orchestration.orchestrator",
            file=sys.stderr,
        )
        raise SystemExit(2)
