#!/usr/bin/env python3
"""Deprecated wrapper. Do not use.

This script has been replaced by the module-path orchestrator. Run:

    python -m onelake_migration.orchestration.orchestrator [args]

or the installed entrypoint `onelake-orchestrate`.

This wrapper now exits with an error to prevent accidental use.
"""

import sys

if __name__ == "__main__":  # pragma: no cover
    sys.stderr.write(
        "orchestrate_onelake_migration.py is deprecated. "
        "Use 'python -m onelake_migration.orchestration.orchestrator' instead.\n"
    )
    raise SystemExit(2)
