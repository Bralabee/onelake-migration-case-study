############################################################
# Core Configuration (override via environment or CLI)      #
############################################################

# Conda environment name (override: `make ENV_NAME=myenv migrate-prod`)
ENV_NAME ?= aca_taskforce_env

# Environment specification file
ENV_FILE ?= environment.yml

# Source directory for Python modules (inserted into PYTHONPATH)
SRC_DIR ?= src

# Primary SharePoint download script (legacy workflow)
SHAREPOINT_SCRIPT ?= $(SRC_DIR)/sharepoint/dll_pdf_fabric.py

# Turbo downloader script (legacy)
SHAREPOINT_TURBO_SCRIPT ?= $(SRC_DIR)/sharepoint/dll_pdf_fabric_turbo.py

# Monitoring scripts
SIMPLE_DASHBOARD ?= $(SRC_DIR)/monitoring/simple_dashboard.py
ENHANCED_DASHBOARD ?= $(SRC_DIR)/monitoring/enhanced_dashboard.py
CUSTOM_DASHBOARD ?= $(SRC_DIR)/monitoring/dashboard_monitor.py
LOG_ANALYZER ?= $(SRC_DIR)/monitoring/log_analyzer.py

# Fabric / OneLake scripts (legacy helpers)
FABRIC_SETUP_SCRIPT ?= $(SRC_DIR)/fabric/fabric_setup_onelake.py
FABRIC_ANALYZE_STRUCTURE ?= $(SRC_DIR)/fabric/analyze_directory_structure.py
FABRIC_CREATE_DIRS_API ?= $(SRC_DIR)/fabric/create_onelake_directories.py
FABRIC_TURBO_LEGACY ?= onelake_migrator_production.py
FABRIC_TURBO_FIXED ?= $(SRC_DIR)/fabric/onelake_migrator_turbo_fixed.py
FABRIC_MIGRATOR_LEGACY ?= $(SRC_DIR)/fabric/onelake_migrator.py

# Unified migrator Python module & default execution flags
MIGRATOR_MODULE ?= fabric.migration.production
PYTHON ?= python

# Default data / source paths (may be overridden)
SOURCE_DIR ?= C:/commercial_pdfs/downloaded_files
DOWNLOAD_PROGRESS_FILE ?= $(SOURCE_DIR)/download_progress_turbo.json

# Fabric IDs (override via: make WORKSPACE_ID=... LAKEHOUSE_ID=... fabric-migrate-azcopy)
WORKSPACE_ID ?= YOUR_WORKSPACE_ID
LAKEHOUSE_ID ?= YOUR_LAKEHOUSE_ID

# AzCopy script & arguments (override AZCOPY_SOURCE if different from SOURCE_DIR)
AZCOPY_SCRIPT ?= scripts/powershell/azcopy_migration.ps1
AZCOPY_SOURCE ?= $(SOURCE_DIR)
AZCOPY_ARGS = -SourcePath "$(AZCOPY_SOURCE)" -WorkspaceId "$(WORKSPACE_ID)" -LakehouseId "$(LAKEHOUSE_ID)"

# Reorganization & helper PowerShell scripts
REORGANIZE_SCRIPT ?= scripts/powershell/reorganize_codebase.ps1
GET_TOKEN_SCRIPT ?= scripts/powershell/get_access_token.ps1
FILE_EXPLORER_SETUP ?= scripts/powershell/onelake_file_explorer_setup.ps1

# .env handling
ENV_TEMPLATE ?= .env.template
ENV_CONFIG ?= .env

# Dashboard ports (override: make DASHBOARD_PORT=9000 dashboard)
DASHBOARD_PORT ?= 8052
DASHBOARD_ENHANCED_PORT ?= 8053

# Internal macro: base invocation for unified migrator (PowerShell required for PYTHONPATH prepend on Windows)
MIGRATE_SHELL = conda run -n $(ENV_NAME) powershell -Command
MIGRATE_ENV_BOOTSTRAP = "$$env:PYTHONPATH='$(SRC_DIR);' + ($$env:PYTHONPATH); $(PYTHON) -m $(MIGRATOR_MODULE)"

# Internal macro: simple conda python call (no PowerShell)
CONDA_PY = conda run -n $(ENV_NAME) $(PYTHON)

# Columnized echo helper (ANSI may not render in all shells; kept simple)
define PRINT_VAR_BLOCK
	@echo "Configuration → ENV_NAME=$(ENV_NAME) SRC_DIR=$(SRC_DIR) SOURCE_DIR=$(SOURCE_DIR) WORKSPACE_ID=$(WORKSPACE_ID) LAKEHOUSE_ID=$(LAKEHOUSE_ID)"
endef

# Optional per-developer overrides (not committed). Provide local.mk to redefine any ?= vars.
-include local.mk

.PHONY: help env-create env-update env-clean env-setup env-activate download run status test clean all dashboard analyze-logs setup-dashboard reorganize vars

# Unified migration targets (new)
.PHONY: migrate-prod migrate-turbo migrate-working migrate-retry migrate-reconcile

# Default target
all: help

# Codebase organization
reorganize:
	@echo "🏗️ Reorganizing codebase structure..."
	powershell -ExecutionPolicy Bypass -File "$(REORGANIZE_SCRIPT)"

reorganize-dryrun:
	@echo "🧪 Testing codebase reorganization (dry run)..."
	powershell -ExecutionPolicy Bypass -File "$(REORGANIZE_SCRIPT)" -DryRun

# Show evaluated core variables
vars:
	$(PRINT_VAR_BLOCK)

# Show help
help:
	@echo "🚀 SharePoint File Download Automation"
	@echo "======================================"
	@echo ""
	@echo "📁 Organization:"
	@echo "  make reorganize         Organize codebase into structured directories"
	@echo "  make reorganize-dryrun  Test reorganization without moving files"
	@echo ""
	@echo "Environment Management:"
	@echo "  make env-create    Create conda environment"
	@echo "  make env-update    Update environment with new packages"
	@echo "  make env-clean     Remove conda environment"
	@echo "  make env-activate  Show activation command"
	@echo "  make setup-dashboard Install dashboard dependencies"
	@echo ""
	@echo "Configuration:"
	@echo "  make env-setup     Copy .env template for configuration"
	@echo "  make status        Check environment and configuration status"
	@echo ""
	@echo "Execution:"
	@echo "  make download      Run the SharePoint download script"
	@echo "  make test          Test script imports and configuration"
	@echo "  make run           Complete setup and run (for new users)"
	@echo ""
	@echo "Monitoring & Analytics:"
	@echo "  make dashboard     Launch real-time monitoring dashboard"
	@echo "  make analyze-logs  Analyze download logs"
	@echo ""
	@echo "Microsoft Fabric (Unified Migrator):"
	@echo "  make migrate-prod        Production mode (balanced)"
	@echo "  make migrate-turbo       Turbo mode (high throughput)"
	@echo "  make migrate-working     Working/safe mode"
	@echo "  make migrate-retry       Retry failed uploads"
	@echo "  make migrate-reconcile   Recalculate progress counters"
	@echo "  make fabric-help         Legacy help (deprecated wrappers)"
	@echo ""
	@echo "Quick Start:"
	@echo "  1. make reorganize     # Organize codebase (FIRST TIME ONLY)"
	@echo "  2. make env-create     # Create environment"
	@echo "  3. make env-setup      # Copy .env template" 
	@echo "  4. Edit .env file with your credentials"
	@echo "  5. make migrate-prod   # Start migration (new unified CLI)"
	@echo ""
	@echo "Unified Migration CLI Examples:"
	@echo "  $(PYTHON) -m $(MIGRATOR_MODULE) --mode production"
	@echo "  $(PYTHON) -m $(MIGRATOR_MODULE) --mode turbo --concurrency 60 --batch-size 300"
	@echo "  $(PYTHON) -m $(MIGRATOR_MODULE) --retry-failures --max-retry 100"
	@echo "  $(PYTHON) -m $(MIGRATOR_MODULE) --reconcile-progress"
	@echo ""
	@echo "Variable Overrides (examples):"
	@echo "  make ENV_NAME=alt_env migrate-prod"
	@echo "  make SOURCE_DIR=D:/data/downloaded migrate-noop"
	@echo "  make WORKSPACE_ID=xxxx LAKEHOUSE_ID=yyyy fabric-migrate-azcopy"
	@echo "  make DASHBOARD_PORT=9001 dashboard"

# Unified migrator targets -------------------------------------------------

migrate-prod:
	@echo "🚀 OneLake Migration (production mode)"
	$(MIGRATE_SHELL) $(MIGRATE_ENV_BOOTSTRAP) --mode production

migrate-turbo:
	@echo "⚡ OneLake Migration (turbo mode)"
	$(MIGRATE_SHELL) $(MIGRATE_ENV_BOOTSTRAP) --mode turbo

migrate-working:
	@echo "🧪 OneLake Migration (working/safe mode)"
	$(MIGRATE_SHELL) $(MIGRATE_ENV_BOOTSTRAP) --mode working

migrate-retry:
	@echo "🔁 Retrying failed uploads (all failures)"
	$(MIGRATE_SHELL) $(MIGRATE_ENV_BOOTSTRAP) --retry-failures

migrate-retry-%:
	@echo "🔁 Retrying first $* failed uploads"
	$(MIGRATE_SHELL) $(MIGRATE_ENV_BOOTSTRAP) --retry-failures --max-retry $*

migrate-reconcile:
	@echo "♻️  Reconciling progress counters"
	$(MIGRATE_SHELL) $(MIGRATE_ENV_BOOTSTRAP) --reconcile-progress

.PHONY: migrate-noop
migrate-noop:
	@echo "🔎 OneLake Migration NOOP (list first 5 files)"
	$(MIGRATE_SHELL) $(MIGRATE_ENV_BOOTSTRAP) --noop

.PHONY: migrate-test-run
migrate-test-run:
	@echo "🧪 OneLake Migration TEST-RUN (first 5 batches)"
	$(MIGRATE_SHELL) $(MIGRATE_ENV_BOOTSTRAP) --test-run

# Environment management
env-create:
	@echo "📦 Creating conda environment..."
	conda env create -f $(ENV_FILE) --force
	@echo "✅ Environment created successfully!"
	@echo "💡 Run 'make env-activate' to see activation command"

env-update:
	@echo "🔄 Updating conda environment..."
	conda env update -f $(ENV_FILE) --prune
	@echo "✅ Environment updated successfully!"

env-clean:
	@echo "🗑️  Removing conda environment..."
	conda env remove -n $(ENV_NAME) -y
	@echo "✅ Environment removed successfully!"

env-activate:
	@echo "To activate the environment, run:"
	@echo "    conda activate $(ENV_NAME)"

# Configuration setup
env-setup:
	@echo "⚙️  Setting up configuration..."
	@if exist $(ENV_CONFIG) ( \
		echo "⚠️  .env file already exists. Backup created as .env.backup" && \
		copy $(ENV_CONFIG) $(ENV_CONFIG).backup \
	)
	copy $(ENV_TEMPLATE) $(ENV_CONFIG)
	@echo "✅ Configuration template copied to .env"
	@echo "📝 Please edit .env file with your actual credentials:"
	@echo "   - TENANT_ID (Azure AD tenant ID)"
	@echo "   - CLIENT_ID (App registration client ID)" 
	@echo "   - CLIENT_SECRET (App registration secret)"
	@echo "   - SP_HOSTNAME (SharePoint domain)"
	@echo "   - SP_SITE_PATH (Site path)"
	@echo "   - SP_START_FOLDER (Folder to download from)"

# Status checks
status:
	@echo "📊 System Status"
	@echo "==============="
	@echo ""
	@echo "Environment Status:"
	@conda env list | findstr $(ENV_NAME) && echo "✅ Environment exists" || echo "❌ Environment not found - run 'make env-create'"
	@echo ""
	@echo "Configuration Status:"
	@if exist $(ENV_CONFIG) ( \
		echo "✅ .env file exists in root" \
	) else if exist config\$(ENV_CONFIG) ( \
		echo "✅ .env file exists in config/" \
	) else ( \
		echo "❌ .env file missing - run 'make env-setup'" \
	)
	@echo ""
	@echo "Script Status:"
	@if exist $(SHAREPOINT_SCRIPT) ( \
		echo "✅ Download script exists" \
	) else ( \
		echo "❌ Download script missing - run 'make reorganize' first" \
	)

# Testing
test:
	@echo "🧪 Testing configuration and imports..."
	@conda run -n $(ENV_NAME) python -c "print('🔍 Testing imports...'); import os, requests, datetime, time, logging, pathlib; print('✅ All imports successful!')"
	@$(CONDA_PY) -c "import sys; sys.path.append('$(SRC_DIR)'); from sharepoint.dll_pdf_fabric import load_env_file, validate_parameters, default_params; load_env_file(); print('✅ Configuration loaded successfully!')"
	@echo "✅ All tests passed!"

# Main execution
download:
	@echo "🚀 Starting SharePoint file download..."
	@echo "📍 Make sure you have:"
	@echo "   1. ✅ Activated environment: conda activate $(ENV_NAME)"
	@echo "   2. ✅ Configured .env file with your credentials"
	@echo "   3. ✅ Proper Azure AD permissions"
	@echo ""
	@echo "🔄 Running download script..."
	$(CONDA_PY) $(SHAREPOINT_SCRIPT)

# Cache management commands
clear-cache:
	@echo "🗑️  Clearing file list and progress cache..."
	$(CONDA_PY) $(SHAREPOINT_SCRIPT) --clear-cache
	@echo "✅ Cache cleared successfully!"

refresh:
	@echo "🔄 Force refreshing file list to detect new files..."
	$(CONDA_PY) $(SHAREPOINT_SCRIPT) --refresh

cache-status:
	@echo "📊 Cache Status"
	@echo "==============="
	@if exist file_list_cache.json ( \
		echo "✅ file_list_cache.json: EXISTS" \
	) else ( \
		echo "❌ file_list_cache.json: NOT FOUND" \
	)
	@if exist download_progress.json ( \
		echo "✅ download_progress.json: EXISTS" \
	) else ( \
		echo "❌ download_progress.json: NOT FOUND" \
	)
	@echo ""

# Complete setup and run for new users
run: env-create env-setup
	@echo ""
	@echo "🎯 Environment setup complete!"
	@echo "📝 Next steps:"
	@echo "   1. Edit the .env file with your actual credentials"
	@echo "   2. Run 'make download' to start downloading files"
	@echo ""
	@echo "💡 Use 'make status' to check your setup anytime"

# Cleanup
clean:
	@echo "🧹 Cleaning up temporary files..."
	@if exist *.log del *.log
	@if exist __pycache__ rmdir /s /q __pycache__
	@if exist .pytest_cache rmdir /s /q .pytest_cache
	@if exist src\__pycache__ rmdir /s /q src\__pycache__
	@if exist src\sharepoint\__pycache__ rmdir /s /q src\sharepoint\__pycache__
	@if exist src\fabric\__pycache__ rmdir /s /q src\fabric\__pycache__
	@if exist src\monitoring\__pycache__ rmdir /s /q src\monitoring\__pycache__
	@echo "✅ Cleanup complete!"

# Turbo version commands for speed optimization
run-turbo-conservative:
	@echo "🚀 Running SharePoint downloader with CONSERVATIVE parallel processing (5 workers)..."
	$(CONDA_PY) $(SHAREPOINT_TURBO_SCRIPT) --conservative

run-turbo-normal:
	@echo "🚀 Running SharePoint downloader with NORMAL parallel processing (10 workers)..."
	$(CONDA_PY) $(SHAREPOINT_TURBO_SCRIPT) --normal

run-turbo-fast:
	@echo "🚀 Running SharePoint downloader with FAST parallel processing (15 workers)..."
	$(CONDA_PY) $(SHAREPOINT_TURBO_SCRIPT) --fast

run-turbo:
	@echo "🚀 Running SharePoint downloader with TURBO parallel processing (25 workers)..."
	$(CONDA_PY) $(SHAREPOINT_TURBO_SCRIPT) --turbo

test-turbo:
	@echo "🧪 Testing turbo version..."
	$(CONDA_PY) $(SHAREPOINT_TURBO_SCRIPT) --help

# Quick comparison between versions
compare-speeds:
	@echo "📊 Speed Comparison Estimates:"
	@echo "================================="
	@echo "Original (dll_pdf_fabric.py):     ~1.5 files/sec  | ~2.5 days total"
	@echo "Turbo Conservative (5 workers):   ~7-10 files/sec | ~12-18 hours"
	@echo "Turbo Normal (10 workers):        ~10-15 files/sec| ~7-10 hours"
	@echo "Turbo Fast (15 workers):          ~15-20 files/sec| ~5-7 hours"
	@echo "Turbo Maximum (25 workers):       ~20-35 files/sec| ~3-5 hours"
	@echo ""
	@echo "💡 Recommendation: Start with 'make run-turbo' for maximum speed"

# Dashboard and monitoring commands
setup-dashboard:
	@echo "📊 Dashboard dependencies are included in environment.yml"
	@echo "✅ Use 'conda env update -f environment.yml' to install dependencies"
	@echo "✅ All dependencies already installed!"

dashboard:
	@echo "🚀 Launching SharePoint Download Dashboard..."
	@echo "📊 Dashboard will be available at: http://localhost:$(DASHBOARD_PORT)"
	@echo "🔄 Real-time monitoring with 5-second refresh intervals"
	@echo "💡 Keep this terminal open while monitoring"
	@echo ""
	$(CONDA_PY) $(SIMPLE_DASHBOARD) --port $(DASHBOARD_PORT)

dashboard-enhanced:
	@echo "🚀 Launching Enhanced SharePoint Download Dashboard..."
	@echo "📊 Enhanced dashboard with detailed analytics at: http://localhost:$(DASHBOARD_ENHANCED_PORT)"
	@echo "🔄 Real-time monitoring with comprehensive statistics"
	@echo "💡 Features: File type analysis, performance metrics, error tracking"
	@echo ""
	$(CONDA_PY) $(ENHANCED_DASHBOARD) --port $(DASHBOARD_ENHANCED_PORT)

dashboard-custom:
	@echo "📊 Launching dashboard with custom settings..."
	@echo "Usage: make dashboard-custom PORT=9000 PATH=D:/alt/path"
	$(CONDA_PY) $(CUSTOM_DASHBOARD) --port $(or $(PORT),$(DASHBOARD_PORT)) --path $(or $(PATH),$(SOURCE_DIR))

analyze-logs:
	@echo "🔍 Analyzing download logs..."
	$(CONDA_PY) $(LOG_ANALYZER) --logs "*.log" "../logs/*.log" --export analysis_results.json
	@echo "📊 Log analysis complete! Results saved to analysis_results.json"

analyze-logs-chart:
	@echo "📈 Analyzing logs with performance charts..."
	$(CONDA_PY) $(LOG_ANALYZER) --logs "*.log" "../logs/*.log" --chart --export analysis_results.json

# Monitoring helpers
monitor-progress:
	@echo "📊 Current Progress Status:"
	@echo "=========================="
	@if exist "$(DOWNLOAD_PROGRESS_FILE)" (powershell -Command "$$progress = Get-Content '$(DOWNLOAD_PROGRESS_FILE)' | ConvertFrom-Json; Write-Host 'Last processed index:' $$progress.last_processed_index; Write-Host 'Successful downloads:' $$progress.results.success.Count; Write-Host 'Failed downloads:' $$progress.results.failed.Count; Write-Host 'Last update:' $$progress.timestamp") else (echo "No progress file found - progress file not present yet")

monitor-cache:
	@echo "📁 Cache File Status:"
	@echo "===================="
	@if exist "data\file_cache_optimized.json" (powershell -Command "$$cache = Get-Content 'data\file_cache_optimized.json' | ConvertFrom-Json; Write-Host 'Total files:' $$cache.files.Count; Write-Host 'Cache created:' $$cache.timestamp") else (echo "No cache file found")

# Complete monitoring suite
monitor-all:
	@echo "🚀 Complete System Monitoring"
	@echo "============================="
	@make monitor-progress
	@echo ""
	@make monitor-cache
	@echo ""
	@echo "💡 For real-time monitoring, run: make dashboard"

# Microsoft Fabric OneLake Migration
fabric-setup:
	@echo "🔧 Setting up OneLake directory structure..."
	@echo "💡 This creates the required directories in your lakehouse"
	$(CONDA_PY) $(FABRIC_SETUP_SCRIPT)

fabric-analyze:
	@echo "🔍 Analyzing files for Fabric OneLake migration..."
	$(CONDA_PY) $(FABRIC_MIGRATOR_LEGACY) --analyze-only --source "$(SOURCE_DIR)"

fabric-migrate:
	@echo "⚠️  DEPRECATED: use 'make migrate-prod' (legacy script call)"
	$(CONDA_PY) $(FABRIC_TURBO_LEGACY)

fabric-migrate-turbo:
	@echo "⚠️  DEPRECATED: use 'make migrate-turbo' (legacy turbo wrapper)"
	$(CONDA_PY) $(FABRIC_TURBO_LEGACY) --mode turbo

fabric-migrate-turbo-conservative:
	@echo "⚠️  DEPRECATED: use 'make migrate-working' (legacy working mode)"
	$(CONDA_PY) $(FABRIC_TURBO_LEGACY) --mode working

fabric-migrate-resume:
	@echo "🔄 Resuming Fabric OneLake migration (legacy script)..."
	$(CONDA_PY) $(FABRIC_MIGRATOR_LEGACY) --resume --source "$(SOURCE_DIR)" --batch-size 50

fabric-migrate-turbo-resume:
	@echo "🔄 Resuming OPTIMIZED Fabric OneLake migration..."
	$(CONDA_PY) $(FABRIC_TURBO_FIXED) --source "$(SOURCE_DIR)" --workers 25 --resume

fabric-test:
	@echo "🧪 Testing unified migrator with 5 batches (test-run)"
	$(MIGRATE_SHELL) $(MIGRATE_ENV_BOOTSTRAP) --test-run

fabric-test-single:
	@echo "🧪 Testing unified migrator single-batch (batch size override)"
	$(MIGRATE_SHELL) $(MIGRATE_ENV_BOOTSTRAP) --batch-size 1 --max-batches 1

fabric-create-directories:
	@echo "🏗️ Analyzing directory structure for OneLake..."
	@echo "💡 This analyzes your files and provides manual creation guide"
	$(CONDA_PY) $(FABRIC_ANALYZE_STRUCTURE)

fabric-get-token:
	@echo "🔑 Getting Azure access token for Fabric API..."
	powershell -ExecutionPolicy Bypass -File "$(GET_TOKEN_SCRIPT)"

fabric-create-directories-api:
	@echo "🏗️ Creating OneLake directories via API..."
	@echo "💡 Requires ACCESS_TOKEN in .env file (run 'make fabric-get-token' first)"
	$(CONDA_PY) $(FABRIC_CREATE_DIRS_API)

fabric-migrate-azcopy:
	@echo "🚀 Starting AzCopy migration to OneLake..."
	@echo "⚡ High-performance migration using Microsoft AzCopy"
	@echo "💡 Override WORKSPACE_ID / LAKEHOUSE_ID / AZCOPY_SOURCE as needed"
	@echo "   Example: make WORKSPACE_ID=xxxx LAKEHOUSE_ID=yyyy AZCOPY_SOURCE=D:/data fabric-migrate-azcopy"
	powershell -NoLogo -NoProfile -Command "if ('$(WORKSPACE_ID)' -eq 'YOUR_WORKSPACE_ID' -or '$(LAKEHOUSE_ID)' -eq 'YOUR_LAKEHOUSE_ID') { Write-Host '❌ WORKSPACE_ID / LAKEHOUSE_ID not set (pass via make variables)'; exit 1 }"
	powershell -ExecutionPolicy Bypass -File "$(AZCOPY_SCRIPT)" $(AZCOPY_ARGS)

fabric-migrate-azcopy-dryrun:
	@echo "🧪 AzCopy dry run - no files will be transferred..."
	powershell -NoLogo -NoProfile -Command "if ('$(WORKSPACE_ID)' -eq 'YOUR_WORKSPACE_ID' -or '$(LAKEHOUSE_ID)' -eq 'YOUR_LAKEHOUSE_ID') { Write-Host '❌ WORKSPACE_ID / LAKEHOUSE_ID not set (pass via make variables)'; exit 1 }"
	powershell -ExecutionPolicy Bypass -File "$(AZCOPY_SCRIPT)" $(AZCOPY_ARGS) -DryRun

fabric-setup-fileexplorer:
	@echo "🗂️ Setting up OneLake File Explorer..."
	powershell -ExecutionPolicy Bypass -File "$(FILE_EXPLORER_SETUP)"

fabric-help:
	@echo "🏗️ Microsoft Fabric OneLake Migration Commands"
	@echo "==============================================="
	@echo "Setup (REQUIRED FIRST):"
	@echo "  make fabric-create-directories  - 🔧 Analyze structure & get manual creation guide"
	@echo "  make fabric-get-token          - 🔑 Get Azure access token for API methods"
	@echo "  make fabric-create-directories-api - 🤖 Create directories via API (experimental)"
	@echo "  make fabric-setup               - 🔧 Legacy directory creation method"
	@echo "  make fabric-setup-fileexplorer  - 🗂️ Setup OneLake File Explorer"
	@echo ""
	@echo "🚀 MIGRATION METHODS:"
	@echo ""
	@echo "Method 1: API-Based (Current approach)"
	@echo "  make fabric-migrate-turbo       - 25 workers (~4-7 hours) 🏆 PYTHON API"
	@echo "  make fabric-migrate-turbo-conservative - 10 workers (~7-10 hours)"
	@echo "  make fabric-migrate             - Single-threaded (~21-52 hours)"
	@echo ""
	@echo "Method 2: AzCopy (Microsoft's high-performance tool)"
	@echo "  make fabric-migrate-azcopy-dryrun - 🧪 Test AzCopy without transferring"
	@echo "  make fabric-migrate-azcopy      - 🚀 AzCopy migration (FASTEST)"
	@echo ""
	@echo "Method 3: OneLake File Explorer (GUI drag-and-drop)"
	@echo "  make fabric-setup-fileexplorer  - Setup instructions for GUI method"
	@echo ""
	@echo "Analysis & Testing:"
	@echo "  make fabric-analyze             - Analyze files for migration (safe)"
	@echo "  make fabric-test                - Test migration with 5 files"
	@echo "  make fabric-test-single         - Test with 1 file"
	@echo ""
	@echo "📊 Performance Comparison (376,882 files):"
	@echo "  Python API Turbo:  15-25 files/sec | 4-7 hours"
	@echo "  AzCopy:            50-100 files/sec | 1-2 hours 🏆 FASTEST"
	@echo "  File Explorer:     Manual batches  | Variable"
	@echo ""
	@echo "🎯 RECOMMENDED APPROACH:"
	@echo "  1. make fabric-create-directories   (Analyze & get creation guide)"
	@echo "  2. Create folders manually in Fabric portal"
	@echo "  3. make fabric-test-single         (Test single file)"
	@echo "  4. make fabric-migrate-azcopy      (Full migration - FASTEST)"
	@echo ""
	@echo "📋 Prerequisites:"
	@echo "  • Update .env with FABRIC_WORKSPACE_ID and FABRIC_LAKEHOUSE_ID"
	@echo "  • Azure AD app with Fabric permissions"
	@echo "  • For AzCopy: Install AzCopy and authenticate with 'azcopy login'"
	@echo "  • Read docs/FABRIC_MIGRATION_GUIDE.md for setup details"
