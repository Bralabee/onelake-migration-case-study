# Quick Reference Guide

> Added (Sept 2025): For OneLake uploads (post-download) use the optimized streaming uploader `src/fabric/onelake_migrator_turbo_fixed.py` which supports adaptive chunking, resumable partial uploads, and per-file SHA256 hashing. See main case study README for details.

## 🚀 Getting Started (New Users)

You can now run an end-to-end SharePoint download + OneLake upload via the orchestrator instead of invoking scripts separately.

```bash
# 1. Complete setup (creates env + validates)
make run

# 2. Edit .env file with your credentials
# (Open .env file and replace placeholder values)

# 3a. Download only (turbo cached)
make download

# 3b. Orchestrated small smoke test (download 25 new, upload 25 new)
conda run -n onelake-migration python -m onelake_migration.orchestration.orchestrator \
	--download-limit 25 \
	--upload-limit 25 \
	--enable-resume-chunks \
	--report-json run_smoke.json

# 3c. Download new files only (skip already present)
conda run -n onelake-migration python -m onelake_migration.orchestration.orchestrator --download-new-only --download-limit 100 --skip-upload

# 3d. Upload only using prior downloads (resume state)
conda run -n onelake-migration python -m onelake_migration.orchestration.orchestrator --skip-download --upload-limit 100 --enable-resume-chunks
```

## 🎮 Common Commands

### Environment Management
```bash
make env-create     # Create conda environment
make env-activate   # Show activation command  
make env-update     # Update packages
make env-clean      # Remove environment
```

### Configuration
```bash
make env-setup      # Copy .env template
make status         # Check setup status
make test          # Test configuration
```

### Running Downloads
```bash
make download      # Run download script (uses cache if < 24h old)
make refresh       # Force re-scan to detect new files
```

### Orchestrator (Download + Upload)
```bash
# Basic bounded run (download + upload)
conda run -n onelake-migration python -m onelake_migration.orchestration.orchestrator --download-limit 50 --upload-limit 50 --enable-resume-chunks --report-json run_50.json

# Profile isolation (separate state namespace)
conda run -n onelake-migration python -m onelake_migration.orchestration.orchestrator --profile prod --download-limit 100 --upload-limit 100

# Validate config only (no transfers)
conda run -n onelake-migration python -m onelake_migration.orchestration.orchestrator --validate-config --skip-download --skip-upload
```

### Cache Management
```bash
make cache-status  # Check cache files
make clear-cache   # Clear cache and force fresh scan
```

### Maintenance
```bash
make clean         # Clean temporary files
make help          # Show all commands
```

## 📋 Pre-requisites Checklist

- [ ] Azure AD App Registration created
- [ ] App has `Sites.Read.All` and `Files.Read.All` permissions
- [ ] Admin consent granted for permissions
- [ ] Tenant ID, Client ID, and Client Secret obtained
- [ ] SharePoint site path identified
- [ ] Target folder path confirmed

## ⚙️ Configuration Values

Edit `.env` file with these values:

```properties
TENANT_ID=your-azure-ad-tenant-id
CLIENT_ID=your-app-registration-client-id  
CLIENT_SECRET=your-app-registration-secret
SP_HOSTNAME=yourtenant.sharepoint.com
SP_SITE_PATH=teams/YourTeamSite
SP_LIBRARY_NAME=Documents
SP_START_FOLDER=Your/Folder/Path
LOCAL_DOWNLOAD_PATH=C:/downloads/sharepoint_files
```

## 🔍 Troubleshooting Quick Fixes

### Authentication Issues
```bash
# Check .env file has no quotes or extra spaces
# Verify credentials in Azure portal
```

### Environment Issues  
```bash
make env-clean
make env-create
```

### Permission Issues
```bash
# Verify app registration permissions in Azure AD
# Ensure admin consent is granted
```

### File Not Found
```bash
# Check SP_SITE_PATH and SP_START_FOLDER are correct
# Verify you have access to the SharePoint site
```

## 📊 Expected Output (Downloader Phase)

```
🔐 Authenticating with Microsoft Graph...
🌐 Getting SharePoint site...
✅ Site found: xxx
📚 Getting document library...
✅ Drive found: xxx  
📁 Navigating to start folder...
✅ Folder found: xxx
📋 Listing files recursively...
✅ Total files found: 150
Starting download of 150 files...
Progress: 1/150 (0.7%)
✅ Downloaded: file1.pdf
...
📊 Download Summary:
✅ Successful: 148
❌ Failed: 2
```

## 📊 Sample Orchestrator Report Extract

```json
{
	"download": {"success": true, "stats": {"new_files_downloaded": 25, "ignored_existing": 75}},
	"upload": {"success": true, "stats": {"successful_this_run": 25, "successful_uploads": 257}},
	"summary": {"profile": "default", "timestamp": "2025-09-10T12:34:56Z"}
}
```

Key new metrics:
- `ignored_existing`: files skipped due to `--download-new-only`
- `successful_this_run`: new uploads completed during this orchestrated run
- `processed_files` (in migrator progress) is normalized to completed + failed after pruning

## 🔗 Further Reference
See `FLAGS_REFERENCE.md` for the complete flag & metrics matrix.

## 🆘 Need Help?

1. Run `make status` to check your setup
2. Run `make test` to test configuration  
3. Check the full README.md for detailed documentation
4. Verify Azure AD app registration and permissions
