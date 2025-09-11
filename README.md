# OneLake Migration Case Study – Optimized Migrator

High‑performance async tool for migrating downloaded SharePoint (or other local) files into Microsoft Fabric OneLake (Delta Lakehouse `Files/` area) with:

* Chunked streaming uploads (adaptive chunk sizing)
* Resumable partial uploads (offset persistence per file)
* Directory pre‑creation cache & persistent `dir_cache.json`
* Hash integrity (SHA256) recorded per completed file
* Profile‑namespaced progress under `.state/<profile>/migrator/migration_progress_optimized.json`
* Partial upload state in `partial_uploads.json`
* Throughput metrics (files/sec, MB/sec, plus `successful_this_run` for current run)
* Verbose per‑step CREATE/APPEND/FLUSH logging (optional)
* Normalized processed count (`processed_files` adjusted post-prune; raw pre-normalization retained as `original_processed_files`)

## Key Files

| File | Purpose |
|------|---------|
| `src/fabric/onelake_migrator_turbo_fixed.py` | Core migrator implementation |
| `sharepoint_downloader.py` (if present) | Fetch initial source files from SharePoint |
| `.state/<profile>/migrator/migration_progress_optimized.json` | Completed & failed file tracking + stats (namespaced) |
| `partial_uploads.json` | Resume offsets for in‑progress large files |
| `dir_cache.json` | Persisted set of already created OneLake directories |
| `file_cache_optimized.json` | Source file discovery cache |
| `_archive_json/` | Archived legacy & duplicate JSON state (production, working, corrupted) |
| `environment.yml` | Conda environment specification (use existing) |
| `tests/test_migrator_adaptive_and_hash.py` | Unit tests for adaptive chunking & hash persistence |

## Environment Setup (Conda)

Use the provided `environment.yml` (already in repo):

```bash
conda env create -f environment.yml  # first time
conda activate aca_taskforce_env
conda env update -f environment.yml  # later updates
```

## Required Environment Variables (.env)

```
TENANT_ID=
CLIENT_ID=
CLIENT_SECRET=
FABRIC_WORKSPACE_ID=
FABRIC_LAKEHOUSE_ID=
ONELAKE_BASE_PATH=/Files/SharePoint_Invoices   # optional override
FABRIC_ACCESS_TOKEN= (optional pre-fetched)
```

## Running the Migrator

Basic run (resume by default):
```bash
python src/fabric/onelake_migrator_turbo_fixed.py --source ./data/downloads --limit 10 --verbose
```

Fresh run ignoring cached progress:
```bash
python src/fabric/onelake_migrator_turbo_fixed.py --source ./data/downloads --reset-progress
```

## End-to-End Orchestrator (Download + Upload)

Preferred options:
- Python module path: `python -m onelake_migration.orchestration.orchestrator [args]`
- CLI entrypoint (after editable install): `onelake-orchestrate [args]`

Smoke (skip phases, CI friendly):
```bash
python -m onelake_migration.orchestration.orchestrator --skip-download --skip-upload --report-json smoke_report.json
```

Download 100 then upload 100 (normal mode):
```bash
python -m onelake_migration.orchestration.orchestrator \
	--download-limit 100 \
	--upload-limit 100 \
	--download-mode normal \
	--enable-resume-chunks \
	--report-json run_100.json \
	--verbose
```

PowerShell variant:
```powershell
python -m onelake_migration.orchestration.orchestrator `
	--download-limit 100 `
	--upload-limit 100 `
	--download-mode turbo `
	--precreate-dirs `
	--enable-resume-chunks `
	--report-json run_100.json `
	--verbose
```

Key Flags (see also `docs/FLAGS_REFERENCE.md` for full matrix):
| Flag | Purpose |
|------|---------|
| `--download-limit N` | Cap files listed & downloaded |
| `--upload-limit N` | Cap number of newly uploaded files (post-change semantics) |
| `--download-mode {conservative,normal,fast,turbo}` | Downloader concurrency presets |
| `--download-new-only` | Downloader: skip already-downloaded local files (counted as `ignored_existing`) |
| `--skip-download` | Skip download phase |
| `--skip-upload` | Skip upload phase |
| `--reset-progress` | Force clean progress before upload |
| `--enable-resume-chunks` | Resumable append logic |
| `--precreate-dirs` | Pre-create OneLake directories |
| `--dry-run-metadata` | Uploader lists only, no network writes |
| `--force-continue` | Continue even if a phase fails |
| `--report-json PATH` | Emit structured run report |
| `--verbose` | Stream underlying script output |

Report excerpt:
```json
{
	"download": {"success": true, "elapsed_sec": 3.2},
	"upload": {"success": true, "elapsed_sec": 11.0},
	"summary": {"migration_stats": {"successful_uploads": 101, "total_files": 101}}
}
```

### Updated Limit & New Metrics (Uploader & Downloader)
`--upload-limit` (or migrator `--limit`) counts only *new* successful uploads this run. Metric `successful_this_run` records the delta; already completed files are skipped without consuming the allowance. Downloader `--download-new-only` introduces `ignored_existing` so intentional skips are distinguished from simple cache hits (`skipped_existing`).

Tip: Pair `--download-limit` and `--upload-limit` for bounded smoke tests.

## Quick Start: Large Sample Validation

Run a high-speed bounded listing & download (skipping upload) to validate scale and concurrency. Force a fresh SharePoint re-scan to avoid truncated cached listings:

```bash
python -m onelake_migration.orchestration.orchestrator \
	--download-limit 1000 \
	--download-mode turbo \
	--download-new-only \
	--download-refresh \
	--skip-upload \
	--profile prod \
	--report-json run_1000_refresh_only.json \
	--verbose
```

Prefer conditional refresh instead of always forcing it? Replace `--download-refresh` with:

```bash
--download-auto-refresh-if-limit-exceeds
```

This triggers a re-scan only when your requested `--download-limit` exceeds the size of the cached file list.

If you expect frequent new files during the day, add:

```bash
--download-max-age 1
```

to treat listings older than 1 hour as stale.

### Downloader Cache-Control Flags (via Orchestrator)

| Flag | Purpose |
|------|---------|
| `--download-refresh` | Force ignore cached SharePoint file listing and re-scan now. |
| `--download-auto-refresh-if-limit-exceeds` | Auto re-scan when requested limit > cached listing length. |
| `--download-max-age HOURS` | Treat cache as stale after HOURS (default 24) and re-scan. |

Symptom & Fix: If `total_listed` stays stuck at (e.g.) 250 while requesting 500+ with no errors, the cache is simply shorter—add `--download-refresh` or the conditional auto-refresh flag.

➡️ For a broader set of 15 practical scenarios (validation, ramp-up, full corpus migration, conditional refresh, incremental sync, resume, dry-run, troubleshooting), see [Quick Start Scenarios](docs/quick_start.md). Windows users: see [Windows Quick Start](docs/WINDOWS_QUICK_START.md).


## Command Line Flags

| Flag | Description |
|------|-------------|
| `--source` | Local source directory of files to upload |
| `--resume/--no-resume` | Continue previous run (default True) |
| `--limit N` | Process only first N files (smoke test) |
| `--reset-progress` | Delete existing progress / caches for a clean run |
| `--verbose` | Detailed CREATE/APPEND/FLUSH and DIR logs |
| `--fail-fast` | Abort on first failure |
| `--dry-run-metadata` | No uploads; only scans & reports stats |
| `--enable-resume-chunks` | Persist per-file append offset in `partial_uploads.json` |
| `--precreate-dirs` | Parallel pre-scan & create directory structure before uploads |
| `--chunk-size-bytes` | Force chunk size override (bytes). Otherwise adaptive heuristic |

## Adaptive Chunk Sizing
Heuristic (when not overridden):

| File Size | Chunk Size |
|-----------|------------|
| < 16MB | 4MB |
| < 128MB | 8MB |
| < 512MB | 16MB |
| ≥ 512MB | 32MB |

Override via `--chunk-size-bytes` or env `CHUNK_SIZE_BYTES`.

## Resumable Partial Uploads

When `--enable-resume-chunks` is set:
* Each successful append advances the stored offset (on transient or non-terminal failure).
* State stored in `partial_uploads.json` – you can delete this file to force full re-upload.
* On success the entry is removed and SHA256 is logged in progress.

## Integrity Hash Recording

Each completed file stores `{file, sha256, size}` inside the namespaced progress file under `completed_files`. This can be used for downstream validation (e.g., verifying parity with source store).

## Progress File Structure (Excerpt)
```json
{
	"completed_files": [
		{"file": "invoices/2025/Jan/doc1.pdf", "sha256": "...", "size": 123456}
	],
	"failed_files": [
		{"file": "bad.bin", "error": "HTTP 500", "step": "append", "timestamp": "2025-09-10T12:34:56"}
	],
	"stats": {
		"total_files": 10,
		"processed_files": 10,
		"successful_uploads": 10,
		"failed_uploads": 0,
		"avg_upload_speed": 7.2,
		"uploaded_bytes": 104857600,
		"total_bytes": 104857600,
		"start_time": "...",
		"end_time": "..."
	}
}
```

## Throughput Metrics
Final log line includes files/sec and MB/sec computed from `uploaded_bytes` and elapsed wall time.

## Directory Creation Strategy
* Incremental creation with cache to avoid redundant round-trips.
* Optional pre-creation pass (`--precreate-dirs`) parallelizes directory provisioning for large trees.

## Authoritative JSON State

Active authoritative JSON files (post-normalization pass):
* `.state/<profile>/migrator/migration_progress_optimized.json` – canonical progress + stats (SHA256 + size per file; includes `successful_this_run`, normalized `processed_files`, and `original_processed_files`)
* `file_cache_optimized.json` – cached source file listing
* `dir_cache.json` – created directory cache
* `partial_uploads.json` – ephemeral resume state (present only while large files mid-upload)

Archived under `_archive_json/` (retained for audit, not used by current code):
* `migration_progress_production*.json` (legacy schema)
* `migration_progress_working.json` (transitional)
* `migration_progress_production_corrupted.json` (forensics)
* Duplicate `data/` copies formerly used during reorganization
* `onelake_directories.json` snapshot & `migration_analysis.json` (historical planning)

Rationale: reduce ambiguity, prevent dashboards from ingesting obsolete schemas, keep reversible audit trail.

## Profiles & Namespaced State

Use `--profile <name>` on downloader, migrator, or orchestrator to isolate cache & progress. Layout:

```
.state/<profile>/downloader/download_progress_turbo.json
.state/<profile>/downloader/file_list_cache.json
.state/<profile>/migrator/migration_progress_optimized.json
.state/<profile>/migrator/file_cache_optimized.json
.state/<profile>/migrator/dir_cache.json
.state/<profile>/migrator/partial_uploads.json
```

Legacy root-level progress/cache files are auto-imported on first run for backward compatibility.

## Context Hash Invalidation

Downloader cache and migrator progress embed a truncated SHA256 `context_hash` (site/drive/folder or workspace/lakehouse/base path). Mismatch => cache/progress ignored to avoid cross-environment contamination.

## Validation Mode & Integrity Checks

Lightweight configuration/auth checks (no file transfers):

```
python src/sharepoint/dll_pdf_fabric_turbo.py --validate-config
python src/fabric/onelake_migrator_turbo_fixed.py --validate-config
python -m onelake_migration.orchestration.orchestrator --validate-config --profile prod
```

Exit codes: 0=OK, 1=missing config, 2=auth/API failure.

## Testing
Run unit tests (after activating conda env):
```bash
pytest -q onelake-migration-case-study/tests
```
Focus areas covered: adaptive chunk sizing, streaming generator behavior, hash persistence.

## Operational Tips
* If progress shows 0 remaining but you added new files, delete `file_cache_optimized.json` to force re-scan.
* Use `--download-new-only` in the downloader/orchestrator to exclude already-downloaded files (`ignored_existing` metric).
* After each run verify: `processed_files == successful_uploads + failed_uploads` (normalization occurs at end of run if pruning removed meta entries).
* Use `--limit` in early validation to ensure directory structure & auth are correct before full runs.
* For very large single files you can raise `--chunk-size-bytes` (e.g., 67108864 for 64MB) but watch memory & network variability.

## Future Enhancements (Candidates)
## Deleting State JSON Files – Effects & Safe Alternatives

| File | Safe to Delete? | Immediate Effect | Risk / Side Effect | Preferred Alternative |
|------|-----------------|------------------|--------------------|-----------------------|
| `.state/<profile>/downloader/file_list_cache.json` | Yes | Forces fresh SharePoint re-scan next run (slower startup) | None (just time) | Use orchestrator `--download-refresh` or `--download-auto-refresh-if-limit-exceeds` |
| `.state/<profile>/downloader/last_run_summary.json` | Yes | Loses last downloader metrics snapshot | Historical metrics gap | Keep; new run overwrites anyway |
| `.state/<profile>/migrator/file_cache_optimized.json` | Yes (caution) | Rebuilt by scanning local source tree | Minor delay; if local files removed they disappear from scope | Use `--reset-progress` (archives + rebuild) |
| `.state/<profile>/migrator/migration_progress_optimized.json` | Not recommended | Loses record of completed uploads; migrator may attempt to re-upload everything | Duplicate uploads / wasted bandwidth (unless server idempotent) | Use `--reset-progress` to archive then start clean |
| `.state/<profile>/migrator/partial_uploads.json` | Only after success | Large in‑flight files lose resume offsets (restart from 0) | Time & bandwidth waste on big files | Leave until run completes (`--enable-resume-chunks`) |
| `.state/<profile>/migrator/dir_cache.json` | Yes | Directories re-created (extra 201/409 chatter) | Small overhead | Leave; harmless if removed |
| `_archive_json/*.json` | Keep for audit | None (unused by current code) | Lose forensic history | Prune only if storage constrained |

### Recommended Clean Reset
Instead of manual deletion:
```bash
python -m onelake_migration.orchestration.orchestrator --skip-download --reset-progress --profile prod
```
This archives existing migrator progress & cache, then rebuilds predictably.

### When You Might Intentionally Delete
| Scenario | Justification |
|----------|---------------|
| Corrupted progress JSON (unparseable) | Force regeneration; archive corrupt copy first |
| Massive directory refactor of source tree | Old cache paths invalid; rebuild for accuracy |
| Privacy scrub (remove file names from disk) | Archive, then securely delete state after compliance export |

### Quick Decision Flow
1. Need fresh listing? Use `--download-refresh` (avoid manual delete).
2. Need full clean migrator state? `--reset-progress`.
3. Only large-file resumes failing? Ensure `--enable-resume-chunks`; don't delete `partial_uploads.json` mid-run.
4. Unsure: back up `.state/<profile>/` before any manual removal.

See `docs/TROUBLESHOOTING.md` and section 16 of `docs/FLAGS_REFERENCE.md` for `source_file_cache_mismatch` explanation related to internal artifact counts.
* Parallel hash verification against source manifest
* Optional CRC32C alongside SHA256 for faster integrity checks
* Multi-process batching for CPU-bound pre-processing
* Structured JSON logging / OpenTelemetry hooks

## Retry & Backoff Strategy

| Component | Transient Status Codes | Max Attempts (default) | Base Delay | Backoff |
|-----------|-----------------------|------------------------|-----------|---------|
| Migrator (create/append/flush) | 408,429,500,502,503,504 | 5 (`RETRY_MAX_ATTEMPTS`) | 1.0s (`RETRY_BASE_DELAY_SECONDS`) | exponential + jitter (30%) |
| Downloader | Includes 429 + network timeouts | Library Retry config | library default | urllib3 exponential |

Formula: `delay = base * 2^(attempt-1) + random(0, 0.3 * base * 2^(attempt-1))`

Notes:
* On transient APPEND/FLUSH with resume enabled, current offset persisted to `partial_uploads.json`.
* Token proactively refreshed ~5 min before expiry.
* Failures after max attempts recorded in `failed_files` with truncated response body.

Env overrides: `RETRY_MAX_ATTEMPTS`, `RETRY_BASE_DELAY_SECONDS`.

---
Maintained as part of the broader Fabric ingestion case study. See `docs/FLAGS_REFERENCE.md` for exhaustive flag & metric definitions. Update this README when adding new flags or stats fields.
