#!/usr/bin/env python3
"""
🔄 Simple Failed Downloads Retry Tool
====================================

A simple approach to retry failed downloads by just continuing
the main download script, which will automatically skip already
downloaded files and retry the remaining ones.

This approach is more reliable because it uses the original
file metadata and download logic.

Author: GitHub Copilot
Date: August 7, 2025
"""

import json
import os
import sys
import time
import logging
from pathlib import Path
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def analyze_failed_files(progress_file):
    """Analyze the current failed files in the progress file."""
    try:
        with open(progress_file, 'r', encoding='utf-8') as f:
            progress_data = json.load(f)
        
        failed_files = progress_data.get('results', {}).get('failed', [])
        successful_files = progress_data.get('results', {}).get('success', [])
        total_count = progress_data.get('total_count', 0)
        
        # Calculate actual total
        actual_total = len(successful_files) + len(failed_files)
        if total_count == 0 and actual_total > 0:
            total_count = actual_total
        
        logger.info(f"📊 Current Download Status:")
        logger.info(f"   Total files: {total_count:,}")
        logger.info(f"   Successfully downloaded: {len(successful_files):,}")
        logger.info(f"   Failed downloads: {len(failed_files):,}")
        if total_count > 0:
            logger.info(f"   Completion rate: {(len(successful_files)/total_count)*100:.1f}%")
        
        if not failed_files:
            logger.info("🎉 No failed files found! All downloads completed successfully.")
            return False
        
        # Analyze failure reasons
        error_types = {}
        for failed in failed_files:
            error = str(failed.get('error', 'Unknown error'))
            error_type = error.split(':')[0] if ':' in error else error
            error_types[error_type] = error_types.get(error_type, 0) + 1
        
        logger.info(f"🔍 Failure Analysis:")
        for error_type, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"   {error_type}: {count:,} files")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error analyzing progress file: {e}")
        return False

def clear_failed_files_status(progress_file):
    """Clear the failed status so main script can retry them."""
    try:
        # Load current progress
        with open(progress_file, 'r', encoding='utf-8') as f:
            progress_data = json.load(f)
        
        failed_files = progress_data.get('results', {}).get('failed', [])
        
        if not failed_files:
            logger.info("No failed files to retry.")
            return False
        
        # Create backup
        backup_path = progress_file.replace('.json', f'_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, indent=2)
        
        logger.info(f"📦 Created backup: {backup_path}")
        
        # Clear failed files - the main script will retry them
        progress_data['results']['failed'] = []
        progress_data['failed_count'] = 0
        progress_data['last_update'] = datetime.now().isoformat()
        progress_data['is_running'] = False
        
        # Add retry metadata
        if 'retry_history' not in progress_data:
            progress_data['retry_history'] = []
        
        progress_data['retry_history'].append({
            'timestamp': datetime.now().isoformat(),
            'action': 'cleared_failed_status',
            'files_cleared': len(failed_files),
            'reason': 'Prepare for retry with main script'
        })
        
        # Save updated progress
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, indent=2)
        
        logger.info(f"✅ Cleared {len(failed_files):,} failed file statuses")
        logger.info("💡 The main download script will now retry these files")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error clearing failed files: {e}")
        return False

def run_main_download_script(mode="turbo"):
    """Run the main download script to retry failed files."""
    try:
        import subprocess
        
        logger.info(f"🚀 Starting main download script in {mode} mode...")
        
        if mode == "turbo":
            cmd = ["python", "dll_pdf_fabric_turbo.py", "--turbo"]
        elif mode == "fast":
            cmd = ["python", "dll_pdf_fabric_turbo.py", "--fast"]
        else:
            cmd = ["python", "dll_pdf_fabric_turbo.py"]
        
        logger.info(f"📝 Command: {' '.join(cmd)}")
        logger.info("⏳ This will continue downloading where it left off...")
        
        # Run the command
        result = subprocess.run(cmd, capture_output=False, text=True)
        
        if result.returncode == 0:
            logger.info("✅ Download script completed successfully")
        else:
            logger.warning(f"⚠️ Download script exited with code {result.returncode}")
        
        return result.returncode == 0
        
    except Exception as e:
        logger.error(f"❌ Error running main download script: {e}")
        return False

def main():
    """Main retry function using the simple approach."""
    
    logger.info("🔄 Simple Failed Downloads Retry Tool")
    logger.info("=" * 50)
    
    # Configuration
    download_path = "C:/commercial_pdfs/downloaded_files"
    progress_file = f"{download_path}/download_progress_turbo.json"
    
    # Check if progress file exists
    if not os.path.exists(progress_file):
        logger.error(f"❌ Progress file not found: {progress_file}")
        logger.error("💡 Run the main download script first to create the progress file")
        return
    
    # Analyze current status
    logger.info("🔍 Analyzing current download status...")
    has_failed_files = analyze_failed_files(progress_file)
    
    if not has_failed_files:
        return
    
    # Ask user for retry approach
    print("\n🔄 Retry Options:")
    print("1. Clear failed status and run TURBO mode (recommended)")
    print("2. Clear failed status and run FAST mode")  
    print("3. Clear failed status and run NORMAL mode")
    print("4. Just clear failed status (manual retry)")
    print("5. Exit without changes")
    
    try:
        choice = input("\nSelect option (1-5): ").strip()
    except KeyboardInterrupt:
        logger.info("\\n❌ Operation cancelled by user")
        return
    
    if choice == "5":
        logger.info("👋 Exiting without changes")
        return
    
    # Clear failed files status
    logger.info("🧹 Clearing failed file statuses...")
    if not clear_failed_files_status(progress_file):
        logger.error("❌ Failed to clear failed files status")
        return
    
    if choice == "4":
        logger.info("✅ Failed files status cleared. You can now run the main script manually:")
        logger.info("💡 Command: python dll_pdf_fabric_turbo.py --turbo")
        return
    
    # Run main script automatically
    mode_map = {"1": "turbo", "2": "fast", "3": "normal"}
    mode = mode_map.get(choice, "turbo")
    
    logger.info(f"🚀 Running retry with {mode.upper()} mode...")
    
    if choice in ["1", "2", "3"]:
        success = run_main_download_script(mode)
        if success:
            logger.info("🎉 Retry completed!")
            logger.info("📊 Check the progress file for updated results")
        else:
            logger.warning("⚠️ Retry had some issues. Check the output above.")
    else:
        logger.warning("❓ Invalid choice. Please run the script again.")

if __name__ == "__main__":
    main()
