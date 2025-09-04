# OneLake File Explorer Setup Script
# This script helps set up OneLake File Explorer for drag-and-drop migration

Write-Host "🗂️ OneLake File Explorer Setup Guide" -ForegroundColor Magenta
Write-Host "====================================" -ForegroundColor Magenta

Write-Host ""
Write-Host "📋 Prerequisites:" -ForegroundColor Yellow
Write-Host "1. ✅ OneLake File Explorer installed" -ForegroundColor White
Write-Host "2. ✅ Signed in to Microsoft Fabric" -ForegroundColor White
Write-Host "3. ✅ Access to workspace: COE_F_EUC_P2" -ForegroundColor White

Write-Host ""
Write-Host "🔗 Installation Steps:" -ForegroundColor Green
Write-Host "1. Download OneLake File Explorer from Microsoft Store" -ForegroundColor White
Write-Host "2. Install and launch the application" -ForegroundColor White
Write-Host "3. Sign in with your Microsoft 365 account" -ForegroundColor White

Write-Host ""
Write-Host "📁 Mount Instructions:" -ForegroundColor Green
Write-Host "1. In OneLake File Explorer, navigate to:" -ForegroundColor White
Write-Host "   Workspaces > COE_F_EUC_P2 > si_dev_lakehouse" -ForegroundColor Cyan
Write-Host "2. Right-click on 'Files' folder" -ForegroundColor White
Write-Host "3. Select 'Sync' or 'Add to OneDrive'" -ForegroundColor White
Write-Host "4. The lakehouse will appear as a mapped drive" -ForegroundColor White

Write-Host ""
Write-Host "📂 Migration Process:" -ForegroundColor Green
Write-Host "1. Open Windows File Explorer" -ForegroundColor White
Write-Host "2. Navigate to source: C:\commercial_pdfs\downloaded_files" -ForegroundColor Cyan
Write-Host "3. Navigate to OneLake mounted drive" -ForegroundColor White
Write-Host "4. Create folder: SharePoint_Invoices" -ForegroundColor White
Write-Host "5. Copy/paste or drag-and-drop files" -ForegroundColor White

Write-Host ""
Write-Host "⚡ Performance Tips:" -ForegroundColor Yellow
Write-Host "• Copy folders in smaller batches (1000-5000 files at a time)" -ForegroundColor White
Write-Host "• Use robocopy for better progress tracking:" -ForegroundColor White
Write-Host "  robocopy ""C:\commercial_pdfs\downloaded_files"" ""X:\SharePoint_Invoices"" /E /MT:8 /R:3 /W:10" -ForegroundColor Cyan
Write-Host "• Monitor network usage to avoid timeouts" -ForegroundColor White

Write-Host ""
Write-Host "🚨 Known Limitations:" -ForegroundColor Red
Write-Host "• Maximum file size: 100 GB per file" -ForegroundColor White
Write-Host "• Path length limit: 400 characters" -ForegroundColor White
Write-Host "• Special characters in filenames may cause issues" -ForegroundColor White
Write-Host "• Large batches may timeout" -ForegroundColor White

Write-Host ""
Write-Host "🔍 Troubleshooting:" -ForegroundColor Yellow
Write-Host "• If sync fails, try smaller batches" -ForegroundColor White
Write-Host "• Restart OneLake File Explorer if it becomes unresponsive" -ForegroundColor White
Write-Host "• Check network connectivity and Fabric service status" -ForegroundColor White

# Function to check OneLake File Explorer installation
function Test-OneLakeFileExplorer {
    $oneLakeApp = Get-AppxPackage | Where-Object { $_.Name -like "*OneLake*" -or $_.Name -like "*Fabric*" }
    
    if ($oneLakeApp) {
        Write-Host "✅ OneLake File Explorer found: $($oneLakeApp.Name)" -ForegroundColor Green
        return $true
    } else {
        Write-Host "❌ OneLake File Explorer not found" -ForegroundColor Red
        Write-Host "📥 Install from Microsoft Store: ms-windows-store://pdp/?productid=9NQV8L9M6V3N" -ForegroundColor Yellow
        return $false
    }
}

Write-Host ""
Write-Host "🔍 Checking installation..." -ForegroundColor Yellow
Test-OneLakeFileExplorer

Write-Host ""
Write-Host "📖 For detailed setup instructions, visit:" -ForegroundColor Cyan
Write-Host "https://docs.microsoft.com/en-us/fabric/onelake/onelake-file-explorer" -ForegroundColor Blue
