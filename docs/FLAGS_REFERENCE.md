# Unified Flags & Metrics Reference

Authoritative matrix of command-line flags, environment variables, metrics, and state files for the SharePoint Downloader, OneLake Migrator, and End-to-End Orchestrator.

---
## 1. Components
| Component | Script | Purpose |
|-----------|--------|---------|
| Downloader (Turbo) | `src/sharepoint/dll_pdf_fabric_turbo.py` | High-speed parallel SharePoint file discovery + download with caching |
| Downloader (Standard) | `src/sharepoint/dll_pdf_fabric.py` | Sequential stable baseline (legacy) |
| Migrator (Optimized) | `src/fabric/onelake_migrator_turbo_fixed.py` | Adaptive streaming uploads to OneLake (hash + resume) |
| Orchestrator | `python -m onelake_migration.orchestration.orchestrator` | Chains downloader + migrator, produces consolidated run report |

---
## 2. Downloader Flags (Turbo)
| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--conservative` | mode switch | off | ~5 workers (safe) |
| `--normal` | mode switch | off | ~10 workers (balanced) |
| `--fast` | mode switch | off | ~15 workers (aggressive) |
| `--turbo` | mode switch | off | ~25 workers (max) |
| `--download-new-only` | bool | false | Skip files already fully downloaded (counts in `ignored_existing`) |
| `--limit N` | int | None | Cap number of files to download this run |
| `--refresh` | bool | false | Force re-scan ignoring valid cache |
| `--auto-refresh-if-limit-exceeds` | bool | false | If requested `--limit` > cached list size, automatically re-scan instead of truncating to cache |
| `--max-age HOURS` | int | 24 | Override max cache age before forced re-scan |
| `--clear-cache` | bool | false | Delete file list + progress caches then exit |
| `--validate-config` | bool | false | Dry validation of env + auth (no listing) |
| `--profile NAME` | str | default | Namespaces state under `.state/<profile>/downloader` |
| `--log-level LEVEL` | str | INFO | Override logging level |
| `--output-dir PATH` | str | from env | Local download path override |

Derived concurrency: chosen mode flag; default if none: `--conservative` equivalent.

---
## 3. Migrator Flags (Optimized)
| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--source PATH` | str | required | Local directory containing files |
| `--limit N` | int | None | Process only first N *new* files |
| `--resume / --no-resume` | bool | resume | Continue previous progress or start fresh in-place |
| `--reset-progress` | bool | false | Delete migrator progress + caches before run |
| `--enable-resume-chunks` | bool | false | Persist append offsets for large files (partial uploads) |
| `--precreate-dirs` | bool | false | Parallel directory pre-provision pass |
| `--chunk-size-bytes BYTES` | int | adaptive | Force override for chunk size |
| `--dry-run-metadata` | bool | false | List & compute stats only (no network writes) |
| `--fail-fast` | bool | false | Abort on first failure instead of accumulating |
| `--verbose` | bool | false | Detailed CREATE/APPEND/FLUSH logging |
| `--validate-config` | bool | false | Configuration/auth check only |
| `--profile NAME` | str | default | Namespaced state under `.state/<profile>/migrator` |

Adaptive chunk heuristic (bytes): <16MB→4MB, <128MB→8MB, <512MB→16MB, else 32MB.

---
## 4. Orchestrator Flags
| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--download-limit N` | int | None | Cap listed + downloaded files (passed to downloader) |
| `--upload-limit N` | int | None | Cap *new* successful uploads this run |
| `--download-mode {conservative,normal,fast,turbo}` | str | conservative | Downloader concurrency preset |
| `--download-new-only` | bool | false | Forwarded to downloader to skip existing local files |
| `--download-refresh` | bool | false | Force downloader to ignore its cached SharePoint listing (passes `--refresh`) |
| `--download-auto-refresh-if-limit-exceeds` | bool | false | Auto re-scan if `--download-limit` exceeds cached file_list length |
| `--download-max-age HOURS` | int | inherit (24) | Override downloader cache age threshold (passes `--max-age`) |
| `--skip-download` | bool | false | Skip downloader phase |
| `--skip-upload` | bool | false | Skip migrator phase |
| `--enable-resume-chunks` | bool | false | Forwarded to migrator |
| `--precreate-dirs` | bool | false | Forwarded to migrator |
| `--reset-progress` | bool | false | Reset migrator progress before upload phase |
| `--dry-run-metadata` | bool | false | Migrator dry run (no uploads) |
| `--force-continue` | bool | false | Continue remaining phase even if previous failed |
| `--report-json PATH` | str | None | Write consolidated run report |
| `--profile NAME` | str | default | Shared namespace for downloader/migrator state |
| `--verbose` | bool | false | Stream sub-process stdout/stderr |
| `--validate-config` | bool | false | Validate both phases & exit |

Upload limit semantics: counts only files whose upload completed this run (see `successful_this_run`).

---
## 5. Metrics (Downloader)
`last_run_summary.json` fields (namespaced):
| Field | Meaning |
|-------|---------|
| `total_files` | Total enumerated candidate files |
| `new_files_downloaded` | Successfully downloaded this run (new) |
| `skipped_existing` | Already present and re-validated (still counted in listing) |
| `ignored_existing` | Excluded due to `--download-new-only` mode |
| `failed_files` | Count of failures this run |
| `duration_sec` | Elapsed seconds |
| `mode` | Concurrency preset used |
| `profile` | Active profile namespace |

---
## 6. Metrics (Migrator Progress `migration_progress_optimized.json`)
| Field | Meaning |
|-------|---------|
| `completed_files` | Array of `{file, sha256, size}` objects (authoritative) |
| `failed_files` | Array of failure objects `{file, error, step, timestamp}` |
| `stats.total_files` | Total files discovered (snapshot at start) |
| `stats.processed_files` | Normalized to `len(completed_files) + len(failed_files)` after final prune |
| `stats.original_processed_files` | (New) Pre-normalization count (audit / debugging) |
| `stats.successful_uploads` | Total unique files ever successfully uploaded (== len(completed_files)) |
| `stats.successful_this_run` | (New) Number of new successful uploads in current execution |
| `stats.failed_uploads` | Count of failed files (length of `failed_files`) |
| `stats.uploaded_bytes` | Sum of sizes for completed files |
| `stats.total_bytes` | Aggregate target bytes of files considered |
| `stats.avg_upload_speed` | Calculated overall MB/sec for completed uploads |
| `context_hash` | Truncated hash of contextual identifiers (workspace, lakehouse, base path) |
| `schema_version` | Version string for progress schema validation |

Normalization ensures `processed_files` can no longer exceed the true canonical count after pruning meta/support entries.

---
## 7. Metrics (Orchestrator Run Report)
Top-level JSON structure (`--report-json`):
```json
{
  "download": {"success": true, "elapsed_sec": 4.21, "stats": {"new_files_downloaded": 10, "ignored_existing": 90}},
  "upload": {"success": true, "elapsed_sec": 18.52, "stats": {"successful_this_run": 10, "successful_uploads": 257}},
  "summary": {"profile": "default", "timestamp": "2025-09-10T12:34:56Z"}
}
```
If `--skip-upload` is used and prior stats reused, an additional marker: `"previous_upload_stats": true` may appear under `upload`.

---
## 8. State & File Layout
| File / Path | Component | Notes |
|-------------|-----------|-------|
| `.state/<profile>/downloader/file_list_cache.json` | Downloader | Cached SharePoint listing |
| `.state/<profile>/downloader/download_progress_turbo.json` | Downloader | Ongoing progress (turbo) |
| `.state/<profile>/downloader/last_run_summary.json` | Downloader | Persisted metrics snapshot |
| `.state/<profile>/migrator/migration_progress_optimized.json` | Migrator | Canonical upload state |
| `.state/<profile>/migrator/file_cache_optimized.json` | Migrator | Local source file cache |
| `.state/<profile>/migrator/dir_cache.json` | Migrator | Created directory cache |
| `.state/<profile>/migrator/partial_uploads.json` | Migrator | Ephemeral per-file offsets (removed post success) |
| `_archive_json/` | Migrator | Legacy / superseded JSONs (audit only) |

Pruning step removes transient/unsupported entries before final metric normalization.

---
## 9. Context Hash Invalidation
Both downloader and migrator embed a truncated SHA256 `context_hash` based on critical identifiers (site + drive + folder for downloader; workspace + lakehouse + base path for migrator). Mismatch during load triggers safe ignore/reset to prevent cross-environment contamination.

---
## 10. Common Usage Patterns
| Goal | Command |
|------|---------|
| Small smoke test end-to-end | `python -m onelake_migration.orchestration.orchestrator --download-limit 25 --upload-limit 25 --enable-resume-chunks --report-json run_smoke.json` |
| Download only (new files) | `python -m onelake_migration.orchestration.orchestrator --download-new-only --download-limit 100 --skip-upload` |
| Upload only (resume prior download) | `python -m onelake_migration.orchestration.orchestrator --skip-download --upload-limit 200 --enable-resume-chunks` |
| Fresh clean migrator run | `python -m onelake_migration.orchestration.orchestrator --skip-download --reset-progress --enable-resume-chunks` |
| Validate configuration only | `python -m onelake_migration.orchestration.orchestrator --validate-config --skip-download --skip-upload` |

---
## 11. Exit Codes (Validate Mode)
| Code | Meaning |
|------|---------|
| 0 | OK – configuration & auth valid |
| 1 | Missing or invalid configuration |
| 2 | Authentication / API failure |

---
## 12. Versioning & Schema
Progress files include `schema_version` (e.g., `1.1`). When bumped, loader archives incompatible prior schema under `_archive_json/` and regenerates fresh state.

---
## 13. Glossary
| Term | Definition |
|------|------------|
| `ignored_existing` | Locally present files explicitly skipped due to `--download-new-only` |
| `skipped_existing` | Already downloaded files encountered in standard mode (still counted in progress) |
| `successful_this_run` | New uploads completed in current migrator execution (bounded by `--upload-limit`) |
| `original_processed_files` | Pre-normalization processed count preserved for audit after pruning |
| `context_hash` | Fingerprint of operational context for safe cache reuse |

---
## 14. Recommended Validation Sequence
1. `--validate-config` (downloader, migrator, or orchestrator)  
2. Small `--limit` run with `--verbose`  
3. Increase `--download-limit` / `--upload-limit` gradually  
4. Monitor `successful_this_run` and ensure normalization (`processed_files == successful_uploads + failed_uploads`)  
5. Archive run reports for audit (`--report-json`).

---
## 15. Troubleshooting Signals
| Symptom | Likely Cause | Action |
|---------|--------------|--------|
| `processed_files` > completed + failed | Pre-normalization view | Open file post-run; final value should be normalized. If not, check pruning logs |
| `ignored_existing` always 0 | Not using `--download-new-only` | Add flag or remove duplicates manually |
| Reused upload stats flagged | `--skip-upload` used | Confirm intent; set upload limit if wanting incremental test |
| Slow throughput | Small chunk size or network | Override with `--chunk-size-bytes`; check bandwidth |
| Resumes not working | Missing flag or cleaned state | Add `--enable-resume-chunks`; verify `partial_uploads.json` present |
| Download limit < desired but cache caps at smaller number | Cached `file_list_cache.json` shorter than requested, no refresh | Re-run with `--download-refresh` (orchestrator) or downloader `--refresh`, or enable `--download-auto-refresh-if-limit-exceeds` |
| Cache not picking up new files within 24h | Newly added files but cache still valid | Use `--download-refresh` or lower `--download-max-age` (e.g., 1) |

---
**Last Updated:** 2025-09-10

---
## 16. Understanding `source_file_cache_mismatch`
The orchestrator adds this diagnostic block to the run report JSON when it detects a divergence between:

1. `source_file_cache_count` – raw count of entries in the migrator's `file_cache_optimized.json` (all items discovered under the source directory before filtering), and
2. `migration_stats.total_files` – the filtered count of files the migrator actually considered for upload (after excluding internal / non-content artifacts).

### Why it appears
| Trigger Scenario | What Happens | Typical Delta |
|------------------|--------------|---------------|
| Metadata & helper artifacts live alongside content (e.g. `file_list_cache.json`, `last_run_summary.json`) | Cache counts them; migrator excludes them | 1–5 |
| Temporary demo/test files (`.txt`, helper markers) present in source tree | Included in cache; excluded by extension filter or later pruning | Small (<10) |
| `--limit` lower than raw cache size | `total_files` reflects post-filter snapshot; cache shows full set | Potentially large, but usually you won't see a mismatch block unless non-content files also present (limit alone does not trigger) |
| Stale cache after adding new real files (no `--refresh` and age < max) | Cache missing new files OR includes removed ones | Variable (may be negative or positive) |
| Partial rebuild after `--reset-progress` but lingering old cache backup inspected | You compare different snapshots manually | Any |

### Interpreting the fields
```json
"source_file_cache_mismatch": {
  "cache_count": 1509,
  "migration_total_files": 1507,
  "delta": 2,
  "note": "Source directory has more files than migration stats recorded. Run with --reset-progress to rebuild cache if new downloads were added after initial scan."
}
```
* `delta` = `cache_count - migration_total_files`.
* A small positive delta made up only of known internal artifacts is benign.

### Common benign internal artifacts
| Path suffix | Reason excluded |
|-------------|-----------------|
| `file_list_cache.json` | Downloader listing cache (not to upload) |
| `last_run_summary.json` | Downloader metrics snapshot |
| `partial_uploads.json` | Resume bookkeeping (ephemeral) |
| Any `.txt` demo files under `data/downloads/demo/` | Example/test placeholders |

### When to take action
Act only if one of these is true:
1. `delta` is large AND not explained by internal artifacts (inspect non-PDF/non-target extensions).
2. You expect newly downloaded content files but they are missing from `migration_stats.total_files`.
3. `delta` negative (rare): indicates progress file thinks there are *more* files than raw cache—usually a stale or pruned cache; rebuild.

### Remediation steps
| Goal | Command / Action |
|------|------------------|
| Rebuild cache after adding/removing files | Add `--reset-progress` (migrator) or delete `.state/<profile>/migrator/file_cache_optimized.json` (last resort) |
| Force fresh SharePoint listing before upload | Use orchestrator `--download-refresh` (passes downloader `--refresh`) |
| Lower cache staleness window | `--download-max-age 1` (forces refresh after 1 hour) |
| Remove internal artifacts from source tree | Move them to a `.meta/` subfolder or clean demo files |
| Verify which entries are extra | Inspect `file_cache_optimized.json` (look for non-content extensions) |

### Suppressing false positives (roadmap suggestion)
Future improvement (optional): ignore a configurable pattern list (e.g. `*.json`, `*.txt`) when computing `source_file_cache_count`. Until implemented, keep internal artifacts outside the upload root if you want `delta = 0`.

### Quick decision guide
| Delta | Contains only known artifacts? | Action |
|-------|-------------------------------|--------|
| 0 | n/a | None |
| 1–5 | Yes | Ignore |
| 1–5 | No / unsure | Inspect cache file; confirm extensions |
| >5 | Mostly content | Run with `--reset-progress` + `--download-refresh` |
| Negative | n/a | Rebuild (`--reset-progress`) and re-run |

---
