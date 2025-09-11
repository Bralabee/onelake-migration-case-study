# Quick Start Scenarios

Practical, copy/paste examples showing how to combine the downloader, migrator, and orchestrator flags for common workflows.

> All commands assume you're in the project root and have activated the conda env (e.g. `conda activate onelake-migration`) and configured credentials in `.env` or profile env files.

## Setup & First Run (If You Haven't Already)

1. Create and activate environment (once):
```bash
conda env create -f environment.yml
conda activate onelake-migration
```
2. Copy template and populate credentials (tenant, client id/secret, workspace & lakehouse IDs):
```bash
cp .env.template .env   # or use your profile-specific env files under config/profiles/
```
3. (Optional) Use a profile for isolation (e.g. `prod`, `staging`). Create `config/profiles/prod.env` if needed.
4. Validate configuration (no data moved):
```bash
python -m onelake_migration.orchestration.orchestrator --validate-config --profile prod
```
5. Perform a smoke test (structure + reporting only):
```bash
python -m onelake_migration.orchestration.orchestrator --skip-download --skip-upload --profile prod --report-json smoke_report.json
```
6. Run a tiny sample end-to-end:
```bash
python -m onelake_migration.orchestration.orchestrator \
  --download-limit 10 \
  --upload-limit 10 \
  --download-new-only \
  --enable-resume-chunks \
  --profile prod \
  --report-json run_10.json
```
7. Inspect JSON report & state:
```
cat run_10.json | head
ls .state/prod/downloader .state/prod/migrator
```
8. Scale using the scenarios below (choose ramp-up, full corpus, or sync patterns).

Windows users: see `WINDOWS_QUICK_START.md` (now also in `docs/`) for PowerShell-specific setup and scenario equivalents.


## 1. Validate Configuration Only
Check auth + required env vars for both phases (no network file transfers):
```bash
python -m onelake_migration.orchestration.orchestrator --validate-config --profile prod
```
Expected: exit 0 on success; prints status for downloader + migrator.

## 2. Minimal Smoke (No Real Work)
End‑to‑end command structure & reporting without doing anything:
```bash
python -m onelake_migration.orchestration.orchestrator \
  --skip-download \
  --skip-upload \
  --report-json smoke_report.json \
  --profile prod
```
Use this to test CI integration and JSON report generation.

## 3. Small Download + Upload (Fresh Sample)
```bash
python -m onelake_migration.orchestration.orchestrator \
  --download-limit 25 \
  --upload-limit 25 \
  --download-mode normal \
  --enable-resume-chunks \
  --report-json run_25.json \
  --profile prod \
  --verbose
```
Purpose: Validate pipeline correctness on a bounded sample.

## 4. Large Listing – Force Fresh Re-scan
If a prior cached listing is too small (e.g., stuck at 250):
```bash
python -m onelake_migration.orchestration.orchestrator \
  --download-limit 1000 \
  --download-refresh \
  --download-new-only \
  --skip-upload \
  --profile prod \
  --report-json run_1000_refresh_only.json \
  --verbose
```
Why: Guarantees the SharePoint tree is re-enumerated; shows true scale before committing to uploads.

## 5. Adaptive Ramp-Up with Conditional Auto-Refresh
Grow sample size without always rescanning:
```bash
# First run (250)
python -m onelake_migration.orchestration.orchestrator --download-limit 250 --download-new-only --skip-upload --profile prod
# Increase limit (500) triggers auto-refresh if cache shorter
python -m onelake_migration.orchestration.orchestrator --download-limit 500 --download-new-only --download-auto-refresh-if-limit-exceeds --skip-upload --profile prod
# Final ramp (1000)
python -m onelake_migration.orchestration.orchestrator --download-limit 1000 --download-new-only --download-auto-refresh-if-limit-exceeds --skip-upload --profile prod
```
Tip: Add `--report-json run_<limit>.json` on each step for auditing.

## 6. Continuous Daily Sync (Stale Cache Threshold)
Treat listings older than 2 hours as stale:
```bash
python -m onelake_migration.orchestration.orchestrator \
  --download-limit 500 \
  --download-new-only \
  --download-max-age 2 \
  --upload-limit 500 \
  --enable-resume-chunks \
  --profile prod \
  --report-json run_sync.json
```
Outcome: Light re-scan cost when content changes; skip if cache still fresh.

## 7. Incremental Upload Only (Skip Download)
When downloads already done externally:
```bash
python -m onelake_migration.orchestration.orchestrator \
  --skip-download \
  --upload-limit 200 \
  --enable-resume-chunks \
  --precreate-dirs \
  --profile prod \
  --report-json run_upload_only.json
```

## 8. Resume Interrupted Large Upload
```bash
python -m onelake_migration.orchestration.orchestrator \
  --skip-download \
  --enable-resume-chunks \
  --upload-limit 300 \
  --profile prod \
  --verbose
```
Prereq: Previous run halted mid-transfer; `partial_uploads.json` still present under profile state.

## 9. Dry-Run Metadata Before Upload
List & size files, create no network writes:
```bash
python -m onelake_migration.orchestration.orchestrator \
  --skip-download \
  --dry-run-metadata \
  --profile prod \
  --report-json run_metadata_inspect.json
```
Use to sanity-check counts, byte totals, and projected duration.

## 10. Combined: Fresh Listing + Partial Upload
Download a large set but only upload first 150 new files:
```bash
python -m onelake_migration.orchestration.orchestrator \
  --download-limit 1000 \
  --download-refresh \
  --download-new-only \
  --upload-limit 150 \
  --enable-resume-chunks \
  --profile prod \
  --report-json run_1000_150_upload.json
```

## 11. Troubleshooting: Truncated Listing
Symptom: `total_listed` < requested limit, no errors, stable across runs.
Fix approaches:
```bash
# Force re-scan
python -m onelake_migration.orchestration.orchestrator --download-limit 800 --download-refresh --skip-upload
# Or conditional strategy
python -m onelake_migration.orchestration.orchestrator --download-limit 800 --download-auto-refresh-if-limit-exceeds --skip-upload
```

## 12. Multi-Profile Separation
Maintain isolated state for staging vs prod:
```bash
python -m onelake_migration.orchestration.orchestrator --download-limit 200 --profile staging --skip-upload
python -m onelake_migration.orchestration.orchestrator --download-limit 200 --profile prod --skip-upload
```
State paths: `.state/staging/...` vs `.state/prod/...`.

## 13. Quick Metrics Verification (No Upload)
```bash
python -m onelake_migration.orchestration.orchestrator --download-limit 300 --download-refresh --download-new-only --skip-upload --profile prod --report-json metrics_probe.json
jq '.download.stats' metrics_probe.json
```
(Use `jq` for quick field introspection.)

## 14. Clean Progress & Re-Benchmark Upload Throughput
```bash
python -m onelake_migration.orchestration.orchestrator \
  --skip-download \
  --reset-progress \
  --enable-resume-chunks \
  --upload-limit 400 \
  --profile perf \
  --report-json run_perf_clean.json
```
Purpose: Establish baseline without historical state influence.

## 15. Full Corpus Migration (All Remaining Files)
Download every new file and upload everything (no limits). Uses idempotent skips for already-processed files.
```bash
python -m onelake_migration.orchestration.orchestrator \
  --download-new-only \
  --enable-resume-chunks \
  --precreate-dirs \
  --profile prod \
  --report-json run_full_corpus.json \
  --verbose
```
Add a forced re-scan on the very first comprehensive run to avoid inheriting a truncated cache:
```bash
python -m onelake_migration.orchestration.orchestrator \
  --download-refresh \
  --download-new-only \
  --enable-resume-chunks \
  --precreate-dirs \
  --profile prod \
  --report-json run_full_corpus_refresh.json \
  --verbose
```
Notes:
* Omit `--upload-limit` to allow all remaining new files to transfer.
* Safe to re-run: previously uploaded files are skipped (not double-counted) while `successful_this_run` reflects only new ones.
* Pair with `--download-max-age 4` if running recurring multi-hour ingestion cycles.

## Flag Selection Cheat Sheet
| Goal | Key Flags |
|------|-----------|
| Force new SharePoint listing | `--download-refresh` |
| Conditional re-scan when scaling | `--download-auto-refresh-if-limit-exceeds` |
| Time-based staleness | `--download-max-age H` |
| Exclude already downloaded | `--download-new-only` |
| Bound sample size (download) | `--download-limit N` |
| Bound new uploads | `--upload-limit N` |
| Resume large file chunks | `--enable-resume-chunks` |
| Pre-create directories | `--precreate-dirs` |
| Metadata only (no upload) | `--dry-run-metadata` |
| Skip a phase | `--skip-download` / `--skip-upload` |
| Separate state/isolation | `--profile NAME` |

## Next Steps
1. Start with Scenario 3 or 4 depending on data volume.
2. Layer limits and refresh strategy that match audit / performance goals.
3. Integrate chosen command into CI and monitor JSON reports for invariants.


---
_Last updated: 2025-09-10_
