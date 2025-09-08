# 🚀 OneLake Migration - Quick Start Guide

**Get up and running in 5 minutes (Unified CLI)**

This guide gets you from zero to running the unified migration engine in the shortest time possible.

---

## ⚡ 30-Second Setup

```powershell
# 1. Navigate to project
cd Commercial_ACA_taskforce

# 2. (First time only) create env & .env template
make env-create
make env-setup

# 3. Activate environment
conda activate aca_taskforce_env

# 4. Generate / refresh token
powershell.exe -ExecutionPolicy Bypass -File scripts/powershell/get_access_token.ps1

# 5. Pre-flight (NOOP – lists first 5 files, no uploads)
python -m fabric.migration.production --noop

# 6. Start migration (production preset)
python -m fabric.migration.production --mode production

# (Or use Make targets)
make migrate-prod
```


## 🎯 Current Project State

### ✅ What Works Right Now
- Environment: `aca_taskforce_env`
- Auth: PowerShell token script + internal MSAL caching
- Unified Engine: `fabric.migration.production`
- Monitoring: Dashboard at http://localhost:8052 (override: `make DASHBOARD_PORT=9001 dashboard`)
- Config: `config/.env` (create via `make env-setup`)
- Makefile variable inspection: `make vars`

### ⚠️ Current Situation
Data set already fully migrated (376,888 files). Re-running against same destination will mostly encounter existing files (conflict messages) which are logged as skips.


## 🔧 Choose Your Mission

### Mission 1: Test Connectivity (Recommended First)
```powershell
python -m fabric.migration.production --test-run
```

### Mission 2: Safe NOOP (Readiness Check)
```powershell
python -m fabric.migration.production --noop
# or
make migrate-noop
```

### Mission 3: Monitor Existing Files
```powershell
python src/monitoring/simple_dashboard.py --port 8052
# View at: http://localhost:8052
```

### Mission 4: Production Migration (if needed)
```powershell
# Production (balanced)
python -m fabric.migration.production --mode production
# Turbo (higher throughput)
python -m fabric.migration.production --mode turbo
# Working / conservative
python -m fabric.migration.production --mode working
```


## 🔍 What You'll See

### Success Indicators (examples)
```text
✅ ACCESS TOKEN VALID - Expires: 2025-09-05 15:05:12
✅ Loaded file cache (N files)
✅ SUCCESS: Uploaded test_upload/test_api_working.py (validation)
```

### Expected "Conflicts" (Already Uploaded)
```text
⚠️ File exists (skipped/failed due to conflict) — normal if rerunning full set
```


## 🚨 Common Quick Fixes

### Token Expired
```powershell
powershell.exe -ExecutionPolicy Bypass -File scripts/powershell/get_access_token.ps1
```

### Wrong Directory
```powershell
Get-Location
```

### Environment Not Active
```powershell
conda activate aca_taskforce_env
python -c "import aiofiles; print('✅ Ready')"
```


## 📋 Essential Commands

### Token
```powershell
powershell.exe -ExecutionPolicy Bypass -File scripts/powershell/get_access_token.ps1
```

### Migration (Unified)
```powershell
# Production
python -m fabric.migration.production --mode production
# Turbo
python -m fabric.migration.production --mode turbo
# Working
python -m fabric.migration.production --mode working
# Test run (5 batches)
python -m fabric.migration.production --test-run
# or Makefile shortcut
make migrate-test-run
# Retry failures (all or capped)
python -m fabric.migration.production --retry-failures --max-retry 250
# Reconcile counters
python -m fabric.migration.production --reconcile-progress
# No‑op (list first five entries, zero uploads)
python -m fabric.migration.production --noop
# or
make migrate-noop
# Structured JSON logs + custom run id
$env:MIGRATION_JSON_LOGS=1; $env:MIGRATION_RUN_ID="quickstart-demo"; python -m fabric.migration.production --test-run
```

### Monitoring (Default Port 8052)
```powershell
python src/monitoring/simple_dashboard.py --port 8052
# or with Makefile variable override
make DASHBOARD_PORT=9001 dashboard
```


## 🎯 5-Minute Success Path (With Pre-flight)

```powershell
make env-create
make env-setup
conda activate aca_taskforce_env
powershell.exe -ExecutionPolicy Bypass -File scripts/powershell/get_access_token.ps1
python -m fabric.migration.production --noop
python -m fabric.migration.production --test-run
python src/monitoring/simple_dashboard.py --port 8052
# Optional production / turbo
python -m fabric.migration.production --mode turbo
```


## 🔍 What Success Looks Like

```text
🔑 Access token loaded / refreshed
✅ Test batch succeeded
📊 Dashboard running at: http://localhost:8052
```


## 🆘 Emergency Troubleshooting

### Nothing Works
```powershell
cd Commercial_ACA_taskforce
conda activate aca_taskforce_env
powershell.exe -ExecutionPolicy Bypass -File scripts/powershell/get_access_token.ps1
python -m fabric.migration.production --test-run
```

### Problem: Can't Generate Token
1. Check internet connection
2. Verify you're on corporate network/VPN
3. Confirm Azure AD permissions
4. Try running PowerShell as administrator

### Import Errors / Environment Incomplete
```powershell
conda activate aca_taskforce_env
pip install aiofiles aiohttp msal
```

### Override Defaults (Advanced)
Use Make variables instead of editing the Makefile:
```powershell
make SOURCE_DIR=D:/alt/data migrate-noop
make WORKSPACE_ID=<guid> LAKEHOUSE_ID=<guid> fabric-migrate-azcopy-dryrun
make DASHBOARD_PORT=9001 dashboard
```

Persistent overrides:
```powershell
copy local.mk.example local.mk
# edit local.mk then run normal targets
make migrate-prod
```


## 📞 Getting Help

1. Check token freshness
2. Confirm environment active
3. Ensure you're in project root
4. Review logs in `logs/` and progress JSON in `data/`

---

### 🕰️ Legacy Script Notice
Older scripts (e.g. `onelake_migrator_turbo_working.py`) remain as temporary wrappers ONLY. They will be removed after the unified CLI is fully adopted. Always prefer:
```powershell
python -m fabric.migration.production --mode production
# or
make migrate-prod
```
Structured logging & correlation id details: see `FABRIC_MIGRATION_GUIDE.md`. For JSON logs:
```powershell
$env:MIGRATION_JSON_LOGS=1; $env:MIGRATION_RUN_ID="quickstart-demo"; python -m fabric.migration.production --test-run
```

**Last Updated:** September 2025 (Unified CLI Refresh + Structured Logging)**
