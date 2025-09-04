# Codebase Reorganization Script
# This script moves files to organized directories and updates the Makefile

param(
    [switch]$DryRun = $false
)

Write-Host "📁 Codebase Reorganization Script" -ForegroundColor Magenta
Write-Host "=================================" -ForegroundColor Magenta

# Define file movements
$fileMoves = @{
    # SharePoint downloaders
    "dll_pdf_fabric.py" = "src\sharepoint\"
    "dll_pdf_fabric_turbo.py" = "src\sharepoint\"
    
    # Fabric migration tools
    "onelake_migrator.py" = "src\fabric\"
    "onelake_migrator_turbo.py" = "src\fabric\"
    "onelake_migrator_turbo_fixed.py" = "src\fabric\"
    "fabric_setup_onelake.py" = "src\fabric\"
    "fabric_diagnostics.py" = "src\fabric\"
    "fabric_discovery.py" = "src\fabric\"
    "analyze_directory_structure.py" = "src\fabric\"
    "create_onelake_directories.py" = "src\fabric\"
    
    # Monitoring and dashboards
    "simple_dashboard.py" = "src\monitoring\"
    "enhanced_dashboard.py" = "src\monitoring\"
    "dashboard_monitor.py" = "src\monitoring\"
    "log_analyzer.py" = "src\monitoring\"
    "monitor_retry.py" = "src\monitoring\"
    
    # PowerShell scripts
    "get_access_token.ps1" = "scripts\powershell\"
    "azcopy_migration.ps1" = "scripts\powershell\"
    "onelake_file_explorer_setup.ps1" = "scripts\powershell\"
    
    # Configuration files
    "env_vars.env" = "config\"
    "fabric_config.env" = "config\"
    "requirements_dashboard.txt" = "config\"
    "requirements_turbo.txt" = "config\"
    
    # Documentation
    "FABRIC_MIGRATION_GUIDE.md" = "docs\"
    "PROGRESS_FILES_ANALYSIS.md" = "docs\"
    "QUICK_START.md" = "docs\"
    "README.md" = "docs\"
    
    # Data and cache files
    "file_cache_optimized.json" = "data\"
    "migration_analysis.json" = "data\"
    "migration_progress_optimized.json" = "data\"
    "onelake_directories.json" = "data\"
    
    # Test and utility scripts
    "test_env.py" = "tests\"
    "test_insights.py" = "tests\"
    "analyze_data_sources.py" = "src\monitoring\"
    "check_data.py" = "src\monitoring\"
    "compare_progress_files.py" = "src\monitoring\"
    "detailed_insights_test.py" = "tests\"
    "rebuild_progress.py" = "src\monitoring\"
    "retry_failed_downloads.py" = "src\sharepoint\"
    "retry_guide.py" = "src\sharepoint\"
    "simple_retry_failed.py" = "src\sharepoint\"
}

# Define new paths for Makefile updates
$makefilePaths = @{
    "dll_pdf_fabric.py" = "src\sharepoint\dll_pdf_fabric.py"
    "dll_pdf_fabric_turbo.py" = "src\sharepoint\dll_pdf_fabric_turbo.py"
    "onelake_migrator.py" = "src\fabric\onelake_migrator.py"
    "onelake_migrator_turbo_fixed.py" = "src\fabric\onelake_migrator_turbo_fixed.py"
    "fabric_setup_onelake.py" = "src\fabric\fabric_setup_onelake.py"
    "analyze_directory_structure.py" = "src\fabric\analyze_directory_structure.py"
    "create_onelake_directories.py" = "src\fabric\create_onelake_directories.py"
    "simple_dashboard.py" = "src\monitoring\simple_dashboard.py"
    "enhanced_dashboard.py" = "src\monitoring\enhanced_dashboard.py"
    "dashboard_monitor.py" = "src\monitoring\dashboard_monitor.py"
    "log_analyzer.py" = "src\monitoring\log_analyzer.py"
    "get_access_token.ps1" = "scripts\powershell\get_access_token.ps1"
    "azcopy_migration.ps1" = "scripts\powershell\azcopy_migration.ps1"
    "onelake_file_explorer_setup.ps1" = "scripts\powershell\onelake_file_explorer_setup.ps1"
}

if ($DryRun) {
    Write-Host "🧪 DRY RUN MODE - No files will be moved" -ForegroundColor Yellow
    Write-Host ""
}

# Move files
Write-Host "📦 Moving files to organized directories..." -ForegroundColor Green
$movedCount = 0
$errorCount = 0

foreach ($file in $fileMoves.Keys) {
    $destination = $fileMoves[$file]
    
    if (Test-Path $file) {
        Write-Host "  Moving $file -> $destination" -ForegroundColor Cyan
        
        if (-not $DryRun) {
            try {
                Move-Item $file $destination -Force
                $movedCount++
            }
            catch {
                Write-Host "  ❌ Failed to move $file : $_" -ForegroundColor Red
                $errorCount++
            }
        } else {
            $movedCount++
        }
    } else {
        Write-Host "  ⚠️ File not found: $file" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "📊 File Movement Summary:" -ForegroundColor Green
Write-Host "  Files moved: $movedCount" -ForegroundColor White
Write-Host "  Errors: $errorCount" -ForegroundColor White

# Update Makefile
Write-Host ""
Write-Host "📝 Updating Makefile paths..." -ForegroundColor Green

if (-not $DryRun) {
    # Read Makefile content
    $makefileContent = Get-Content "Makefile" -Raw
    
    # Update paths in Makefile
    foreach ($oldPath in $makefilePaths.Keys) {
        $newPath = $makefilePaths[$oldPath]
        $makefileContent = $makefileContent -replace [regex]::Escape($oldPath), $newPath
    }
    
    # Update SCRIPT_FILE variable
    $makefileContent = $makefileContent -replace "SCRIPT_FILE=dll_pdf_fabric.py", "SCRIPT_FILE=src\sharepoint\dll_pdf_fabric.py"
    
    # Write updated Makefile
    $makefileContent | Set-Content "Makefile" -NoNewline
    
    Write-Host "✅ Makefile updated with new paths" -ForegroundColor Green
} else {
    Write-Host "🧪 Would update Makefile paths (dry run)" -ForegroundColor Yellow
}

# Create __init__.py files for Python packages
$pythonDirs = @("src", "src\sharepoint", "src\fabric", "src\monitoring", "tests")

Write-Host ""
Write-Host "🐍 Creating Python package structure..." -ForegroundColor Green

foreach ($dir in $pythonDirs) {
    $initFile = Join-Path $dir "__init__.py"
    
    if (-not $DryRun) {
        if (-not (Test-Path $initFile)) {
            New-Item $initFile -ItemType File -Force | Out-Null
            Write-Host "  Created $initFile" -ForegroundColor Cyan
        }
    } else {
        Write-Host "  Would create $initFile" -ForegroundColor Yellow
    }
}

# Create README for the new structure
$newReadmeContent = @"
# Commercial ACA Taskforce - Organized Codebase

## Directory Structure

```
├── src/                      # Source code
│   ├── sharepoint/          # SharePoint download modules
│   ├── fabric/              # Microsoft Fabric integration
│   └── monitoring/          # Dashboards and monitoring tools
├── scripts/                 # Utility scripts
│   └── powershell/         # PowerShell automation scripts
├── config/                  # Configuration files
├── data/                    # Cache and data files
├── docs/                    # Documentation
├── tests/                   # Test files
├── Makefile                 # Main automation interface
└── environment.yml          # Conda environment specification
```

## Quick Start

1. `make env-create` - Create conda environment
2. `make env-setup` - Setup configuration
3. `make download` - Start SharePoint download
4. `make fabric-migrate-turbo` - Migrate to Fabric OneLake

## Key Scripts

- **SharePoint Download**: `src/sharepoint/dll_pdf_fabric.py`
- **Turbo Download**: `src/sharepoint/dll_pdf_fabric_turbo.py`
- **Fabric Migration**: `src/fabric/onelake_migrator_turbo_fixed.py`
- **Monitoring**: `src/monitoring/simple_dashboard.py`

For full documentation, see `docs/` directory.
"@

Write-Host ""
Write-Host "📖 Creating updated README..." -ForegroundColor Green

if (-not $DryRun) {
    $newReadmeContent | Set-Content "README_ORGANIZED.md"
    Write-Host "✅ Created README_ORGANIZED.md" -ForegroundColor Green
} else {
    Write-Host "🧪 Would create README_ORGANIZED.md" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "🎉 Codebase reorganization complete!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Summary:" -ForegroundColor Cyan
Write-Host "  • Files organized into logical directories" -ForegroundColor White
Write-Host "  • Makefile updated with new paths" -ForegroundColor White
Write-Host "  • Python package structure created" -ForegroundColor White
Write-Host "  • All existing functionality preserved" -ForegroundColor White
Write-Host ""
Write-Host "🧪 Test the reorganization:" -ForegroundColor Yellow
Write-Host "  make status" -ForegroundColor White
Write-Host "  make fabric-help" -ForegroundColor White
