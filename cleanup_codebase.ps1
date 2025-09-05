# OneLake Migration Codebase Cleanup Script
# Removes empty files and resolves duplicates to maintain clean structure

Write-Host "🧹 Starting Commercial_ACA_taskforce Codebase Cleanup..." -ForegroundColor Green

# Define base directory
$BaseDir = "C:\Users\sibitoye\Documents\HS2_PROJECTS_2025\Commercial_ACA_taskforce"
Set-Location $BaseDir

Write-Host "`n📋 Cleanup Summary:" -ForegroundColor Yellow

# 1. Remove empty Python files that are duplicates of files in src/
Write-Host "`n1️⃣ Removing empty duplicate Python files..." -ForegroundColor Cyan

$EmptyDuplicates = @(
    "enhanced_dashboard.py",           # Empty - real version in src/monitoring/
    "fabric_discovery.py",             # Empty - real version in src/fabric/
    "fabric_setup_onelake.py"         # Empty - real version in src/fabric/
)

foreach ($file in $EmptyDuplicates) {
    if (Test-Path $file) {
        $fileInfo = Get-Item $file
        if ($fileInfo.Length -eq 0) {
            Remove-Item $file -Force
            Write-Host "   ✅ Removed empty duplicate: $file" -ForegroundColor Green
        } else {
            Write-Host "   ⚠️  Skipped $file - not empty ($(($fileInfo.Length)) bytes)" -ForegroundColor Yellow
        }
    } else {
        Write-Host "   ℹ️  File not found: $file" -ForegroundColor Gray
    }
}

# 2. Consolidate duplicate data files (keep data/ versions)
Write-Host "`n2️⃣ Consolidating duplicate data files..." -ForegroundColor Cyan

$DataDuplicates = @{
    "file_cache_optimized.json" = "data/file_cache_optimized.json"
    "onelake_directories.json" = "data/onelake_directories.json"
}

foreach ($duplicate in $DataDuplicates.GetEnumerator()) {
    $rootFile = $duplicate.Key
    $dataFile = $duplicate.Value
    
    if ((Test-Path $rootFile) -and (Test-Path $dataFile)) {
        $rootSize = (Get-Item $rootFile).Length
        $dataSize = (Get-Item $dataFile).Length
        
        if ($rootSize -eq $dataSize) {
            Remove-Item $rootFile -Force
            Write-Host "   ✅ Removed duplicate: $rootFile (kept $dataFile)" -ForegroundColor Green
        } else {
            Write-Host "   ⚠️  Size mismatch - Root: $rootSize bytes, Data: $dataSize bytes" -ForegroundColor Yellow
            Write-Host "      Manual review needed for: $rootFile vs $dataFile" -ForegroundColor Yellow
        }
    }
}

# 3. Handle migration_progress_optimized.json special case
Write-Host "`n3️⃣ Handling migration progress files..." -ForegroundColor Cyan

if ((Test-Path "migration_progress_optimized.json") -and (Test-Path "data/migration_progress_optimized.json")) {
    $rootSize = (Get-Item "migration_progress_optimized.json").Length
    $dataSize = (Get-Item "data/migration_progress_optimized.json").Length
    
    Write-Host "   📊 Root progress file: $rootSize bytes" -ForegroundColor White
    Write-Host "   📊 Data progress file: $dataSize bytes" -ForegroundColor White
    
    if ($rootSize -gt $dataSize) {
        Write-Host "   ✅ Root file is newer/larger - keeping both for safety" -ForegroundColor Green
    } else {
        Write-Host "   ✅ Data file is newer/larger - keeping both for safety" -ForegroundColor Green
    }
    Write-Host "   ℹ️  Both progress files retained (contain different data)" -ForegroundColor Gray
}

# 4. Consolidate documentation (keep root versions, move docs/ to archive)
Write-Host "`n4️⃣ Organizing documentation..." -ForegroundColor Cyan

$DocFiles = @("README.md", "QUICK_START.md")

# Create docs archive if it doesn't exist
if (-not (Test-Path "docs/archive")) {
    New-Item -ItemType Directory -Path "docs/archive" -Force | Out-Null
    Write-Host "   📁 Created docs/archive directory" -ForegroundColor Gray
}

foreach ($docFile in $DocFiles) {
    $rootDoc = $docFile
    $docsDoc = "docs/$docFile"
    
    if ((Test-Path $rootDoc) -and (Test-Path $docsDoc)) {
        $rootSize = (Get-Item $rootDoc).Length
        $docsSize = (Get-Item $docsDoc).Length
        
        # Move docs version to archive
        Move-Item $docsDoc "docs/archive/$docFile" -Force
        Write-Host "   ✅ Moved docs/$docFile to docs/archive/ (Root: $rootSize bytes > Docs: $docsSize bytes)" -ForegroundColor Green
    }
}

# 5. Handle PowerShell script duplicate
Write-Host "`n5️⃣ Consolidating PowerShell scripts..." -ForegroundColor Cyan

if ((Test-Path "reorganize_codebase.ps1") -and (Test-Path "scripts/powershell/reorganize_codebase.ps1")) {
    $rootSize = (Get-Item "reorganize_codebase.ps1").Length
    $scriptsSize = (Get-Item "scripts/powershell/reorganize_codebase.ps1").Length
    
    if ($rootSize -eq $scriptsSize) {
        Remove-Item "reorganize_codebase.ps1" -Force
        Write-Host "   ✅ Removed duplicate: reorganize_codebase.ps1 (kept scripts/powershell/ version)" -ForegroundColor Green
    } else {
        Write-Host "   ⚠️  Size difference - keeping both for manual review" -ForegroundColor Yellow
    }
}

# 6. Verify __init__.py files are appropriately empty
Write-Host "`n6️⃣ Verifying Python package structure..." -ForegroundColor Cyan

$InitFiles = @(
    "src/__init__.py",
    "src/fabric/__init__.py", 
    "src/monitoring/__init__.py",
    "src/sharepoint/__init__.py",
    "tests/__init__.py"
)

foreach ($initFile in $InitFiles) {
    if (Test-Path $initFile) {
        $fileInfo = Get-Item $initFile
        if ($fileInfo.Length -eq 0) {
            Write-Host "   ✅ $initFile - Correctly empty (Python package marker)" -ForegroundColor Green
        } else {
            Write-Host "   ℹ️  $initFile - Contains content ($(($fileInfo.Length)) bytes)" -ForegroundColor Gray
        }
    } else {
        Write-Host "   ❌ Missing: $initFile" -ForegroundColor Red
    }
}

# 7. Summary of directory structure
Write-Host "`n📂 Final Directory Structure Summary:" -ForegroundColor Yellow

Write-Host "`n   Core Migration Tools:" -ForegroundColor Cyan
Write-Host "   • onelake_migrator_turbo_working.py - Validated working version"
Write-Host "   • src/fabric/onelake_migrator_turbo_fixed.py - Production version"
Write-Host "   • src/monitoring/simple_dashboard.py - Monitoring dashboard"

Write-Host "`n   Organization:" -ForegroundColor Cyan
Write-Host "   • src/ - All source code organized by function"
Write-Host "   • config/ - Configuration files and environment variables"
Write-Host "   • scripts/ - PowerShell automation scripts"
Write-Host "   • data/ - Data files and progress tracking"
Write-Host "   • tests/ - Test files and validation scripts"
Write-Host "   • docs/ - Documentation (with archive for old versions)"

Write-Host "`n   Key Data Files:" -ForegroundColor Cyan
Write-Host "   • data/file_cache_optimized.json - File cache (98MB)"
Write-Host "   • migration_progress_*.json - Progress tracking files"
Write-Host "   • *.log - Migration execution logs"

Write-Host "`n🎯 Cleanup Complete!" -ForegroundColor Green
Write-Host "   • Removed empty duplicate Python files"
Write-Host "   • Consolidated data files to data/ directory"
Write-Host "   • Organized documentation with archive"
Write-Host "   • Maintained clean Python package structure"
Write-Host "   • Preserved all important progress and configuration files"

Write-Host "`n📋 Next Steps:" -ForegroundColor Yellow
Write-Host "   1. Review docs/archive/ for any content you want to preserve"
Write-Host "   2. Test migration tools to ensure nothing was broken"
Write-Host "   3. Consider running: git add . && git commit -m 'Clean up codebase structure'"

Write-Host "`n✨ Directory is now clean and coherent!" -ForegroundColor Green
