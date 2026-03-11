# 🏗️ Microsoft Fabric OneLake Migration Setup Guide

## Overview
This guide helps you migrate your downloaded SharePoint files to Microsoft Fabric OneLake for advanced analytics.

## Prerequisites

### 1. Microsoft Fabric Access
- ✅ Microsoft Fabric license (Premium or Fabric capacity)
- ✅ Access to a Fabric workspace
- ✅ Permission to create Lakehouses

### 2. Required Information
You need to gather the following IDs from your Fabric environment:

#### Fabric Workspace ID
1. Go to [Microsoft Fabric Portal](https://app.fabric.microsoft.com)
2. Navigate to your workspace
3. Copy the workspace ID from the URL: `https://app.fabric.microsoft.com/groups/{WORKSPACE_ID}/`

#### Fabric Lakehouse ID  
1. In your Fabric workspace, create or navigate to a Lakehouse
2. Copy the Lakehouse ID from the URL: `https://app.fabric.microsoft.com/groups/{WORKSPACE_ID}/items/{LAKEHOUSE_ID}`

## Configuration Steps

### Step 1: Update .env File
Add your Fabric details to the `.env` file:

```properties
# Microsoft Fabric OneLake Configuration
FABRIC_WORKSPACE_ID=12345678-1234-1234-1234-123456789abc
FABRIC_LAKEHOUSE_ID=87654321-4321-4321-4321-cba987654321
ONELAKE_BASE_PATH=/Files/SharePoint_Invoices
DELTA_TABLE_NAME=sharepoint_invoices
```

### Step 2: App Registration Permissions
Your existing Azure AD app registration needs additional permissions for Fabric:

1. Go to [Azure Portal](https://portal.azure.com) → App Registrations
2. Find your app: `74ab6fe0-38a7-45c4-8fe4-512e5dc28a85`
3. Add API permissions:
   - **Power BI Service** → Application permissions → `App.ReadWrite.All`
   - **Microsoft Graph** → Application permissions → `Files.ReadWrite.All`

### Step 3: Test Migration
Run the analysis first to understand your data:

```bash
# Analyze files only (no migration)
conda run -n onelake-migration python src/fabric/onelake_migrator.py --analyze-only --source "C:/commercial_pdfs/downloaded_files"
```

## Migration Features (Optimized Uploader)

### 🔍 File & Scope Analysis
* File inventory (count, cumulative bytes, type distribution)
* Storage cost estimation (standard vs archive tiers)
* Migration duration forecasts (adaptive based on historical MB/sec)

### 📊 Metadata & Integrity
* File properties (relative path, size, modified time)
* SHA256 hash computed during streaming (no extra file pass)
* Optional document classification (if downstream classifier enabled)
* Folder structure preservation (mirrors local hierarchy under `ONELAKE_BASE_PATH`)

### 🚀 High-Performance Streaming Uploads
* Adaptive chunked streaming (4MB–32MB heuristic) – overrides via `--chunk-size-bytes`
* Resumable partial uploads (persisted offsets in `partial_uploads.json`)
* Automatic directory creation with cache + optional pre-creation pass
* Robust retry (exponential backoff + jitter for 408/429/5xx)
* Flush-after-final-chunk semantics using OneLake append/flush REST pattern

### 🧠 Adaptive Chunk Logic
| File Size | Default Chunk |
|-----------|---------------|
| < 16MB | 4MB |
| < 128MB | 8MB |
| < 512MB | 16MB |
| ≥ 512MB | 32MB |

### 📈 Progress & Metrics (Normalized)
`migration_progress_optimized.json` (namespaced under `.state/<profile>/migrator/`) stores:
- `completed_files`: array of `{file, sha256, size}` (authoritative successful uploads)
- `failed_files`: `{file, error, step, timestamp}` entries
- `stats` object (fields):
    - `total_files`: snapshot of discovered candidates
    - `processed_files`: FINAL normalized count (`len(completed_files)+len(failed_files)`) after pruning
    - `original_processed_files`: pre-normalization raw counter (retained for audit)
    - `successful_uploads`: cumulative distinct successes (== len(completed_files))
    - `successful_this_run`: number of new successes in the current execution (bounded by `--limit` / orchestrator `--upload-limit`)
    - `failed_uploads`: count of failures (== len(failed_files))
    - `uploaded_bytes` / `total_bytes`: actual vs planned bytes
    - `avg_upload_speed`: MB/sec effective throughput
    - `start_time` / `end_time`
    - `context_hash`: truncated fingerprint of Fabric workspace + lakehouse + base path
    - `schema_version`: progress schema version

Normalization ensures no residual meta/support entries inflate `processed_files`. If you see a mismatch during runtime logs, the final persisted JSON should still present the normalized value.

Files/sec and MB/sec appear in final summary log lines.

### 🧩 Resumable State Files
| File | Purpose |
|------|---------|
| `partial_uploads.json` | Track next append `position` for in-progress large files (removed on success) |
| `dir_cache.json` | Avoid duplicate directory creation calls |
| `file_cache_optimized.json` | Source file discovery cache |
| `_archive_json/*.json` | Archived legacy/incompatible progress snapshots |

### 🏗️ Delta Lake / Fabric Integration
* Metadata (if exported) can seed Delta tables for file lineage
* Hash values enable downstream integrity validation or deduping
* Compatible with Fabric notebooks & Lakehouse file queries

### 🔐 Authentication
* Client credentials flow; token auto-refresh
* Scope: `https://storage.azure.com/.default`

### 🛡️ Reliability
* Transient-safe: partial progress persisted before retries
* Fail-fast optional (`--fail-fast`) or continue collecting failures
* Clear restart options via `--reset-progress`

## Usage Examples

### Optimized Migration (New Script + Orchestrator Option)
Primary optimized script: `onelake_migrator_turbo_fixed.py`

```bash
# Minimal test (first 5 files, verbose HTTP steps)
conda run -n onelake-migration python src/fabric/onelake_migrator_turbo_fixed.py \
    --source ./downloaded_files --limit 5 --verbose

# Enable resumable chunk uploads & pre-create directories
conda run -n onelake-migration python src/fabric/onelake_migrator_turbo_fixed.py \
    --source ./downloaded_files --enable-resume-chunks --precreate-dirs

# Force a larger chunk size (e.g., 64MB) for very large files
conda run -n onelake-migration python src/fabric/onelake_migrator_turbo_fixed.py \
    --source ./downloaded_files --chunk-size-bytes 67108864

# Clean restart ignoring previous progress & caches
conda run -n onelake-migration python src/fabric/onelake_migrator_turbo_fixed.py \
    --source ./downloaded_files --reset-progress

# Orchestrated end-to-end (download + upload 50 new files) with JSON report
conda run -n onelake-migration python -m onelake_migration.orchestration.orchestrator \
    --download-limit 50 \
    --upload-limit 50 \
    --enable-resume-chunks \
    --report-json run_50.json
```

### Legacy Script (Still Available)
`onelake_migrator.py` retained for reference (batch-based, non-streaming). Prefer the optimized script for production loads.

## Expected Results

### OneLake Structure (Result)
```
/Files/SharePoint_Invoices/
├── Plant Invoices/
│   ├── P4/
│   │   ├── invoice1.pdf
│   │   └── invoice2.pdf
│   └── P5/
├── Other_Documents/
└── delta_tables/
    └── sharepoint_invoices/
        └── metadata.parquet
```

### Delta Lake Table
A queryable table with metadata:
```sql
SELECT 
    document_type,
    COUNT(*) as file_count,
    SUM(file_size_bytes)/1024/1024/1024 as total_gb
FROM sharepoint_invoices 
GROUP BY document_type
ORDER BY total_gb DESC
```

## Fabric Analytics Integration

Once migrated, you can:

### 1. Create Fabric Notebooks
```python
# Read the file metadata
df = spark.read.table("sharepoint_invoices")

# Analyze document types
df.groupBy("document_type").count().display()

# Find large files
df.filter(df.file_size_bytes > 10*1024*1024).display()
```

### 2. Build Power BI Reports
- Connect to the Delta table
- Create visualizations of file inventory
- Monitor migration progress
- Track document types and sizes

### 3. Set up Data Pipelines
- Automated file processing
- Document AI integration
- Compliance monitoring
- Backup scheduling

## Troubleshooting (Expanded)

### Common Issues

**Permission Errors**
- Verify app registration permissions
- Check Fabric workspace access
- Ensure lakehouse creation rights

**Token Expiration**
- App registration secrets expire
- Refresh tokens automatically handled
- Check Azure AD app status

**Large File Uploads**
* Use streaming script (default) – no need for manual splitting
* If throttled, reduce concurrent processes (if you add external parallelism)

**Resume Not Working**
* Confirm `--enable-resume-chunks` flag used
* Inspect `partial_uploads.json` for file entry with next position
* Delete entry to force full re-upload

**Hash Missing In Progress**
* Ensure you are using `onelake_migrator_turbo_fixed.py`
* Confirm file completed (hash only persisted on final flush)

**Memory Issues**
* Streaming avoids loading entire file – if still high, check other processes
* Disable any external buffering layers

**Throughput Lower Than Expected**
* Check network bandwidth & latency
* Increase chunk size via `--chunk-size-bytes` (balanced with error recovery granularity)
* Avoid running multiple heavy I/O jobs concurrently on same disk
* Verify `successful_this_run` is progressing (if fixed, you may have hit an `--upload-limit` cap)

## Cost Considerations

### OneLake Storage Pricing
- **Standard**: ~$0.023/GB/month
- **Archive**: ~$0.002/GB/month (after 30 days)

### Estimated Costs for Your Data
Based on analysis, your migration will cost approximately:
- **376,882 files** (~500GB estimated)
- **Monthly cost**: ~$11.50/month
- **Annual cost**: ~$138/year

### Cost Optimization
- Use archival policies for old files
- Implement retention policies
- Consider file deduplication

## Next Steps

1. **Get Fabric workspace details** and update `.env`
2. **Test with small batch** to verify connectivity
3. **Run full analysis** to understand scope
4. **Execute migration** in production
5. **Set up Fabric analytics** for insights

## Support & Artifacts

Key JSON artifacts (per profile namespace):
* `migration_progress_optimized.json` – canonical progress (normalized metrics)
* `partial_uploads.json` – resume offsets (ephemeral)
* `dir_cache.json` – directory creation cache
* `file_cache_optimized.json` – discovered source files
* `_archive_json/` – archived legacy or incompatible schema snapshots

For integrity validation you can re-hash a subset of uploaded OneLake files and compare to stored SHA256.

For issues with this migration tool:
1. Check logs and final normalized `processed_files` alignment
2. Review `failed_files` entries (look at `step` and `error`)
3. Confirm `context_hash` matches intended environment (mismatch triggers safe reset)
4. Verify Fabric permissions and quotas
5. If uploads appear capped early, review orchestrator `--upload-limit` or migrator `--limit`

See `FLAGS_REFERENCE.md` for the complete flag and metrics matrix including downloader/orchestrator options.
