# Quick Reference Guide

## 🚀 Getting Started (New Users)

```bash
# 1. Complete setup
make run

# 2. Edit .env file with your credentials
# (Open .env file and replace placeholder values)

# 3. Download files
make download
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

## 📊 Expected Output

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

## 🆘 Need Help?

1. Run `make status` to check your setup
2. Run `make test` to test configuration  
3. Check the full README.md for detailed documentation
4. Verify Azure AD app registration and permissions
