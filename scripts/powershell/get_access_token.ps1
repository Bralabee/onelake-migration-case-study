# PowerShell script to get Azure access token for Fabric API
# This script gets an access token and adds it to your .env file

param(
    [switch]$ShowToken = $false
)

Write-Host "Azure Access Token Generator for Fabric API" -ForegroundColor Magenta
Write-Host "===============================================" -ForegroundColor Magenta

# Check if Azure CLI is installed
try {
    $azVersion = az --version 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Azure CLI found" -ForegroundColor Green
    } else {
        throw "Azure CLI not found"
    }
}
catch {
    Write-Host "Azure CLI not installed" -ForegroundColor Red
    Write-Host "Install from: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli" -ForegroundColor Yellow
    exit 1
}

# Check if user is logged in
Write-Host "Checking Azure CLI login status..." -ForegroundColor Yellow
$accountInfo = az account show 2>$null | ConvertFrom-Json

if ($LASTEXITCODE -ne 0) {
    Write-Host "Not logged in to Azure CLI" -ForegroundColor Red
    Write-Host "Logging in..." -ForegroundColor Yellow
    az login
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Login failed" -ForegroundColor Red
        exit 1
    }
    
    $accountInfo = az account show | ConvertFrom-Json
}

Write-Host "Logged in as: $($accountInfo.user.name)" -ForegroundColor Green
Write-Host "Subscription: $($accountInfo.name)" -ForegroundColor Cyan

# Get access token for OneLake (Azure Storage scope)
Write-Host "Getting access token for OneLake Data Lake API..." -ForegroundColor Yellow

try {
    $tokenInfo = az account get-access-token --resource "https://storage.azure.com" | ConvertFrom-Json
    
    if ($tokenInfo.accessToken) {
        Write-Host "Access token obtained successfully!" -ForegroundColor Green
        
        if ($ShowToken) {
            Write-Host "Access Token (first 50 chars): $($tokenInfo.accessToken.Substring(0, 50))..." -ForegroundColor Gray
        }
        
        # Add token to .env file - check multiple locations
        $envPaths = @(".env", "config\.env", "..\.env", "..\config\.env")
        $envFound = $false
        
        foreach ($envPath in $envPaths) {
            if (Test-Path $envPath) {
                Write-Host "Adding ACCESS_TOKEN to $envPath file..." -ForegroundColor Yellow
                
                # Read current .env content
                $envContent = Get-Content $envPath -Raw
                
                # Remove existing ACCESS_TOKEN line if present
                $envLines = $envContent -split "`n" | Where-Object { $_ -notmatch "^ACCESS_TOKEN=" }
                
                # Add new ACCESS_TOKEN
                $envLines += "ACCESS_TOKEN=$($tokenInfo.accessToken)"
                
                # Write back to file
                $envLines -join "`n" | Set-Content $envPath -NoNewline
                
                Write-Host "ACCESS_TOKEN added to $envPath file" -ForegroundColor Green
                $envFound = $true
                break
            }
        }
        
        if (-not $envFound) {
            Write-Host ".env file not found in any of these locations: $($envPaths -join ', ')" -ForegroundColor Red
            Write-Host "Make sure you're in the project directory or have run 'make env-setup'" -ForegroundColor Yellow
        }
        
        # Show expiry info (regardless of env file status)
        $expiryTime = [DateTime]$tokenInfo.expiresOn
        $timeUntilExpiry = $expiryTime - (Get-Date)
        
        Write-Host "Token expires: $expiryTime" -ForegroundColor Yellow
        Write-Host "Valid for: $([math]::Round($timeUntilExpiry.TotalHours, 1)) hours" -ForegroundColor Yellow
        
        if ($timeUntilExpiry.TotalHours -lt 1) {
            Write-Host "Token expires soon! You may need to run this script again." -ForegroundColor Red
        }
        
    } else {
        Write-Host "Failed to get access token" -ForegroundColor Red
        exit 1
    }
}
catch {
    Write-Host "Error getting access token: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Green
Write-Host "1. Run: make fabric-create-directories" -ForegroundColor White
Write-Host "2. Follow the manual directory creation guide" -ForegroundColor White
Write-Host "3. Test with: make fabric-test-single" -ForegroundColor White
Write-Host ""
Write-Host "If token expires, run this script again: .\get_access_token.ps1" -ForegroundColor Yellow
