#!/usr/bin/env python3
"""
OneLake Migration Script - PRODUCTION VERSION
==================================================

Full migration of ACA SharePoint files to Microsoft Fabric OneLake
using the validated working API pattern.

VERSION: Production v1.0 (Validated 2025-08-08)
"""

import os
import json
import asyncio
import aiohttp
import time
from pathlib import Path
from urllib.parse import quote
import logging

# Configuration
class Config:
    # OneLake Configuration (validated working pattern)
    ONELAKE_BASE_URL = "https://onelake.dfs.fabric.microsoft.com"
    WORKSPACE_ID = "abc64232-25a2-499d-90ae-9fe5939ae437"  # GUID format
    LAKEHOUSE_ID = "a622b04f-1094-4f9b-86fd-5105f4778f76"  # GUID format
    
    # API Configuration  
    API_VERSION = "2020-06-12"  # Data Lake Gen2 API version
    
    # Performance Configuration
    MAX_CONCURRENT_UPLOADS = 20  # Increased for production
    BATCH_SIZE = 100  # Larger batches for production
    RETRY_ATTEMPTS = 3
    REQUEST_TIMEOUT = 120  # Increased timeout for larger files
    
    # Progress tracking
    PROGRESS_FILE = "migration_progress_production.json"
    LOG_FILE = "onelake_migration_production.log"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Config.LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class OneLakeProductionMigrator:
    def __init__(self):
        self.access_token = None
        self.progress = self.load_progress()
        self.session = None
        
    def get_access_token(self):
        """Get Azure Storage scoped access token from environment file"""
        try:
            # Load from environment file
            env_file = "config/.env"
            if os.path.exists(env_file):
                with open(env_file, 'r') as f:
                    for line in f:
                        if line.strip().startswith('ACCESS_TOKEN='):
                            self.access_token = line.strip().split('=', 1)[1]
                            logger.info("SUCCESS: Access token loaded from environment file")
                            return True
            
            logger.error("FAILED: ACCESS_TOKEN not found in config/.env file")
            logger.info("HINT: Run PowerShell script first: scripts/powershell/get_access_token.ps1")
            return False
            
        except Exception as e:
            logger.error(f"FAILED: Failed to load access token: {e}")
            return False
    
    def load_progress(self):
        """Load existing progress or create new progress structure"""
        if os.path.exists(Config.PROGRESS_FILE):
            with open(Config.PROGRESS_FILE, 'r') as f:
                return json.load(f)
        return {
            "total_files": 0,
            "uploaded_files": 0,
            "failed_files": 0,
            "skipped_files": 0,
            "completed_files": {},
            "failed_files_list": [],
            "start_time": None,
            "last_update": None,
            "current_batch": 0
        }
    
    def save_progress(self):
        """Save current progress to file"""
        self.progress["last_update"] = time.time()
        with open(Config.PROGRESS_FILE, 'w') as f:
            json.dump(self.progress, f, indent=2)
    
    def load_file_cache(self):
        """Load files from the optimized cache"""
        try:
            with open('file_cache_optimized.json', 'r') as f:
                cache_data = json.load(f)
            
            if 'files' in cache_data:
                files = cache_data['files']
                logger.info(f"Loaded {len(files):,} files from cache (timestamp: {cache_data.get('timestamp', 'Unknown')})")
                return files
            else:
                logger.error("No 'files' key found in cache")
                return []
                
        except Exception as e:
            logger.error(f"Failed to load file cache: {e}")
            return []
    
    def build_onelake_url(self, relative_path):
        """Build OneLake URL using validated working pattern"""
        # Clean and encode the path
        clean_path = relative_path.replace('\\', '/').strip('/')
        encoded_path = quote(clean_path, safe='/')
        
        # Use GUID format (no .Lakehouse suffix needed)
        url = f"{Config.ONELAKE_BASE_URL}/{Config.WORKSPACE_ID}/{Config.LAKEHOUSE_ID}/Files/{encoded_path}"
        return url
    
    def get_headers(self, content_length=None):
        """Get headers for OneLake API requests"""
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "x-ms-version": Config.API_VERSION,
            "x-ms-client-request-id": f"migration-{int(time.time())}",
            "x-ms-date": time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
        }
        
        if content_length is not None:
            headers["Content-Length"] = str(content_length)
            headers["Content-Type"] = "application/octet-stream"
            
        return headers
    
    async def upload_file_async(self, session, file_info):
        """
        Upload a single file using validated Create-Append-Flush pattern
        """
        local_path = file_info.get('path')
        relative_path = file_info.get('relative_path')
        expected_size = file_info.get('size_bytes', 0)
        
        if not local_path or not relative_path:
            return {"success": False, "path": relative_path, "error": "Missing path information"}
        
        # Check if file already uploaded
        if relative_path in self.progress["completed_files"]:
            return {"success": True, "path": relative_path, "size": expected_size, "skipped": True}
        
        try:
            # Check if file exists
            if not os.path.exists(local_path):
                return {"success": False, "path": relative_path, "error": f"Local file not found: {local_path}"}
            
            # Read file content
            with open(local_path, 'rb') as f:
                file_content = f.read()
            
            file_size = len(file_content)
            base_url = self.build_onelake_url(relative_path)
            
            # Step 1: Create file (Content-Length: 0)
            create_url = f"{base_url}?resource=file"
            create_headers = self.get_headers(content_length=0)
            
            async with session.put(create_url, headers=create_headers, timeout=Config.REQUEST_TIMEOUT) as response:
                if response.status not in [200, 201]:
                    error_text = await response.text()
                    raise Exception(f"Create failed: HTTP {response.status} - {error_text}")
            
            # Step 2: Append data (if file has content)
            if file_size > 0:
                append_url = f"{base_url}?action=append&position=0"
                append_headers = self.get_headers(content_length=file_size)
                
                async with session.patch(append_url, data=file_content, headers=append_headers, timeout=Config.REQUEST_TIMEOUT) as response:
                    if response.status not in [200, 202]:
                        error_text = await response.text()
                        raise Exception(f"Append failed: HTTP {response.status} - {error_text}")
                
                # Step 3: Flush
                flush_url = f"{base_url}?action=flush&position={file_size}"
                flush_headers = self.get_headers(content_length=0)
                
                async with session.patch(flush_url, headers=flush_headers, timeout=Config.REQUEST_TIMEOUT) as response:
                    if response.status not in [200, 201]:
                        error_text = await response.text()
                        raise Exception(f"Flush failed: HTTP {response.status} - {error_text}")
            
            # Success
            logger.info(f"SUCCESS: Uploaded {relative_path} ({file_size:,} bytes)")
            return {"success": True, "path": relative_path, "size": file_size}
            
        except Exception as e:
            logger.error(f"FAILED: Upload failed: {relative_path} - {str(e)}")
            return {"success": False, "path": relative_path, "error": str(e)}
    
    async def upload_batch(self, file_batch):
        """Upload a batch of files concurrently"""
        timeout = aiohttp.ClientTimeout(total=Config.REQUEST_TIMEOUT * 2)
        connector = aiohttp.TCPConnector(limit=Config.MAX_CONCURRENT_UPLOADS)
        
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            tasks = []
            for file_info in file_batch:
                task = self.upload_file_async(session, file_info)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return results
    
    def migrate_files(self, start_batch=0, max_batches=None):
        """Main migration function with working API pattern"""
        if not self.get_access_token():
            logger.error("FAILED: Cannot proceed without access token")
            return False
        
        # Load file cache
        files = self.load_file_cache()
        if not files:
            logger.error("FAILED: No files to migrate")
            return False
        
        logger.info(f"STARTING: Production migration")
        logger.info(f"Total files in cache: {len(files):,}")
        logger.info(f"Starting from batch: {start_batch}")
        logger.info(f"Max batches: {max_batches if max_batches else 'All'}")
        logger.info(f"Target: {Config.ONELAKE_BASE_URL}/{Config.WORKSPACE_ID}/{Config.LAKEHOUSE_ID}/Files/")
        
        self.progress["total_files"] = len(files)
        self.progress["start_time"] = time.time()
        
        # Calculate batch range
        total_batches = (len(files) + Config.BATCH_SIZE - 1) // Config.BATCH_SIZE
        end_batch = min(total_batches, start_batch + max_batches) if max_batches else total_batches
        
        logger.info(f"Processing batches {start_batch + 1} to {end_batch} of {total_batches}")
        
        # Process files in batches
        for batch_num in range(start_batch, end_batch):
            start_idx = batch_num * Config.BATCH_SIZE
            end_idx = min(start_idx + Config.BATCH_SIZE, len(files))
            batch = files[start_idx:end_idx]
            
            self.progress["current_batch"] = batch_num + 1
            
            logger.info(f"BATCH: Processing batch {batch_num + 1}/{total_batches} ({len(batch)} files)")
            
            # Run async batch upload
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(self.upload_batch(batch))
                
                # Process results
                batch_success = 0
                batch_failed = 0
                batch_skipped = 0
                
                for result in results:
                    if isinstance(result, dict):
                        if result["success"]:
                            if result.get("skipped", False):
                                batch_skipped += 1
                                self.progress["skipped_files"] += 1
                            else:
                                batch_success += 1
                                self.progress["uploaded_files"] += 1
                                self.progress["completed_files"][result["path"]] = {
                                    "status": "completed",
                                    "size": result["size"],
                                    "timestamp": time.time(),
                                    "batch": batch_num + 1
                                }
                        else:
                            batch_failed += 1
                            self.progress["failed_files"] += 1
                            self.progress["failed_files_list"].append({
                                "path": result["path"],
                                "error": result["error"],
                                "timestamp": time.time(),
                                "batch": batch_num + 1
                            })
                    else:
                        # Exception occurred
                        batch_failed += 1
                        self.progress["failed_files"] += 1
                        logger.error(f"BATCH EXCEPTION: {result}")
                
                # Save progress after each batch
                self.save_progress()
                
                # Batch summary
                logger.info(f"BATCH COMPLETE: Success: {batch_success}, Failed: {batch_failed}, Skipped: {batch_skipped}")
                
                # Overall progress update
                completed = self.progress["uploaded_files"]
                total = self.progress["total_files"]
                percentage = (completed / total) * 100 if total > 0 else 0
                
                logger.info(f"PROGRESS: {completed:,}/{total:,} files ({percentage:.1f}%)")
                
            finally:
                loop.close()
        
        # Final summary
        self.print_summary()
        return True
    
    def print_summary(self):
        """Print migration summary"""
        total = self.progress["total_files"]
        uploaded = self.progress["uploaded_files"]
        failed = self.progress["failed_files"]
        skipped = self.progress["skipped_files"]
        percentage = (uploaded / total) * 100 if total > 0 else 0
        
        duration = time.time() - self.progress["start_time"]
        hours, remainder = divmod(duration, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        logger.info("\n" + "="*60)
        logger.info("PRODUCTION MIGRATION SUMMARY")
        logger.info("="*60)
        logger.info(f"SUCCESS: Total files processed: {total:,}")
        logger.info(f"SUCCESS: Successfully uploaded: {uploaded:,}")
        logger.info(f"SKIPPED: Already uploaded: {skipped:,}")
        logger.info(f"FAILED: Failed uploads: {failed:,}")
        logger.info(f"PERCENT: Success rate: {percentage:.1f}%")
        logger.info(f"TIME: Total time: {int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}")
        
        if failed > 0:
            logger.info(f"\nFAILED FILES: Check details in: {Config.PROGRESS_FILE}")

def main():
    """Main function to run production migration"""
    import argparse
    
    parser = argparse.ArgumentParser(description='OneLake Production Migration')
    parser.add_argument('--start-batch', type=int, default=0, help='Starting batch number (0-based)')
    parser.add_argument('--max-batches', type=int, help='Maximum number of batches to process')
    parser.add_argument('--test-run', action='store_true', help='Run with first 5 batches only')
    
    args = parser.parse_args()
    
    migrator = OneLakeProductionMigrator()
    
    if args.test_run:
        logger.info("TEST RUN: Processing first 5 batches only")
        success = migrator.migrate_files(start_batch=0, max_batches=5)
    else:
        success = migrator.migrate_files(start_batch=args.start_batch, max_batches=args.max_batches)
    
    if success:
        logger.info("MIGRATION COMPLETED SUCCESSFULLY!")
    else:
        logger.error("MIGRATION FAILED")

if __name__ == "__main__":
    main()
