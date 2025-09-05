# OneLake Migration Codebase Cleanup Script
# Removes empty files and resolves duplicates to maintain clean structure

Write-Host "Starting Commercial_ACA_taskforce Codebase Cleanup..." -ForegroundColor Green

# Define base directory
$BaseDir = "C:\Users\sibitoye\Documents\HS2_PROJECTS_2025\Commercial_ACA_taskforce"
Set-Location $BaseDir

Write-Host "`nCleanup Summary:" -ForegroundColor Yellow

# 1. Remove empty Python files that are duplicates of files in src/
Write-Host "`n1. Removing empty duplicate Python files..." -ForegroundColor Cyan

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
            Write-Host "   Removed empty duplicate: $file" -ForegroundColor Green
        } else {
            Write-Host "   Skipped $file - not empty ($($fileInfo.Length) bytes)" -ForegroundColor Yellow
        }
    } else {
        Write-Host "   File not found: $file" -ForegroundColor Gray
    }
}

# 2. Consolidate duplicate data files (keep data/ versions)
Write-Host "`n2. Consolidating duplicate data files..." -ForegroundColor Cyan

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
            Write-Host "   Removed duplicate: $rootFile (kept $dataFile)" -ForegroundColor Green
        } else {
            Write-Host "   Size mismatch - Root: $rootSize bytes, Data: $dataSize bytes" -ForegroundColor Yellow
        }
    }
}

# 3. Handle documentation (keep root versions, archive docs/)
Write-Host "`n3. Organizing documentation..." -ForegroundColor Cyan

# Create docs archive if needed
if (-not (Test-Path "docs/archive")) {
    New-Item -ItemType Directory -Path "docs/archive" -Force | Out-Null
    Write-Host "   Created docs/archive directory" -ForegroundColor Gray
}

$DocFiles = @("README.md", "QUICK_START.md")

foreach ($docFile in $DocFiles) {
    $rootDoc = $docFile
    $docsDoc = "docs/$docFile"
    
    if ((Test-Path $rootDoc) -and (Test-Path $docsDoc)) {
        # Move docs version to archive
        Move-Item $docsDoc "docs/archive/$docFile" -Force
        Write-Host "   Moved docs/$docFile to docs/archive/" -ForegroundColor Green
    }
}

# 4. Handle PowerShell script duplicate
Write-Host "`n4. Consolidating PowerShell scripts..." -ForegroundColor Cyan

if ((Test-Path "reorganize_codebase.ps1") -and (Test-Path "scripts/powershell/reorganize_codebase.ps1")) {
    $rootSize = (Get-Item "reorganize_codebase.ps1").Length
    $scriptsSize = (Get-Item "scripts/powershell/reorganize_codebase.ps1").Length
    
    if ($rootSize -eq $scriptsSize) {
        Remove-Item "reorganize_codebase.ps1" -Force
        Write-Host "   Removed duplicate: reorganize_codebase.ps1 (kept scripts/powershell/ version)" -ForegroundColor Green
    } else {
        Write-Host "   Size difference - keeping both for manual review" -ForegroundColor Yellow
    }
}

# 5. Summary
Write-Host "`nCleanup Complete!" -ForegroundColor Green
Write-Host "   - Removed empty duplicate Python files" -ForegroundColor White
Write-Host "   - Consolidated data files to data/ directory" -ForegroundColor White
Write-Host "   - Organized documentation with archive" -ForegroundColor White
Write-Host "   - Maintained clean directory structure" -ForegroundColor White

Write-Host "`nDirectory is now clean and coherent!" -ForegroundColor Green
