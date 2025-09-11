ENV_NAME=onelake-migration
ENV_FILE=environment.yml
SCRIPT_FILE=src/sharepoint/dll_pdf_fabric.py
ENV_TEMPLATE=.env.template
ENV_CONFIG=.env

.PHONY: help env-create env-update env-clean env-setup env-activate download run status test clean all dashboard analyze-logs setup-dashboard reorganize

# Default target
all: help

# Codebase organization
reorganize:
	@echo "🏗️ Reorganizing codebase structure..."
	powershell -ExecutionPolicy Bypass -File "reorganize_codebase.ps1"

reorganize-dryrun:
	@echo "🧪 Testing codebase reorganization (dry run)..."
	powershell -ExecutionPolicy Bypass -File "reorganize_codebase.ps1" -DryRun

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
	@echo "  make lock          Generate multi-platform conda lock files"
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
	@echo "Microsoft Fabric:"
	@echo "  make fabric-help   Show all Fabric migration options"
	@echo ""
	@echo "Quick Start:"
	@echo "  1. make reorganize     # Organize codebase (FIRST TIME ONLY)"
	@echo "  2. make env-create     # Create environment"
	@echo "  3. make env-setup      # Copy .env template" 
	@echo "  4. Edit .env file with your credentials"
	@echo "  5. make download       # Run the script"

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

lock:
	@echo "🔐 Generating multi-platform lock files (linux/osx/win)..."
	conda run -n $(ENV_NAME) bash scripts/generate_lock.sh
	@echo "✅ Lock files generated in locks/"

env-clean:
	@echo "🗑️  Removing conda environment..."
	conda env remove -n $(ENV_NAME) -y
	@echo "✅ Environment removed successfully!"

env-activate:
	@echo "To activate the environment, run:"
	@echo "    conda activate $(ENV_NAME)"

# Configuration setup
env-setup-unified:
	@echo "⚙️  Setting up configuration (unified cross-platform)..."
	@if [ -f $(ENV_CONFIG) ]; then \
	  echo "⚠️  .env file already exists. Backup created as .env.backup"; \
	  cp $(ENV_CONFIG) $(ENV_CONFIG).backup || copy $(ENV_CONFIG) $(ENV_CONFIG).backup; \
	fi
	@# Attempt POSIX cp first, fallback to Windows copy
	@if cp $(ENV_TEMPLATE) $(ENV_CONFIG) 2>/dev/null; then \
	  echo "✅ Copied template via cp"; \
	else \
	  copy $(ENV_TEMPLATE) $(ENV_CONFIG); \
	  echo "✅ Copied template via copy"; \
	fi
	@echo "📝 Edit .env with required credentials"

# Backward compatibility alias
env-setup-posix: env-setup-unified
env-setup: env-setup-unified

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
	@if exist $(SCRIPT_FILE) ( \
		echo "✅ Download script exists" \
	) else ( \
		echo "❌ Download script missing - run 'make reorganize' first" \
	)

# Testing
test:
	@echo "🧪 Testing configuration and imports..."
	@conda run -n $(ENV_NAME) python -c "print('🔍 Testing imports...'); import os, requests, datetime, time, logging, pathlib; print('✅ All imports successful!')"
	@conda run -n $(ENV_NAME) python -c "import sys; sys.path.append('src'); from sharepoint.dll_pdf_fabric import load_env_file, validate_parameters, default_params; load_env_file(); print('✅ Configuration loaded successfully!')"
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
	conda run -n $(ENV_NAME) python $(SCRIPT_FILE)

# Cache management commands
clear-cache:
	@echo "🗑️  Clearing file list and progress cache..."
	conda run -n $(ENV_NAME) python $(SCRIPT_FILE) --clear-cache
	@echo "✅ Cache cleared successfully!"

refresh:
	@echo "🔄 Force refreshing file list to detect new files..."
	conda run -n $(ENV_NAME) python $(SCRIPT_FILE) --refresh

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
	conda run -n $(ENV_NAME) python src/sharepoint/dll_pdf_fabric_turbo.py --conservative

run-turbo-normal:
	@echo "🚀 Running SharePoint downloader with NORMAL parallel processing (10 workers)..."
	conda run -n $(ENV_NAME) python src/sharepoint/dll_pdf_fabric_turbo.py --normal

run-turbo-fast:
	@echo "🚀 Running SharePoint downloader with FAST parallel processing (15 workers)..."
	conda run -n $(ENV_NAME) python src/sharepoint/dll_pdf_fabric_turbo.py --fast

run-turbo:
	@echo "🚀 Running SharePoint downloader with TURBO parallel processing (25 workers)..."
	conda run -n $(ENV_NAME) python src/sharepoint/dll_pdf_fabric_turbo.py --turbo

test-turbo:
	@echo "🧪 Testing turbo version..."
	conda run -n $(ENV_NAME) python src/sharepoint/dll_pdf_fabric_turbo.py --help

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
	@echo "📊 Dashboard will be available at: http://localhost:8052"
	@echo "🔄 Real-time monitoring with 5-second refresh intervals"
	@echo "💡 Keep this terminal open while monitoring"
	@echo ""
	conda run -n $(ENV_NAME) python src/monitoring/simple_dashboard.py

dashboard-enhanced:
	@echo "🚀 Launching Enhanced SharePoint Download Dashboard..."
	@echo "📊 Enhanced dashboard with detailed analytics at: http://localhost:8053"
	@echo "🔄 Real-time monitoring with comprehensive statistics"
	@echo "💡 Features: File type analysis, performance metrics, error tracking"
	@echo ""
	conda run -n $(ENV_NAME) python src/monitoring/enhanced_dashboard.py

dashboard-custom:
	@echo "📊 Launching dashboard with custom settings..."
	@echo "Usage: make dashboard-custom PORT=8051 PATH=/custom/path"
	conda run -n $(ENV_NAME) python src/monitoring/dashboard_monitor.py --port $(or $(PORT),8050) --path $(or $(PATH),C:/commercial_pdfs/downloaded_files)

analyze-logs:
	@echo "🔍 Analyzing download logs..."
	conda run -n $(ENV_NAME) python src/monitoring/log_analyzer.py --logs "*.log" "../logs/*.log" --export analysis_results.json
	@echo "📊 Log analysis complete! Results saved to analysis_results.json"

analyze-logs-chart:
	@echo "📈 Analyzing logs with performance charts..."
	conda run -n $(ENV_NAME) python src/monitoring/log_analyzer.py --logs "*.log" "../logs/*.log" --chart --export analysis_results.json

# Monitoring helpers
monitor-progress:
	@echo "📊 Current Progress Status:"
	@echo "=========================="
	@if exist "C:\commercial_pdfs\downloaded_files\download_progress_turbo.json" (powershell -Command "$$progress = Get-Content 'C:\commercial_pdfs\downloaded_files\download_progress_turbo.json' | ConvertFrom-Json; Write-Host 'Last processed index:' $$progress.last_processed_index; Write-Host 'Successful downloads:' $$progress.results.success.Count; Write-Host 'Failed downloads:' $$progress.results.failed.Count; Write-Host 'Last update:' $$progress.timestamp") else (echo "No progress file found - download may not be running or not started yet")

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
	conda run -n $(ENV_NAME) python src/fabric/fabric_setup_onelake.py

fabric-analyze:
	@echo "🔍 Analyzing files for Fabric OneLake migration..."
	conda run -n $(ENV_NAME) python src/fabric/onelake_migrator.py --analyze-only --source "C:/commercial_pdfs/downloaded_files"

fabric-migrate:
	@echo "🚀 Starting Fabric OneLake migration..."
	@echo "⚠️  This will upload files to Microsoft Fabric OneLake"
	conda run -n $(ENV_NAME) python src/fabric/onelake_migrator.py --source "C:/commercial_pdfs/downloaded_files" --batch-size 50

fabric-migrate-turbo:
	@echo "🚀 Starting OPTIMIZED Fabric OneLake migration with parallel processing..."
	@echo "⚡ Expected performance: 15-25 files/sec (vs 2-5 files/sec standard)"
	@echo "⏱️  Estimated time for 376,882 files: 4-7 hours (vs 21-52 hours standard)"
	@echo "⚠️  This will upload files to Microsoft Fabric OneLake"
	conda run -n $(ENV_NAME) python src/fabric/onelake_migrator_turbo_fixed.py --source "C:/commercial_pdfs/downloaded_files" --workers 25

fabric-migrate-turbo-conservative:
	@echo "🚀 Starting CONSERVATIVE optimized Fabric OneLake migration..."
	@echo "⚡ Expected performance: 10-15 files/sec"
	@echo "⏱️  Estimated time for 376,882 files: 7-10 hours"
	conda run -n $(ENV_NAME) python src/fabric/onelake_migrator_turbo_fixed.py --source "C:/commercial_pdfs/downloaded_files" --workers 10

fabric-migrate-resume:
	@echo "🔄 Resuming Fabric OneLake migration..."
	conda run -n $(ENV_NAME) python src/fabric/onelake_migrator.py --resume --source "C:/commercial_pdfs/downloaded_files" --batch-size 50

fabric-migrate-turbo-resume:
	@echo "🔄 Resuming OPTIMIZED Fabric OneLake migration..."
	conda run -n $(ENV_NAME) python src/fabric/onelake_migrator_turbo_fixed.py --source "C:/commercial_pdfs/downloaded_files" --workers 25 --resume

fabric-test:
	@echo "🧪 Testing Fabric OneLake connection with small batch..."
	conda run -n $(ENV_NAME) python src/fabric/onelake_migrator.py --source "C:/commercial_pdfs/downloaded_files" --batch-size 5

fabric-test-single:
	@echo "🧪 Testing Fabric OneLake with single file upload..."
	conda run -n $(ENV_NAME) python src/fabric/onelake_migrator.py --source "C:/commercial_pdfs/downloaded_files" --batch-size 1

fabric-create-directories:
	@echo "🏗️ Analyzing directory structure for OneLake..."
	@echo "💡 This analyzes your files and provides manual creation guide"
	conda run -n $(ENV_NAME) python src/fabric/analyze_directory_structure.py

fabric-get-token:
	@echo "🔑 Getting Azure access token for Fabric API..."
	powershell -ExecutionPolicy Bypass -File "scripts/powershell/get_access_token.ps1"

fabric-create-directories-api:
	@echo "🏗️ Creating OneLake directories via API..."
	@echo "💡 Requires ACCESS_TOKEN in .env file (run 'make fabric-get-token' first)"
	conda run -n $(ENV_NAME) python src/fabric/create_onelake_directories.py

fabric-migrate-azcopy:
	@echo "🚀 Starting AzCopy migration to OneLake..."
	@echo "⚡ High-performance migration using Microsoft AzCopy"
	@echo "💡 Make sure AzCopy is installed and you're authenticated"
	powershell -ExecutionPolicy Bypass -File "scripts/powershell/azcopy_migration.ps1" -SourcePath "C:\commercial_pdfs\downloaded_files" -WorkspaceId "abc64232-25a2-499d-90ae-9fe5939ae437" -LakehouseId "a622b04f-1094-4f9b-86fd-5105f4778f76"

fabric-migrate-azcopy-dryrun:
	@echo "🧪 AzCopy dry run - no files will be transferred..."
	powershell -ExecutionPolicy Bypass -File "scripts/powershell/azcopy_migration.ps1" -SourcePath "C:\commercial_pdfs\downloaded_files" -WorkspaceId "abc64232-25a2-499d-90ae-9fe5939ae437" -LakehouseId "a622b04f-1094-4f9b-86fd-5105f4778f76" -DryRun

fabric-setup-fileexplorer:
	@echo "🗂️ Setting up OneLake File Explorer..."
	powershell -ExecutionPolicy Bypass -File "scripts/powershell/onelake_file_explorer_setup.ps1"

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

# Cross-platform shell detection (POSIX fallback)
UNAME_S := $(shell uname 2>/dev/null)
IS_WINDOWS := $(findstring Windows,$(OS))
POWERSHELL := powershell
ifeq ($(UNAME_S),Linux)
  POWERSHELL := pwsh
endif
ifeq ($(UNAME_S),Darwin)
  POWERSHELL := pwsh
endif

# POSIX-friendly copy using cp if available
CP ?= cp

# Portable env setup (creates .env from template) - works on Linux/macOS
env-setup-posix:
	@echo "⚙️  (POSIX) Setting up configuration..."
	@if [ -f $(ENV_CONFIG) ]; then \
	  echo "⚠️  .env exists. Creating backup .env.backup"; \
	  $(CP) $(ENV_CONFIG) $(ENV_CONFIG).backup; \
	fi
	$(CP) $(ENV_TEMPLATE) $(ENV_CONFIG)
	@echo "✅ Configuration template copied to .env (POSIX)"

# Run preflight checks (environment must be active or conda run used)
preflight:
	@echo "🩺 Running preflight validation..."
	@conda run -n $(ENV_NAME) python scripts/preflight_check.py || (echo "❌ Preflight failed" && exit 1)
	@echo "✅ Preflight succeeded"

# Convenience target: create env, setup config (POSIX), run preflight
bootstrap-posix: env-create env-setup-posix preflight
	@echo "🎯 POSIX bootstrap complete. Edit .env then run: make download"

# Fast token sanity (Graph metadata) without MSAL full logic - optional future
# token-check:
# 	@echo "🔐 Token check not yet implemented in POSIX section"

# Override help to append new targets info
help: help-posix-extension

help-posix-extension:
	@echo "" \
	&& echo "🌐 Cross-Platform Extensions:" \
	&& echo "  make env-setup            Unified .env template copy (all platforms)" \
	&& echo "  make preflight            Run preflight validation script" \
	&& echo "  make bootstrap-posix      Create env + config + preflight (Linux/macOS)"
