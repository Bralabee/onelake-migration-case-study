# AzCopy Migration Script for OneLake
# This script uses AzCopy for high-performance file migration to Microsoft Fabric OneLake

param(
    [Parameter(Mandatory=$true)]
    [string]$SourcePath = "C:\commercial_pdfs\downloaded_files",
    
    [Parameter(Mandatory=$true)]
    [string]$WorkspaceId = "abc64232-25a2-499d-90ae-9fe5939ae437",
    
    [Parameter(Mandatory=$true)]
    [string]$LakehouseId = "a622b04f-1094-4f9b-86fd-5105f4778f76",
    
    [string]$DestinationPath = "Files/SharePoint_Invoices",
    
    [int]$ConcurrentConnections = 100,
    
    [switch]$DryRun = $false
)

# Function to check if AzCopy is installed
function Test-AzCopy {
    try {
        $azcopyVersion = azcopy --version
        Write-Host "✅ AzCopy found: $azcopyVersion" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "❌ AzCopy not found. Please install AzCopy first." -ForegroundColor Red
        Write-Host "📥 Download from: https://docs.microsoft.com/en-us/azure/storage/common/storage-use-azcopy-v10" -ForegroundColor Yellow
        return $false
    }
}

# Function to authenticate with Azure AD
function Initialize-AzAuth {
    Write-Host "🔐 Authenticating with Azure AD..." -ForegroundColor Yellow
    
    # Login using device code flow (interactive)
    azcopy login
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Authentication successful!" -ForegroundColor Green
        return $true
    } else {
        Write-Host "❌ Authentication failed!" -ForegroundColor Red
        return $false
    }
}

# Function to construct OneLake URL
function Get-OneLakeUrl {
    param(
        [string]$WorkspaceId,
        [string]$LakehouseId,
        [string]$Path
    )
    
    return "https://onelake.dfs.fabric.microsoft.com/$WorkspaceId/$LakehouseId/$Path"
}

# Function to perform the migration
function Start-Migration {
    param(
        [string]$Source,
        [string]$Destination,
        [int]$Connections,
        [bool]$IsDryRun
    )
    
    Write-Host "🚀 Starting migration..." -ForegroundColor Green
    Write-Host "📁 Source: $Source" -ForegroundColor Cyan
    Write-Host "🎯 Destination: $Destination" -ForegroundColor Cyan
    Write-Host "🔗 Concurrent connections: $Connections" -ForegroundColor Cyan
    
    # Construct AzCopy command
    $azcopyArgs = @(
        "sync"
        $Source
        $Destination
        "--recursive"
        "--cap-mbps", "1000"  # Limit bandwidth to 1 Gbps
        "--concurrent-tasks", $Connections
        "--log-level", "INFO"
        "--overwrite", "ifSourceNewer"
    )
    
    if ($IsDryRun) {
        $azcopyArgs += "--dry-run"
        Write-Host "🧪 DRY RUN MODE - No files will be transferred" -ForegroundColor Yellow
    }
    
    # Execute AzCopy
    Write-Host "⚡ Executing AzCopy command..." -ForegroundColor Green
    Write-Host "Command: azcopy $($azcopyArgs -join ' ')" -ForegroundColor Gray
    
    $startTime = Get-Date
    & azcopy @azcopyArgs
    $endTime = Get-Date
    
    $duration = $endTime - $startTime
    Write-Host "⏱️ Migration completed in: $($duration.ToString('hh\:mm\:ss'))" -ForegroundColor Green
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Migration successful!" -ForegroundColor Green
    } else {
        Write-Host "❌ Migration failed with exit code: $LASTEXITCODE" -ForegroundColor Red
    }
}

# Function to analyze source directory
function Get-MigrationStats {
    param([string]$Path)
    
    Write-Host "📊 Analyzing source directory..." -ForegroundColor Yellow
    
    $files = Get-ChildItem -Path $Path -Recurse -File
    $totalFiles = $files.Count
    $totalSize = ($files | Measure-Object -Property Length -Sum).Sum
    $totalSizeGB = [math]::Round($totalSize / 1GB, 2)
    
    Write-Host "📁 Total files: $totalFiles" -ForegroundColor Cyan
    Write-Host "💾 Total size: $totalSizeGB GB" -ForegroundColor Cyan
    
    # Estimate transfer time based on typical AzCopy performance
    $estimatedHours = [math]::Round($totalFiles / 50 / 3600, 1)  # ~50 files/sec average
    Write-Host "⏱️ Estimated time: ~$estimatedHours hours" -ForegroundColor Cyan
    
    return @{
        Files = $totalFiles
        SizeGB = $totalSizeGB
        EstimatedHours = $estimatedHours
    }
}

# Main execution
Write-Host "🏗️ Microsoft Fabric OneLake Migration with AzCopy" -ForegroundColor Magenta
Write-Host "=================================================" -ForegroundColor Magenta

# Check prerequisites
if (-not (Test-AzCopy)) {
    exit 1
}

if (-not (Test-Path $SourcePath)) {
    Write-Host "❌ Source path does not exist: $SourcePath" -ForegroundColor Red
    exit 1
}

# Analyze source
$stats = Get-MigrationStats -Path $SourcePath

# Authenticate
if (-not (Initialize-AzAuth)) {
    exit 1
}

# Construct destination URL
$destinationUrl = Get-OneLakeUrl -WorkspaceId $WorkspaceId -LakehouseId $LakehouseId -Path $DestinationPath

# Confirm migration
if (-not $DryRun) {
    Write-Host ""
    Write-Host "⚠️ WARNING: This will transfer $($stats.Files) files ($($stats.SizeGB) GB) to OneLake" -ForegroundColor Yellow
    Write-Host "💰 This may incur Azure charges based on data transfer and storage" -ForegroundColor Yellow
    $confirm = Read-Host "Continue? (y/N)"
    
    if ($confirm -ne "y" -and $confirm -ne "Y") {
        Write-Host "❌ Migration cancelled by user" -ForegroundColor Red
        exit 0
    }
}

# Start migration
Start-Migration -Source $SourcePath -Destination $destinationUrl -Connections $ConcurrentConnections -IsDryRun $DryRun

Write-Host ""
Write-Host "📋 Migration Summary:" -ForegroundColor Green
Write-Host "  Source: $SourcePath" -ForegroundColor White
Write-Host "  Destination: $destinationUrl" -ForegroundColor White
Write-Host "  Mode: $(if ($DryRun) { 'DRY RUN' } else { 'LIVE MIGRATION' })" -ForegroundColor White
