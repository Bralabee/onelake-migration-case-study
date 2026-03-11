"""Legacy console script entrypoints (compat shim).

This file exists only for transitional compatibility with the older `src_pkg/` layout.
The canonical CLI now lives at `src/onelake_migration/cli.py`.

These wrappers forward to the new CLI when possible.
"""

from __future__ import annotations

import importlib.util
import runpy
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
NEW_CLI_PATH = PROJECT_ROOT / "src" / "onelake_migration" / "cli.py"

_FALLBACK_DOWNLOADER = PROJECT_ROOT / "src" / "sharepoint" / "dll_pdf_fabric_turbo.py"
_FALLBACK_MIGRATOR = PROJECT_ROOT / "src" / "fabric" / "onelake_migrator_turbo_fixed.py"


def _exec_script(path: Path) -> None:
    if not path.exists():
        print(f"Script not found: {path}", file=sys.stderr)
        raise SystemExit(2)
    runpy.run_path(str(path), run_name="__main__")


def _load_new_cli():
    if not NEW_CLI_PATH.exists():
        return None
    spec = importlib.util.spec_from_file_location("_onelake_migration_cli", NEW_CLI_PATH)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def download_main() -> None:  # onelake-download
    cli = _load_new_cli()
    if cli is not None:
        return cli.download_main()
    _exec_script(_FALLBACK_DOWNLOADER)


def migrate_main() -> None:  # onelake-migrate
    cli = _load_new_cli()
    if cli is not None:
        return cli.migrate_main()
    _exec_script(_FALLBACK_MIGRATOR)


def orchestrate_main() -> None:  # onelake-orchestrate
    cli = _load_new_cli()
    if cli is not None:
        return cli.orchestrate_main()
    print(
        "orchestrator module not importable; please run: python -m onelake_migration.orchestration.orchestrator",
        file=sys.stderr,
    )
    raise SystemExit(2)
