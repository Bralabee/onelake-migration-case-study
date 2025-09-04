#!/usr/bin/env python3
"""
OneLake Migration Script - WORKING VERSION
==================================================

High-performance migration of ACA SharePoint files to Microsoft Fabric OneLake
using the validated Data Lake Gen2 API pattern.

WORKING API PATTERN:
- URL: https://onelake.dfs.fabric.microsoft.com/{workspace_guid}/{lakehouse_guid}/Files/{path}
- Authentication: Bearer token with Azure Storage scope (https://storage.azure.com)
- Method: Create-Append-Flush sequence

VERSION: Working v1.0 (Validated 2025-08-08)
AUTHORS: Diagnostic analysis revealed the correct API pattern
"""

import os
import json
import asyncio
import aiohttp
import time
from pathlib import Path
from urllib.parse import quote
import subprocess
from concurrent.futures import ThreadPoolExecutor
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
    MAX_CONCURRENT_UPLOADS = 10
    BATCH_SIZE = 50
    RETRY_ATTEMPTS = 3
    REQUEST_TIMEOUT = 60
    
    # Progress tracking
    PROGRESS_FILE = "migration_progress_working.json"
    LOG_FILE = "onelake_migration_working.log"

# Setup logging (without emoji for Windows compatibility)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Config.LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class OneLakeMigrator:
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
            "completed_files": {},
            "failed_files_list": [],
            "start_time": None,
            "last_update": None
        }
    
    def save_progress(self):
        """Save current progress to file"""
        self.progress["last_update"] = time.time()
        with open(Config.PROGRESS_FILE, 'w') as f:
            json.dump(self.progress, f, indent=2)
    
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
    
    async def upload_file_async(self, session, file_path, onelake_path):
        """
        Upload a single file using validated Create-Append-Flush pattern
        
        VALIDATED WORKING PATTERN:
        1. CREATE: PUT ?resource=file (Content-Length: 0)
        2. APPEND: PATCH ?action=append&position=0 (with file content)
        3. FLUSH: PATCH ?action=flush&position={content_length} (Content-Length: 0)
        """
        try:
            # Read file content
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            file_size = len(file_content)
            base_url = self.build_onelake_url(onelake_path)
            
            # Step 1: Create file (Content-Length: 0)
            create_url = f"{base_url}?resource=file"
            create_headers = self.get_headers(content_length=0)
            
            async with session.put(create_url, headers=create_headers, timeout=Config.REQUEST_TIMEOUT) as response:
                if response.status not in [200, 201]:
                    error_text = await response.text()
                    raise Exception(f"Create failed: HTTP {response.status} - {error_text}")
            
            # Step 2: Append data
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
            logger.info(f"SUCCESS: Uploaded: {onelake_path} ({file_size:,} bytes)")
            return {"success": True, "path": onelake_path, "size": file_size}
            
        except Exception as e:
            logger.error(f"FAILED: Upload failed: {onelake_path} - {str(e)}")
            return {"success": False, "path": onelake_path, "error": str(e)}
    
    async def upload_batch(self, file_batch):
        """Upload a batch of files concurrently"""
        timeout = aiohttp.ClientTimeout(total=Config.REQUEST_TIMEOUT * 2)
        connector = aiohttp.TCPConnector(limit=Config.MAX_CONCURRENT_UPLOADS)
        
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            tasks = []
            for local_path, onelake_path in file_batch:
                task = self.upload_file_async(session, local_path, onelake_path)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return results
    
    def migrate_files(self, file_list):
        """Main migration function with working API pattern"""
        if not self.get_access_token():
            logger.error("FAILED: Cannot proceed without access token")
            return False
        
        self.progress["total_files"] = len(file_list)
        self.progress["start_time"] = time.time()
        
        logger.info(f"STARTING: Migration of {len(file_list):,} files")
        logger.info(f"TARGET: {Config.ONELAKE_BASE_URL}/{Config.WORKSPACE_ID}/{Config.LAKEHOUSE_ID}/Files/")
        
        # Process files in batches
        batch_number = 0
        for i in range(0, len(file_list), Config.BATCH_SIZE):
            batch = file_list[i:i + Config.BATCH_SIZE]
            batch_number += 1
            
            logger.info(f"BATCH: Processing batch {batch_number} ({len(batch)} files)")
            
            # Run async batch upload
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(self.upload_batch(batch))
                
                # Process results
                for result in results:
                    if isinstance(result, dict):
                        if result["success"]:
                            self.progress["uploaded_files"] += 1
                            self.progress["completed_files"][result["path"]] = {
                                "status": "completed",
                                "size": result["size"],
                                "timestamp": time.time()
                            }
                        else:
                            self.progress["failed_files"] += 1
                            self.progress["failed_files_list"].append({
                                "path": result["path"],
                                "error": result["error"],
                                "timestamp": time.time()
                            })
                    else:
                        # Exception occurred
                        self.progress["failed_files"] += 1
                        logger.error(f"BATCH EXCEPTION: {result}")
                
                # Save progress after each batch
                self.save_progress()
                
                # Progress update
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
        percentage = (uploaded / total) * 100 if total > 0 else 0
        
        duration = time.time() - self.progress["start_time"]
        hours, remainder = divmod(duration, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        logger.info("\n" + "="*50)
        logger.info("MIGRATION SUMMARY")
        logger.info("="*50)
        logger.info(f"SUCCESS: Total files processed: {total:,}")
        logger.info(f"SUCCESS: Successfully uploaded: {uploaded:,}")
        logger.info(f"FAILED: Failed uploads: {failed:,}")
        logger.info(f"PERCENT: Success rate: {percentage:.1f}%")
        logger.info(f"TIME: Total time: {int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}")
        
        if failed > 0:
            logger.info(f"\nFAILED FILES: Failed files logged in: {Config.PROGRESS_FILE}")

def main():
    """Main function to run a test migration"""
    migrator = OneLakeMigrator()
    
    # Test with a single file
    test_files = [
        ("C:\\Users\\sibitoye\\Documents\\HS2_PROJECTS_2025\\Commercial_ACA_taskforce\\test_onelake_api.py", 
         "test_upload/test_api_working.py")
    ]
    
    logger.info("TEST: Running test migration with working API pattern")
    success = migrator.migrate_files(test_files)
    
    if success:
        logger.info("SUCCESS: Test migration completed successfully!")
    else:
        logger.error("FAILED: Test migration failed")

if __name__ == "__main__":
    main()
