# onelake_migration Package Restructure (Phase 1)

This repository is transitioning from mixed loose scripts + `src_pkg/` to a single coherent package under `src/onelake_migration/`.

## Phase 1 (Completed)
- Created new package root: `src/onelake_migration/`
- Added subpackage placeholders: `sharepoint/`, `migrator/`, `orchestration/`, `diagnostics/`
- Adjusted `pyproject.toml` to point setuptools to `src/`
- Left existing console entrypoints (`onelake-download`, etc.) pointing to legacy scripts via runpy
- Added transitional note to old `src_pkg/onelake_migration/cli.py`
- Introduced internal module `onelake_migration.orchestration.orchestrator` and deprecated root script wrapper

### New Invocation (Preferred)
```
conda run -n onelake-migration python -m onelake_migration.orchestration.orchestrator --help
```
or after install:
```
onelake-orchestrate --help
```

## Next Phases
1. Migrate core downloader & migrator logic into structured modules.
2. Refactor orchestrator into `orchestration/orchestrator.py` exposing a callable used by CLI.
3. Replace runpy execution with direct imports for faster startup & easier testing.
4. Provide deprecation stubs in old top-level scripts printing guidance.
5. Update documentation & examples.

## Rollback
Revert `pyproject.toml` change and remove the new `src/onelake_migration/` directory.

## Notes
During the transition both `src_pkg/onelake_migration` and `src/onelake_migration` coexist; only the latter will accumulate new code.
