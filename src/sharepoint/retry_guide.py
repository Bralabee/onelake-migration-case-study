#!/usr/bin/env python3
"""
🔄 Retry Mechanisms Summary & Quick Start Guide
==============================================

This script provides an overview of all available retry mechanisms
for failed SharePoint downloads and how to use them effectively.

Available Tools:
1. simple_retry_failed.py - Automated retry with progress clearing
2. retry_failed_downloads.py - Detailed retry with fresh authentication
3. monitor_retry.py - Real-time progress monitoring
4. Dashboard monitoring at http://localhost:8051

Current Status (as of August 8, 2025):
- Total files: 413,840
- Successfully downloaded: 375,993 (90.9%)
- Failed downloads: 37,847 (9.1%)

Author: GitHub Copilot
Date: August 8, 2025
"""

import json
import subprocess
import sys
from pathlib import Path

def show_current_status():
    """Show the current download status."""
    print("📊 CURRENT DOWNLOAD STATUS")
    print("=" * 50)
    
    # Try to find the best progress file
    base_path = Path("C:/commercial_pdfs/downloaded_files")
    candidates = [
        base_path / "download_progress_turbo.json",
        base_path / "download_progress_turbo_backup_20250808_022130.json",
        base_path / "download_progress_turbo_backup_20250808_015125.json", 
        base_path / "download_progress_turbo_backup_20250807_235850.json",
        base_path / "download_progress.json"
    ]
    
    progress_file = None
    for candidate in candidates:
        if candidate.exists():
            progress_file = candidate
            break
    
    if not progress_file:
        print("❌ No progress file found!")
        return
    
    try:
        with open(progress_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        success_count = len(data.get('results', {}).get('success', []))
        failed_count = len(data.get('results', {}).get('failed', []))
        total_count = data.get('total_count', success_count + failed_count)
        completion_rate = (success_count / total_count * 100) if total_count > 0 else 0
        
        print(f"📁 Using file: {progress_file.name}")
        print(f"📈 Total files: {total_count:,}")
        print(f"✅ Successfully downloaded: {success_count:,}")
        print(f"❌ Failed downloads: {failed_count:,}")
        print(f"📊 Completion rate: {completion_rate:.1f}%")
        print(f"📉 Files remaining: {failed_count:,}")
        
    except Exception as e:
        print(f"❌ Error reading progress file: {e}")

def show_retry_options():
    """Show available retry options."""
    print("\n🔄 RETRY MECHANISMS AVAILABLE")
    print("=" * 50)
    
    print("1. 🚀 SIMPLE RETRY (Recommended)")
    print("   Command: python simple_retry_failed.py")
    print("   Features:")
    print("   - Clears failed status and retries automatically")
    print("   - Uses TURBO mode for fastest downloads")
    print("   - Creates backup before clearing failures")
    print("   - Skips already downloaded files")
    print()
    
    print("2. 🔧 DETAILED RETRY")
    print("   Command: python retry_failed_downloads.py")
    print("   Features:")
    print("   - Fresh authentication tokens")
    print("   - Detailed error analysis")
    print("   - Optimized retry logic")
    print("   - Progress tracking")
    print()
    
    print("3. 📊 PROGRESS MONITORING")
    print("   Command: python monitor_retry.py")
    print("   Features:")
    print("   - Real-time progress updates")
    print("   - Change tracking")
    print("   - Automatic file selection")
    print("   - Ctrl+C to stop")
    print()
    
    print("4. 🌐 WEB DASHBOARD")
    print("   URL: http://localhost:8051")
    print("   Features:")
    print("   - Visual progress tracking")
    print("   - File insights and analytics")
    print("   - Auto-refresh every 5 seconds")
    print("   - Comprehensive data analysis")

def show_common_failure_types():
    """Show common failure types and solutions."""
    print("\n❓ COMMON FAILURE TYPES & SOLUTIONS")
    print("=" * 50)
    
    print("1. 'Not found in downloaded files' (Most common)")
    print("   Cause: Network timeouts or connection issues")
    print("   Solution: Simple retry usually works")
    print()
    
    print("2. 'HTTPSConnectionPool' errors")
    print("   Cause: SharePoint server connectivity issues")
    print("   Solution: Wait a few minutes, then retry")
    print()
    
    print("3. '401 Client Error' (Authentication)")
    print("   Cause: Expired tokens or permission issues")
    print("   Solution: Use detailed retry for fresh authentication")
    print()
    
    print("4. '429 Rate Limiting'")
    print("   Cause: Too many requests too quickly")
    print("   Solution: Built-in rate limiting in TURBO mode")

def quick_retry():
    """Execute quick retry."""
    print("\n🚀 STARTING QUICK RETRY...")
    print("=" * 50)
    
    try:
        # Run simple retry
        result = subprocess.run([sys.executable, "simple_retry_failed.py"], 
                               input="1\n", text=True, capture_output=True)
        print("Retry process initiated...")
        print("Use 'python monitor_retry.py' to monitor progress")
        print("Or check dashboard at http://localhost:8051")
        
    except Exception as e:
        print(f"❌ Error starting retry: {e}")
        print("Try running: python simple_retry_failed.py")

def main():
    """Main function."""
    print("🔄 SHAREPOINT DOWNLOAD RETRY GUIDE")
    print("=" * 50)
    
    show_current_status()
    show_retry_options()
    show_common_failure_types()
    
    print("\n🎯 RECOMMENDED ACTIONS")
    print("=" * 50)
    print("1. Run: python simple_retry_failed.py (choose option 1)")
    print("2. Monitor: python monitor_retry.py") 
    print("3. Dashboard: http://localhost:8051")
    print("4. Wait for completion or check progress periodically")
    
    print("\n💡 TIPS")
    print("=" * 50)
    print("- TURBO mode is fastest and most reliable")
    print("- Monitor progress to see real-time updates")
    print("- Dashboard shows comprehensive analytics")
    print("- Backups are created automatically before retries")
    print("- Failed files are cleared and retried automatically")

if __name__ == "__main__":
    main()
