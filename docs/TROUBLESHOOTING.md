# Troubleshooting Guide

Focused answers to common operational questions. See `FLAGS_REFERENCE.md` for exhaustive flag & metric definitions.

---
## 1. Why do I see `source_file_cache_mismatch` in the run report?
**Short answer:** The raw cache counted files the migrator intentionally excluded (metadata, helper, or filtered artifacts), or the cache is stale.

### Typical benign causes
| Cause | Example Entries | Notes |
|-------|-----------------|-------|
| Internal downloader artifacts | `file_list_cache.json`, `last_run_summary.json` | Not content to migrate |
| Demo / test placeholders | `data/downloads/demo/*.txt` | Safe to ignore or delete |
| Stale cache (no refresh) | Added new PDFs after last scan | Use `--download-refresh` |
| Progress reset delta | After `--reset-progress` but before fresh listing | Re-run orchestrator |

### How to confirm
1. Open `.state/<profile>/migrator/file_cache_optimized.json`.
2. Scan for non-target extensions (e.g. `.json`, `.txt`).
3. Compare `cache_count` vs `migration_stats.total_files`.
4. If delta equals number of internal artifacts → benign.

### Remediation options
| Goal | Action |
|------|--------|
| Rebuild migrator view entirely | Run with `--reset-progress` (orchestrator or migrator) |
| Force fresh SharePoint listing | Add `--download-refresh` |
| Reduce cache staleness window | `--download-max-age 1` (hours) |
| Eliminate mismatch altogether | Move internal JSON/TXT files to a `.meta/` subfolder |

### When to worry
- Delta large (>5) and entries are legitimate content (e.g. PDFs) missing from `total_files`.
- Negative delta (progress thinks more files exist than cache) – usually indicates manual tampering or partial cache write; rebuild.

### Quick checklist
- Small delta (<=5) & only internal artifacts → Ignore
- Large delta & content missing → Refresh + reset
- Persistent mismatch after reset → Inspect logs (`--verbose`) and ensure no filtering logic (extension rules) removed desired files

---
## 2. `processed_files` does not equal `successful_uploads + failed_uploads`
During run you might see a transient difference; at end it should be normalized. If still off:
1. Ensure run cleanly exited (exit_code 0).
2. Inspect `migration_progress_optimized.json` archives for earlier schema; stale copy may be viewed.
3. If corrupted, move file to `_archive_json/` and re-run with `--reset-progress`.

---
## 3. Download limit hit but fewer files uploaded
Possible reasons:
- `--upload-limit` lower than `--download-limit`.
- Many files already uploaded previously (see `successful_this_run`).
- Migrator filtered internal artifacts.

Remedy: Inspect run report `summary.migration_stats` and cache file for difference sources.

---
## 4. Resume not picking up large partial uploads
Check `partial_uploads.json` exists during upload. If absent:
- Add `--enable-resume-chunks`.
- Confirm no cleanup script removed it mid-run.

---
## 5. Slow throughput
- Network throttling: Try fewer workers (downloader modes) or adjust chunk size.
- Very large file skew: Increase workers; enable chunk resume to avoid full restarts.

---
## 6. Clean-room rerun procedure
1. Stop all runs.
2. Backup `.state/<profile>/` if needed.
3. Delete migrator cache + progress JSONs OR run with `--reset-progress`.
4. Run orchestrator with `--download-refresh --download-limit N --upload-limit N`.

---
**Last Updated:** 2025-09-11
