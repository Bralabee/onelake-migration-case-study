# Windows Quick Start (PowerShell)

Dedicated guide for Windows / PowerShell usage of the SharePoint → OneLake migration toolkit.

> Use PowerShell 7+ where possible. Replace backtick continuations with line breaks if pasting into legacy consoles.

## 1. Environment Setup
```powershell
# Create environment (first time)
conda env create -f environment.yml
# Activate
conda activate onelake-migration
```

## 2. Configuration
```powershell
# Copy template .env (if present)
if (Test-Path .env.template) { Copy-Item .env.template .env -Force }

# (Optional) Profile-specific env file for prod
if (!(Test-Path config/profiles)) { New-Item -ItemType Directory -Path config/profiles | Out-Null }
Copy-Item .env config/profiles/prod.env -Force
```
Populate required values inside `.env` or `config/profiles/prod.env`:
```
TENANT_ID=...
CLIENT_ID=...
CLIENT_SECRET=...
FABRIC_WORKSPACE_ID=...
FABRIC_LAKEHOUSE_ID=...
ONELAKE_BASE_PATH=/Files/SharePoint_Invoices
```

## 3. Validate Configuration
```powershell
python -m onelake_migration.orchestration.orchestrator --validate-config --profile prod
```
Expect success message and exit code 0.

## 4. Smoke Test (No Work Performed)
```powershell
python -m onelake_migration.orchestration.orchestrator `
  --skip-download `
  --skip-upload `
  --profile prod `
  --report-json smoke_report.json
```
`smoke_report.json` should contain download/upload placeholders with success flags.

## 5. Small Sample Run (10 Files)
```powershell
python -m onelake_migration.orchestration.orchestrator `
  --download-limit 10 `
  --upload-limit 10 `
  --download-new-only `
  --enable-resume-chunks `
  --profile prod `
  --report-json run_10.json `
  --verbose
```
Inspect outputs:
```powershell
type run_10.json
```

## 6. Larger Listing With Forced Refresh
```powershell
python -m onelake_migration.orchestration.orchestrator `
  --download-limit 1000 `
  --download-refresh `
  --download-new-only `
  --skip-upload `
  --profile prod `
  --report-json run_1000_refresh_only.json `
  --verbose
```
Purpose: re-enumerates full SharePoint tree ignoring stale cache.

## 7. Adaptive Ramp-Up (Conditional Auto-Refresh)
```powershell
python -m onelake_migration.orchestration.orchestrator --download-limit 250 --download-new-only --skip-upload --profile prod
python -m onelake_migration.orchestration.orchestrator --download-limit 500 --download-new-only --download-auto-refresh-if-limit-exceeds --skip-upload --profile prod
python -m onelake_migration.orchestration.orchestrator --download-limit 1000 --download-new-only --download-auto-refresh-if-limit-exceeds --skip-upload --profile prod
```
Only rescans when requested limit exceeds cached list size.

## 8. Continuous Sync (Time-Based Cache Staleness)
```powershell
python -m onelake_migration.orchestration.orchestrator `
  --download-limit 500 `
  --download-new-only `
  --download-max-age 2 `
  --upload-limit 500 `
  --enable-resume-chunks `
  --profile prod `
  --report-json run_sync.json
```
Listing cache older than 2 hours triggers a refresh.

## 9. Resume Interrupted Upload
```powershell
python -m onelake_migration.orchestration.orchestrator `
  --skip-download `
  --enable-resume-chunks `
  --upload-limit 300 `
  --profile prod `
  --verbose
```
Relies on presence of partial upload state file.

## 10. Dry-Run Metadata (No Upload)
```powershell
python -m onelake_migration.orchestration.orchestrator `
  --skip-download `
  --dry-run-metadata `
  --profile prod `
  --report-json run_metadata_inspect.json
```
Check size totals & file counts without network writes.

## 11. Partial Upload After Large Listing
```powershell
python -m onelake_migration.orchestration.orchestrator `
  --download-limit 1000 `
  --download-refresh `
  --download-new-only `
  --upload-limit 150 `
  --enable-resume-chunks `
  --profile prod `
  --report-json run_1000_150_upload.json
```

## 12. Full Corpus Migration (Idempotent)
```powershell
python -m onelake_migration.orchestration.orchestrator `
  --download-new-only `
  --enable-resume-chunks `
  --precreate-dirs `
  --profile prod `
  --report-json run_full_corpus.json `
  --verbose
```
Repeat run skips already uploaded files; `successful_this_run` reflects only new additions.

## 13. Full Corpus (First Run With Refresh)
```powershell
python -m onelake_migration.orchestration.orchestrator `
  --download-refresh `
  --download-new-only `
  --enable-resume-chunks `
  --precreate-dirs `
  --profile prod `
  --report-json run_full_corpus_refresh.json `
  --verbose
```

## 14. Troubleshooting Truncated Listing
If `total_listed` < requested limit and stable:
```powershell
python -m onelake_migration.orchestration.orchestrator --download-limit 800 --download-refresh --skip-upload --profile prod
# or
python -m onelake_migration.orchestration.orchestrator --download-limit 800 --download-auto-refresh-if-limit-exceeds --skip-upload --profile prod
```

## 15. Clean Progress & Throughput Benchmark
```powershell
python -m onelake_migration.orchestration.orchestrator `
  --skip-download `
  --reset-progress `
  --enable-resume-chunks `
  --upload-limit 400 `
  --profile perf `
  --report-json run_perf_clean.json
```

## Cheat Sheet
| Goal | Key Flags |
|------|-----------|
| Force new listing | `--download-refresh` |
| Conditional re-scan | `--download-auto-refresh-if-limit-exceeds` |
| Age-based staleness | `--download-max-age H` |
| Only new local files | `--download-new-only` |
| Bound download sample | `--download-limit N` |
| Bound new uploads | `--upload-limit N` |
| Resume large uploads | `--enable-resume-chunks` |
| Pre-create directories | `--precreate-dirs` |
| Metadata only | `--dry-run-metadata` |
| Skip a phase | `--skip-download` / `--skip-upload` |
| Profile namespace | `--profile NAME` |

## Suggested Path
1. Validate → Smoke → Small sample.
2. Large listing (refresh) to size corpus.
3. Partial upload or full corpus depending on scope.
4. Schedule recurring sync with time-based cache policy.

---
_Last updated: 2025-09-10_
