#!/usr/bin/env python3
"""
🔧 Progress File Recovery Tool
=============================

Rebuilds the download_progress_turbo.json file by scanning
actual downloaded files and comparing with the cache.

This is useful when the progress file gets corrupted but
the files have already been downloaded.

Author: GitHub Copilot
Date: August 7, 2025
"""

import json
import os
from pathlib import Path
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_cache_file(cache_path):
    """Load the file list cache."""
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        return cache_data.get('files', [])
    except Exception as e:
        logger.error(f"Error loading cache file: {e}")
        return []

def scan_downloaded_files(download_path):
    """Scan the download directory to see what files exist."""
    download_dir = Path(download_path)
    if not download_dir.exists():
        logger.error(f"Download directory does not exist: {download_path}")
        return set()
    
    downloaded_files = set()
    logger.info(f"🔍 Scanning downloaded files in: {download_path}")
    
    # Recursively find all files
    for file_path in download_dir.rglob("*"):
        if file_path.is_file() and not file_path.name.startswith('.'):
            # Get relative path from download directory
            relative_path = file_path.relative_to(download_dir)
            downloaded_files.add(str(relative_path).replace('\\', '/'))
    
    logger.info(f"✅ Found {len(downloaded_files)} downloaded files")
    return downloaded_files

def rebuild_progress_file(cache_files, downloaded_files, output_path):
    """Rebuild the progress file based on cache and downloaded files."""
    
    successful_downloads = []
    failed_downloads = []
    
    logger.info("🔧 Analyzing file status...")
    
    for file_info in cache_files:
        file_path = file_info.get('path', '')
        if file_path in downloaded_files:
            successful_downloads.append({
                "path": file_path,
                "size": file_info.get('size', 0),
                "timestamp": datetime.now().isoformat(),
                "status": "success"
            })
        else:
            failed_downloads.append({
                "path": file_path,
                "error": "Not found in downloaded files",
                "timestamp": datetime.now().isoformat(),
                "status": "pending"
            })
    
    # Create new progress structure
    progress_data = {
        "start_time": datetime.now().isoformat(),
        "last_update": datetime.now().isoformat(),
        "total_count": len(cache_files),
        "downloaded_count": len(successful_downloads),
        "failed_count": len(failed_downloads),
        "is_running": False,
        "last_processed_index": len(successful_downloads) - 1 if successful_downloads else 0,
        "results": {
            "success": successful_downloads,
            "failed": failed_downloads
        },
        "statistics": {
            "success_rate": round((len(successful_downloads) / len(cache_files)) * 100, 2) if cache_files else 0,
            "total_size": sum(f.get('size', 0) for f in successful_downloads),
            "completion_percentage": round((len(successful_downloads) / len(cache_files)) * 100, 2) if cache_files else 0
        },
        "metadata": {
            "rebuilt": True,
            "rebuild_time": datetime.now().isoformat(),
            "rebuild_reason": "Corrupted progress file recovery"
        }
    }
    
    # Save the rebuilt progress file
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Progress file rebuilt successfully: {output_path}")
        logger.info(f"📊 Summary:")
        logger.info(f"   Total files: {progress_data['total_count']:,}")
        logger.info(f"   Downloaded: {progress_data['downloaded_count']:,}")
        logger.info(f"   Remaining: {progress_data['failed_count']:,}")
        logger.info(f"   Completion: {progress_data['statistics']['completion_percentage']:.1f}%")
        
        return True
        
    except Exception as e:
        logger.error(f"Error saving progress file: {e}")
        return False

def main():
    """Main function to rebuild progress file."""
    
    # Paths
    download_path = "C:/commercial_pdfs/downloaded_files"
    cache_path = f"{download_path}/file_list_cache.json"
    progress_path = f"{download_path}/download_progress_turbo.json"
    backup_path = f"{download_path}/download_progress_turbo_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    logger.info("🔧 SharePoint Progress File Recovery Tool")
    logger.info("=" * 50)
    
    # Backup existing corrupted file
    if os.path.exists(progress_path):
        try:
            import shutil
            shutil.copy2(progress_path, backup_path)
            logger.info(f"📦 Backed up corrupted file to: {backup_path}")
        except Exception as e:
            logger.warning(f"Could not backup existing file: {e}")
    
    # Load cache file
    logger.info("📚 Loading file list cache...")
    cache_files = load_cache_file(cache_path)
    
    if not cache_files:
        logger.error("❌ Could not load cache file. Make sure file_list_cache.json exists.")
        return
    
    logger.info(f"✅ Loaded {len(cache_files):,} files from cache")
    
    # Scan downloaded files
    downloaded_files = scan_downloaded_files(download_path)
    
    if not downloaded_files:
        logger.error("❌ No downloaded files found. Check the download path.")
        return
    
    # Rebuild progress file
    logger.info("🔧 Rebuilding progress file...")
    success = rebuild_progress_file(cache_files, downloaded_files, progress_path)
    
    if success:
        logger.info("🎉 Progress file successfully rebuilt!")
        logger.info("💡 You can now run the turbo script normally")
        logger.info("🚀 Command: python dll_pdf_fabric_turbo.py")
    else:
        logger.error("❌ Failed to rebuild progress file")

if __name__ == "__main__":
    main()
