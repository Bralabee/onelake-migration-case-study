# SharePoint File Download Automation

This project automates the download of files from Microsoft SharePoint/Teams using the Microsoft Graph API.

## 📋 Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Configuration](#configuration)
- [Usage](#usage)
- [Speed Optimization](#speed-optimization)
- [Automation](#automation)
- [Troubleshooting](#troubleshooting)
- [File Structure](#file-structure)

## 🎯 Overview

The SharePoint File Download Automation provides two download-phase scripts and now pairs with a separate OneLake uploader *and* an end-to-end orchestrator for seamless download + upload flows:

1. **Standard Version** (`dll_pdf_fabric.py`) – Reliable sequential downloads
2. **Turbo Version** (`dll_pdf_fabric_turbo.py`) – High-speed parallel downloads
3. **(Post-Download) OneLake Uploader** (`src/fabric/onelake_migrator_turbo_fixed.py`) – Adaptive chunked + resumable streaming to Fabric OneLake (see case study root README)
4. **End-to-End Orchestrator** (`conda run -n onelake-migration python -m onelake_migration.orchestration.orchestrator`) – Chains downloader + migrator, adds bounded limits & consolidated JSON run reporting

### Key Features (Download Phase & Orchestrator Additions)

- **Authenticated Access**: Uses Azure AD service principal for secure access
- **Recursive Download**: Downloads all files from folders and subfolders
- **Progress Tracking**: Real-time progress updates with detailed logging
- **Error Handling**: Retry logic with exponential backoff for failed downloads
- **Folder Preservation**: Maintains SharePoint folder structure locally
- **Environment Configuration**: Secure credential management via `.env` file
- **Resume Capability**: Continue downloads from where they left off
- **File Caching**: Smart caching with 24-hour expiration for efficiency
- **Speed Optimization**: Parallel processing for 10-25x faster downloads
- **New-Only Mode**: `--download-new-only` to ignore already downloaded files (tracked as `ignored_existing`)
- **Profile Namespacing**: Use `--profile` to isolate state under `.state/<profile>/...`
- **Orchestrated Limits**: Pair `--download-limit` and `--upload-limit` to bound smoke tests end-to-end
- **Consolidated Metrics**: Run report captures downloader + migrator stats (`successful_this_run`, normalized `processed_files`)

## 🔧 Prerequisites

### Required Software
- **Python 3.11+**
- **Conda/Miniconda**
- **Git** (for version control)

### Azure Requirements
- **Azure AD Tenant** access
- **App Registration** with appropriate permissions
- **SharePoint Site** access

### Required Permissions
Your Azure AD app registration needs these Microsoft Graph permissions:
- `Sites.Read.All` - Read SharePoint sites
- `Files.Read.All` - Read files in SharePoint

## 🚀 Setup

### 1. Environment Setup
```bash
# Clone or navigate to the project directory
cd onelake-migration-case-study

# Create conda environment
make env-create
# OR manually
conda env create -f environment.yml

# Activate environment
conda activate onelake-migration
```

### 2. Azure App Registration

1. **Register Application**:
   - Go to [Azure Portal](https://portal.azure.com) → Azure Active Directory → App registrations
   - Click "New registration"
   - Name: `SharePoint File Downloader`
   - Supported account types: `Accounts in this organizational directory only`
   - Click "Register"

2. **Configure Permissions**:
   - Go to "API permissions"
   - Add permission → Microsoft Graph → Application permissions
   - Add: `Sites.Read.All`, `Files.Read.All`
   - Click "Grant admin consent"
   - Add permission → Microsoft Graph → Application permissions
   - Add: `Sites.Read.All`, `Files.Read.All`
   - Click "Grant admin consent"

3. **Create Client Secret**:
   - Go to "Certificates & secrets"
   - Click "New client secret"
   - Description: `SharePoint Download Secret`
   - Copy the secret value (you won't see it again!)

4. **Get IDs**:
   - **Tenant ID**: Azure AD → Overview → Directory (tenant) ID
   - **Client ID**: App registration → Overview → Application (client) ID

## ⚙️ Configuration

### 1. Environment Variables

Copy the template and configure your credentials:

```bash
# Copy template
make env-setup
# OR manually:
# cp .env.template .env
```

Edit `.env` file with your values:

```properties
# Microsoft Azure AD App Registration
TENANT_ID=your-tenant-id-here
CLIENT_ID=your-client-id-here
CLIENT_SECRET=your-client-secret-here

# SharePoint Configuration
SP_HOSTNAME=yourtenant.sharepoint.com
SP_SITE_PATH=teams/YourTeamSite
SP_LIBRARY_NAME=Documents
SP_START_FOLDER=Your/Folder/Path

# Local Download Configuration
LOCAL_DOWNLOAD_PATH=C:/downloads/sharepoint_files
```

### 2. Configuration Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `TENANT_ID` | Your Azure AD tenant ID | `efe042fe-23234c69c5ec` |
| `CLIENT_ID` | App registration client ID | `74ab6fe0512e5dc28a85` |
| `CLIENT_SECRET` | App registration secret | `cMZ8Q~p4VzzS_B0.HTjJrO8cvp` |
| `SP_HOSTNAME` | SharePoint domain | `contoso.sharepoint.com` |
| `SP_SITE_PATH` | Site path (after /sites/ or /teams/) | `teams/ProjectTeam` |
| `SP_LIBRARY_NAME` | Document library name | `Documents` |
| `SP_START_FOLDER` | Folder path within library | `Projects/2025/Invoices` |
| `LOCAL_DOWNLOAD_PATH` | Local download directory | `C:/downloads/files` |

## 🎮 Usage

### Quick Start

```bash
# Run complete setup and download
make run

# OR step by step:
make env-create    # Create environment
make env-activate  # Show activation command
make download      # Run download script
```

### Manual Execution & Orchestrated Runs

```bash
# Activate environment
conda activate onelake-migration

# Run the standard script
conda run -n onelake-migration python src/sharepoint/dll_pdf_fabric.py

# Run the turbo script (see Speed Optimization section)
conda run -n onelake-migration python src/sharepoint/dll_pdf_fabric_turbo.py --conservative

# Orchestrated small test (download 25, upload 25 new)
conda run -n onelake-migration python -m onelake_migration.orchestration.orchestrator --download-limit 25 --upload-limit 25 --enable-resume-chunks --report-json run_smoke.json

# Download new files only (skip upload phase)
conda run -n onelake-migration python -m onelake_migration.orchestration.orchestrator --download-new-only --download-limit 100 --skip-upload

# Upload only (previous downloads exist)
conda run -n onelake-migration python -m onelake_migration.orchestration.orchestrator --skip-download --upload-limit 100 --enable-resume-chunks
```

## 🚀 Speed Optimization

For large file sets (100,000+ files), use the high-performance turbo version:

### Performance Comparison

| Version | Speed | Time for 376k files | Workers | Use Case |
|---------|-------|-------------------|---------|----------|
| Standard | ~1.5 files/sec | ~2.5 days | 1 | Reliable, lower resource usage |
| Turbo Conservative | ~7-10 files/sec | ~12-18 hours | 5 | Safe parallel processing |
| Turbo Normal | ~15-20 files/sec | ~6-8 hours | 10 | Balanced speed/stability |
| Turbo Fast | ~20-25 files/sec | ~4-5 hours | 15 | High-speed processing |
| Turbo Maximum | ~25-30 files/sec | ~3-4 hours | 25 | Maximum performance |

### Turbo Usage

```bash
# Test turbo version first
make test-turbo

# Start conservatively (recommended for first run)
make run-turbo-conservative

# Increase speed based on system capacity
make run-turbo-normal
make run-turbo-fast
make run-turbo           # Maximum speed

# Direct execution with options
conda run -n onelake-migration python src/sharepoint/dll_pdf_fabric_turbo.py --conservative
conda run -n onelake-migration python src/sharepoint/dll_pdf_fabric_turbo.py --normal
conda run -n onelake-migration python src/sharepoint/dll_pdf_fabric_turbo.py --fast
conda run -n onelake-migration python src/sharepoint/dll_pdf_fabric_turbo.py --turbo

# View speed comparison
make compare-speeds
```

### Turbo Features
- **Parallel Downloads**: 5-25 concurrent workers
- **Connection Pooling**: Optimized HTTP sessions
- **Thread-Safe Progress**: Real-time monitoring
- **Smart Retry Logic**: Per-worker error handling
- **Resource Monitoring**: Automatic speed tracking

### Cache Management

The script implements intelligent caching to avoid re-scanning large folder structures on subsequent runs:

```bash
# Check cache status
make cache-status

# Normal download (uses cache if valid and < 24h old)
make download

# Force refresh to detect new files
make refresh

# Clear cache and force fresh scan
make clear-cache
# or directly
conda run -n onelake-migration python src/sharepoint/dll_pdf_fabric.py --clear-cache

# View help and options
conda run -n onelake-migration python src/sharepoint/dll_pdf_fabric.py --help
```

**Cache Files:**
- `file_list_cache.json`: Stores the complete file list from SharePoint with metadata
- `download_progress.json`: Tracks download progress and completed files

**Cache Validation:**
The file list cache is automatically validated and refreshed if:
- SharePoint site configuration changes (site_id, drive_id, or folder_id)
- Cache is older than 24 hours (to detect new files)
- Cache file format is incompatible
- Force refresh is requested (`--refresh` flag)

**Benefits:**
- Skip lengthy file discovery phase (saves minutes for large folders)
- Resume downloads from where they left off
- Avoid re-processing completed files
- Automatic detection of new files after 24 hours
- Manual refresh option for immediate new file detection

### Script Output (Downloader Example)

The script provides detailed logging:

```
2025-08-07 12:51:04,266 - INFO - 🔐 Authenticating with Microsoft Graph...
2025-08-07 12:51:04,450 - INFO - 🌐 Getting SharePoint site...
2025-08-07 12:51:04,593 - INFO - ✅ Site found: contoso.sharepoint.com,xxx
2025-08-07 12:51:04,594 - INFO - 📚 Getting document library...
2025-08-07 12:51:04,788 - INFO - 📂 Available Drives:
2025-08-07 12:51:04,788 - INFO - - Name: Documents, ID: xxx
2025-08-07 12:51:04,789 - INFO - ✅ Drive found: xxx
2025-08-07 12:51:04,789 - INFO - 📁 Navigating to start folder...
2025-08-07 12:51:05,080 - INFO - ✅ Found folder: Projects
2025-08-07 12:51:05,284 - INFO - ✅ Found folder: Invoices
2025-08-07 12:51:05,285 - INFO - ✅ Folder found: xxx
2025-08-07 12:51:05,285 - INFO - 📋 Listing files recursively...
2025-08-07 12:51:05,449 - INFO - 📁 Processing folder: Subfolder1/
2025-08-07 12:51:05,628 - INFO - ✅ Total files found: 150
2025-08-07 12:51:05,629 - INFO - Starting download of 150 files to C:/downloads/files
2025-08-07 12:51:05,630 - INFO - Progress: 1/150 (0.7%)
2025-08-07 12:51:05,631 - INFO - Downloading: file1.pdf (attempt 1)
2025-08-07 12:51:05,855 - INFO - ✅ Downloaded: file1.pdf
...
2025-08-07 12:55:30,123 - INFO - 📊 Download Summary:
2025-08-07 12:55:30,124 - INFO - ✅ Successful: 148
2025-08-07 12:55:30,125 - INFO - ❌ Failed: 2
```

## 🤖 Automation

### Makefile Commands

| Command | Description |
|---------|-------------|
| `make help` | Show all available commands |
| `make env-create` | Create conda environment |
| `make env-update` | Update environment with new packages |
| `make env-clean` | Remove environment |
| `make env-setup` | Copy .env template for configuration |
| `make download` | Run the download script |
| `make refresh` | Force re-scan to detect new files |
| `make clear-cache` | Clear file list and progress cache |
| `make cache-status` | Show cache file status |
| `make run` | Complete setup and run (new users) |
| `make status` | Check environment and configuration |

### Scheduling (Windows)

To run automatically, use Windows Task Scheduler:

1. **Create Task**:
   - Open Task Scheduler
   - Create Basic Task
   - Name: "SharePoint File Download"

2. **Configure Trigger**:
   - Daily, Weekly, or Custom schedule

3. **Configure Action**:
   - Program: `C:\path\to\conda.exe`
   - Arguments: `run -n onelake-migration python C:\path\to\src\sharepoint\dll_pdf_fabric.py`
   - Start in: `C:\path\to\Commercial_ACA_taskforce`

## 🔍 Troubleshooting

### Common Issues

#### Authentication Errors
```
HTTPError: 400 Client Error: Bad Request
```
**Solution**: Check your `.env` file for:
- Extra quotes or spaces in values
- Correct tenant/client IDs
- Valid client secret

#### Permission Errors
```
403 Forbidden
```
**Solution**: Verify your app registration has:
- `Sites.Read.All` permission
- `Files.Read.All` permission
- Admin consent granted

#### Site/Folder Not Found
```
❌ Drive 'Documents' not found
❌ Folder 'Projects' not found
```
**Solution**: 
- Check `SP_SITE_PATH` is correct
- Verify `SP_LIBRARY_NAME` exists
- Ensure `SP_START_FOLDER` path is accurate

#### Environment Issues
```
ModuleNotFoundError: No module named 'requests'
```
**Solution**:
```bash
# Recreate environment
make env-clean
make env-create
conda activate onelake-migration
```

### Debug Mode

Enable detailed debugging by modifying the script:
```python
# Change logging level
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
```

## 📁 File Structure (Download + Upload + Orchestrator Context)

```
Commercial_ACA_taskforce/
├── dll_pdf_fabric.py                 # Standard download script (sequential)
├── dll_pdf_fabric_turbo.py           # Turbo download script (parallel)
├── src/fabric/onelake_migrator_turbo_fixed.py  # Optimized OneLake streaming uploader
├── environment.yml                   # Conda environment definition
├── Makefile                          # Automation commands
├── .env / .env.template / .env.example
├── QUICK_START.md                    # Quick setup guide
├── file_list_cache.json              # Download phase file list cache
├── download_progress.json            # Legacy progress tracking (sequential)
├── download_progress_turbo.json      # Turbo progress tracking
├── migration_progress_optimized.json # OneLake upload progress (hash + size per file, normalized metrics)
├── (orchestrator via module path)     # python -m onelake_migration.orchestration.orchestrator
└── downloaded_files/                 # Downloaded files (created automatically)
      └── ...
```

### OneLake Upload (Post-Download)
After downloads complete:
```bash
conda run -n onelake-migration python src/fabric/onelake_migrator_turbo_fixed.py \
   --source ./downloaded_files --enable-resume-chunks --precreate-dirs
```
Progress & integrity details (including per-file SHA256, `successful_this_run`, normalized `processed_files`) stored in `migration_progress_optimized.json`.

See `FLAGS_REFERENCE.md` for a complete matrix of downloader, migrator, and orchestrator flags plus metric definitions.

## 🔒 Security Notes

- **Never commit `.env` files** to version control
- **Rotate client secrets** regularly (every 6-12 months)
- **Use least-privilege permissions** for the app registration
- **Store credentials securely** in production environments
- **Monitor access logs** in Azure AD

## 📈 Performance

### Standard Version
- **Sequential Processing**: Downloads files one at a time
- **Retry Logic**: 3 attempts with exponential backoff
- **Progress Tracking**: Real-time progress updates
- **Speed**: ~1.5 files/sec (reliable for smaller sets)

### Turbo Version
- **Parallel Processing**: 5-25 concurrent downloads
- **Connection Pooling**: Optimized HTTP sessions with keep-alive
- **Thread-Safe Operations**: Concurrent progress tracking
- **Smart Resource Management**: Automatic connection limits
- **Speed**: ~7-30 files/sec (10-25x faster than standard)
- **Memory Efficient**: Streams large files instead of loading into memory

## 🆘 Support

For issues or questions:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review Azure AD app registration permissions
3. Verify SharePoint site access
4. Check environment configuration

---

**Last Updated**: September 10, 2025  
**Version**: 1.1  
**Author**: Sanmi Ibitoye for : Commercial ACA Taskforce
