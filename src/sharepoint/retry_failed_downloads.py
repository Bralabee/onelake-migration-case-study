#!/usr/bin/env python3
"""
🔄 Failed Downloads Retry Tool
=============================

Retries all failed downloads from the progress file.
This script specifically targets files that failed during
the initial download process.

Features:
- Loads failed files from progress file
- Retries with fresh authentication tokens
- Uses optimized retry logic
- Updates progress file with new results

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

# Import the main download functions
from dll_pdf_fabric_turbo import (
    load_env_file, validate_parameters, get_graph_token,
    download_file_safely_turbo, create_optimized_session,
    get_fresh_download_url
)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_failed_files(progress_file):
    """Load failed files from the progress file."""
    try:
        with open(progress_file, 'r', encoding='utf-8') as f:
            progress_data = json.load(f)
        
        failed_files = progress_data.get('results', {}).get('failed', [])
        
        if not failed_files:
            logger.info("🎉 No failed files found in progress file!")
            return []
        
        logger.info(f"📋 Found {len(failed_files)} failed files to retry")
        return failed_files
        
    except Exception as e:
        logger.error(f"❌ Error loading progress file: {e}")
        return []

def convert_failed_to_file_info(failed_entry, cache_files):
    """Convert a failed entry back to file_info format needed for downloading."""
    file_path = failed_entry.get('file', '')
    
    # Find the original file info from cache
    for file_info in cache_files:
        if file_info.get('path') == file_path:
            return file_info
    
    # If not found in cache, create minimal file_info
    return {
        'path': file_path,
        'download_url': '',  # Will need to be regenerated
        'size': 0,
        'id': None
    }

def load_cache_files(cache_file):
    """Load the original file cache."""
    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        return cache_data.get('files', [])
    except Exception as e:
        logger.error(f"❌ Error loading cache file: {e}")
        return []

def regenerate_download_url(file_info, drive_id, headers, session):
    """Regenerate download URL for a file using Graph API."""
    if not file_info.get('id'):
        logger.warning(f"⚠️ No file ID for {file_info['path']}, cannot regenerate URL")
        return None
    
    try:
        url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{file_info['id']}"
        response = session.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        file_data = response.json()
        download_url = file_data.get("@microsoft.graph.downloadUrl")
        
        if download_url:
            logger.info(f"✅ Regenerated download URL for {file_info['path']}")
            return download_url
        else:
            logger.warning(f"⚠️ No download URL in response for {file_info['path']}")
            return None
            
    except Exception as e:
        logger.warning(f"⚠️ Failed to regenerate URL for {file_info['path']}: {e}")
        return None

def retry_failed_downloads(failed_files, cache_files, download_path, headers, drive_id, max_workers=10):
    """Retry downloading all failed files."""
    
    logger.info(f"🔄 Starting retry of {len(failed_files)} failed downloads")
    
    # Create session for URL regeneration
    session = create_optimized_session()
    
    # Convert failed entries to file_info and regenerate URLs
    retry_files = []
    for failed_entry in failed_files:
        file_info = convert_failed_to_file_info(failed_entry, cache_files)
        
        # Regenerate download URL if needed
        if not file_info.get('download_url') or '401' in str(failed_entry.get('error', '')):
            new_url = regenerate_download_url(file_info, drive_id, headers, session)
            if new_url:
                file_info['download_url'] = new_url
                retry_files.append(file_info)
            else:
                logger.warning(f"⚠️ Skipping {file_info['path']} - could not regenerate URL")
        else:
            retry_files.append(file_info)
    
    if not retry_files:
        logger.error("❌ No files available for retry")
        return [], []
    
    logger.info(f"🚀 Retrying {len(retry_files)} files with fresh URLs")
    
    # Retry downloads with higher retry count
    successful_retries = []
    still_failed = []
    
    for i, file_info in enumerate(retry_files, 1):
        logger.info(f"🔄 Retrying {i}/{len(retry_files)}: {file_info['path']}")
        
        # Use more aggressive retry settings for failed files
        result = download_file_safely_turbo(
            file_info, 
            download_path, 
            headers, 
            drive_id, 
            session, 
            max_retries=5  # More retries for failed files
        )
        
        if result['status'] == 'success':
            successful_retries.append(result)
            logger.info(f"✅ Retry successful: {file_info['path']}")
        else:
            still_failed.append(result)
            logger.warning(f"❌ Retry failed: {file_info['path']} - {result.get('error', 'Unknown error')}")
        
        # Brief pause between retries to avoid overwhelming the server
        if i % 10 == 0:
            time.sleep(1)
    
    return successful_retries, still_failed

def update_progress_file(progress_file, successful_retries, still_failed, original_failed_count):
    """Update the progress file with retry results."""
    try:
        # Load current progress
        with open(progress_file, 'r', encoding='utf-8') as f:
            progress_data = json.load(f)
        
        # Remove originally failed files that were retried
        current_failed = progress_data.get('results', {}).get('failed', [])
        retry_paths = {r['file'] for r in successful_retries + still_failed}
        
        # Keep only failed files that weren't retried
        updated_failed = [f for f in current_failed if f.get('file', '') not in retry_paths]
        
        # Add successful retries to success list
        current_success = progress_data.get('results', {}).get('success', [])
        current_success.extend(successful_retries)
        
        # Add still failed files back to failed list
        updated_failed.extend(still_failed)
        
        # Update progress data
        progress_data['results']['success'] = current_success
        progress_data['results']['failed'] = updated_failed
        progress_data['last_update'] = datetime.now().isoformat()
        progress_data['downloaded_count'] = len(current_success)
        progress_data['failed_count'] = len(updated_failed)
        
        # Add retry metadata
        if 'retry_history' not in progress_data:
            progress_data['retry_history'] = []
        
        progress_data['retry_history'].append({
            'timestamp': datetime.now().isoformat(),
            'attempted': original_failed_count,
            'successful': len(successful_retries),
            'still_failed': len(still_failed)
        })
        
        # Recalculate statistics
        total_files = progress_data.get('total_count', len(current_success) + len(updated_failed))
        progress_data['statistics'] = {
            'success_rate': round((len(current_success) / total_files) * 100, 2) if total_files > 0 else 0,
            'total_size': sum(f.get('size', 0) for f in current_success),
            'completion_percentage': round((len(current_success) / total_files) * 100, 2) if total_files > 0 else 0
        }
        
        # Save updated progress
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"💾 Progress file updated with retry results")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error updating progress file: {e}")
        return False

def main():
    """Main retry function."""
    
    logger.info("🔄 SharePoint Failed Downloads Retry Tool")
    logger.info("=" * 50)
    
    # Load environment
    load_env_file()
    
    # Configuration
    download_path = "C:/commercial_pdfs/downloaded_files"
    progress_file = f"{download_path}/download_progress_turbo.json"
    cache_file = f"{download_path}/file_list_cache.json"
    
    # Check if files exist
    if not os.path.exists(progress_file):
        logger.error(f"❌ Progress file not found: {progress_file}")
        return
    
    if not os.path.exists(cache_file):
        logger.error(f"❌ Cache file not found: {cache_file}")
        return
    
    # Load configuration
    params = {
        "tenant_id": os.environ.get("TENANT_ID", ""),
        "client_id": os.environ.get("CLIENT_ID", ""),
        "client_secret": os.environ.get("CLIENT_SECRET", ""),
        "sp_hostname": os.environ.get("SP_HOSTNAME", ""),
        "sp_site_path": os.environ.get("SP_SITE_PATH", ""),
        "sp_library_name": os.environ.get("SP_LIBRARY_NAME", "Documents"),
        "sp_start_folder": os.environ.get("SP_START_FOLDER", "/"),
    }
    
    # Validate parameters
    try:
        validate_parameters(params)
    except ValueError as e:
        logger.error(f"❌ Configuration error: {e}")
        return
    
    # Get authentication token
    try:
        token = get_graph_token(params["tenant_id"], params["client_id"], params["client_secret"])
        headers = {"Authorization": f"Bearer {token}"}
        logger.info("✅ Authentication successful")
    except Exception as e:
        logger.error(f"❌ Authentication failed: {e}")
        return
    
    # Load failed files
    failed_files = load_failed_files(progress_file)
    if not failed_files:
        return
    
    # Load cache for file info
    cache_files = load_cache_files(cache_file)
    if not cache_files:
        logger.error("❌ Could not load cache files")
        return
    
    # Get drive_id from cache
    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        drive_id = cache_data.get('drive_id')
        if not drive_id:
            logger.error("❌ Drive ID not found in cache")
            return
    except Exception as e:
        logger.error(f"❌ Error reading drive ID from cache: {e}")
        return
    
    # Retry failed downloads
    successful_retries, still_failed = retry_failed_downloads(
        failed_files, cache_files, download_path, headers, drive_id
    )
    
    # Update progress file
    if update_progress_file(progress_file, successful_retries, still_failed, len(failed_files)):
        logger.info("🎉 Retry operation completed!")
        logger.info(f"📊 Results:")
        logger.info(f"   • Successfully retried: {len(successful_retries)}")
        logger.info(f"   • Still failed: {len(still_failed)}")
        logger.info(f"   • Success rate: {(len(successful_retries)/len(failed_files)*100):.1f}%")
        
        if still_failed:
            logger.info(f"💡 You can run this script again to retry the remaining {len(still_failed)} failed files")
        else:
            logger.info("🎉 All failed files have been successfully downloaded!")
    else:
        logger.error("❌ Failed to update progress file")

if __name__ == "__main__":
    main()
