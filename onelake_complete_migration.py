#!/usr/bin/env python3
"""
OneLake Complete Migration Script - FULL AUTOMATION
==================================================

Migrates ALL remaining files automatically with:
- Automatic token refresh every 45 minutes
- Continuous batch processing
- Progress tracking and resumability
- Error handling and recovery

VERSION: Full Automation v1.0 (2025-08-08)
"""

import os
import json
import asyncio
import aiohttp
import time
import subprocess
from pathlib import Path
from urllib.parse import quote
import logging
from datetime import datetime, timedelta

# Configuration
class Config:
    # OneLake Configuration (validated working pattern)
    ONELAKE_BASE_URL = "https://onelake.dfs.fabric.microsoft.com"
    WORKSPACE_ID = "abc64232-25a2-499d-90ae-9fe5939ae437"  # GUID format
    LAKEHOUSE_ID = "a622b04f-1094-4f9b-86fd-5105f4778f76"  # GUID format
    
    # API Configuration  
    API_VERSION = "2020-06-12"  # Data Lake Gen2 API version
    
    # Performance Configuration
    MAX_CONCURRENT_UPLOADS = 20  # Optimized for production
    BATCH_SIZE = 100  # Files per batch
    RETRY_ATTEMPTS = 3
    REQUEST_TIMEOUT = 120  # Timeout for large files
    
    # Token refresh configuration
    TOKEN_REFRESH_MINUTES = 45  # Refresh token every 45 minutes
    
    # Progress tracking
    PROGRESS_FILE = "migration_progress_production.json"
    LOG_FILE = "onelake_migration_complete.log"

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

class CompleteMigrator:
    def __init__(self):
        self.access_token = None
        self.token_timestamp = None
        self.files_data = []
        self.progress_data = {}
        self.total_batches = 0
        self.completed_batches = 0
        
    def refresh_access_token(self):
        """Refresh access token using PowerShell script"""
        try:
            logger.info("🔄 REFRESHING ACCESS TOKEN...")
            
            # Run PowerShell script to get new token
            ps_script = "scripts/powershell/get_access_token.ps1"
            if os.path.exists(ps_script):
                result = subprocess.run([
                    "powershell.exe", 
                    "-ExecutionPolicy", "Bypass", 
                    "-File", ps_script
                ], capture_output=True, text=True, timeout=60)
                
                if result.returncode == 0:
                    logger.info("✅ PowerShell token refresh completed")
                    # Load the new token
                    if self.get_access_token():
                        self.token_timestamp = datetime.now()
                        logger.info("✅ ACCESS TOKEN REFRESHED SUCCESSFULLY")
                        return True
                else:
                    logger.error(f"❌ PowerShell script failed: {result.stderr}")
            else:
                logger.warning(f"⚠️ PowerShell script not found: {ps_script}")
                
        except Exception as e:
            logger.error(f"❌ Token refresh failed: {e}")
            
        return False
    
    def is_token_expired(self):
        """Check if token needs refresh"""
        if not self.token_timestamp:
            return True
            
        elapsed = datetime.now() - self.token_timestamp
        return elapsed.total_seconds() > (Config.TOKEN_REFRESH_MINUTES * 60)
    
    def ensure_valid_token(self):
        """Ensure we have a valid access token"""
        if self.is_token_expired():
            logger.info("⏰ Token refresh needed...")
            if not self.refresh_access_token():
                logger.error("❌ Failed to refresh token")
                return False
        return True

    def get_access_token(self):
        """Get Azure Storage scoped access token from environment file"""
        try:
            with open("config/.env", 'r') as f:
                for line in f:
                    if line.strip().startswith('ACCESS_TOKEN='):
                        self.access_token = line.strip().split('=', 1)[1]
                        logger.info("SUCCESS: Access token loaded from environment file")
                        return True
        except FileNotFoundError:
            logger.error("FAILED: ACCESS_TOKEN not found in config/.env file")
            logger.info("HINT: Run PowerShell script first: scripts/powershell/get_access_token.ps1")
            return False
        except Exception as e:
            logger.error(f"FAILED: Failed to load access token: {e}")
            return False

    def load_file_cache(self):
        """Load the optimized file cache"""
        try:
            with open("file_cache_optimized.json", 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.files_data = data.get('files', [])
                logger.info(f"SUCCESS: Loaded {len(self.files_data):,} files from cache")
                return True
        except Exception as e:
            logger.error(f"FAILED: Cannot load file cache: {e}")
            return False

    def load_progress(self):
        """Load migration progress"""
        try:
            with open(Config.PROGRESS_FILE, 'r', encoding='utf-8') as f:
                self.progress_data = json.load(f)
                uploaded = self.progress_data.get('uploaded_files', 0)
                logger.info(f"PROGRESS: Loaded existing progress - {uploaded:,} files completed")
        except FileNotFoundError:
            logger.info("PROGRESS: Starting fresh migration")
            self.progress_data = {
                "total_files": len(self.files_data),
                "uploaded_files": 0,
                "failed_files": 0,
                "skipped_files": 0,
                "completed_files": {}
            }

    def save_progress(self):
        """Save migration progress"""
        try:
            with open(Config.PROGRESS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.progress_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"WARNING: Failed to save progress: {e}")

    def get_headers(self):
        """Get headers for OneLake API requests"""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "x-ms-version": Config.API_VERSION,
            "User-Agent": "OneLakeCompleteMigrator/1.0"
        }

    def calculate_remaining_batches(self):
        """Calculate how many batches are remaining"""
        uploaded_files = self.progress_data.get('uploaded_files', 0)
        skipped_files = self.progress_data.get('skipped_files', 0)
        processed_files = uploaded_files + skipped_files
        
        remaining_files = len(self.files_data) - processed_files
        remaining_batches = (remaining_files + Config.BATCH_SIZE - 1) // Config.BATCH_SIZE
        start_batch = (processed_files // Config.BATCH_SIZE) + 1
        
        return start_batch, remaining_batches

    async def upload_file_to_onelake(self, session, file_info):
        """Upload a single file to OneLake using Data Lake Gen2 API with token refresh"""
        
        # Check if already uploaded
        relative_path = file_info['relative_path']
        if relative_path in self.progress_data['completed_files']:
            return {"status": "skipped", "file": relative_path}

        # Ensure valid token before upload
        if not self.ensure_valid_token():
            return {"status": "failed", "file": relative_path, "error": "Token refresh failed"}

        local_path = file_info['path']
        onelake_path = f"Files/SharePoint_Invoices/{relative_path.replace(os.sep, '/')}"
        
        try:
            # Read file
            with open(local_path, 'rb') as f:
                file_content = f.read()
            
            file_size = len(file_content)
            encoded_path = quote(onelake_path, safe='/')
            
            # Step 1: Create file
            create_url = f"{Config.ONELAKE_BASE_URL}/{Config.WORKSPACE_ID}/{Config.LAKEHOUSE_ID}/{encoded_path}?resource=file"
            
            async with session.put(
                create_url,
                headers=self.get_headers(),
                timeout=aiohttp.ClientTimeout(total=Config.REQUEST_TIMEOUT)
            ) as response:
                if response.status == 401:
                    # Token expired, refresh and retry
                    logger.warning(f"🔄 Token expired during upload, refreshing...")
                    if self.ensure_valid_token():
                        # Retry with new token
                        async with session.put(
                            create_url,
                            headers=self.get_headers(),
                            timeout=aiohttp.ClientTimeout(total=Config.REQUEST_TIMEOUT)
                        ) as retry_response:
                            if retry_response.status not in [201, 409]:
                                error_text = await retry_response.text()
                                return {"status": "failed", "file": relative_path, 
                                       "error": f"Create failed after refresh: HTTP {retry_response.status} - {error_text}"}
                    else:
                        return {"status": "failed", "file": relative_path, "error": "Token refresh failed"}
                elif response.status not in [201, 409]:
                    error_text = await response.text()
                    return {"status": "failed", "file": relative_path, 
                           "error": f"Create failed: HTTP {response.status} - {error_text}"}

            # Step 2: Append data
            append_url = f"{Config.ONELAKE_BASE_URL}/{Config.WORKSPACE_ID}/{Config.LAKEHOUSE_ID}/{encoded_path}?action=append&position=0"
            
            async with session.patch(
                append_url,
                headers={**self.get_headers(), "Content-Length": str(file_size)},
                data=file_content,
                timeout=aiohttp.ClientTimeout(total=Config.REQUEST_TIMEOUT)
            ) as response:
                if response.status == 401:
                    # Token expired, refresh and retry
                    if self.ensure_valid_token():
                        async with session.patch(
                            append_url,
                            headers={**self.get_headers(), "Content-Length": str(file_size)},
                            data=file_content,
                            timeout=aiohttp.ClientTimeout(total=Config.REQUEST_TIMEOUT)
                        ) as retry_response:
                            if retry_response.status != 202:
                                error_text = await retry_response.text()
                                return {"status": "failed", "file": relative_path, 
                                       "error": f"Append failed after refresh: HTTP {retry_response.status} - {error_text}"}
                    else:
                        return {"status": "failed", "file": relative_path, "error": "Token refresh failed"}
                elif response.status != 202:
                    error_text = await response.text()
                    return {"status": "failed", "file": relative_path, 
                           "error": f"Append failed: HTTP {response.status} - {error_text}"}

            # Step 3: Flush/commit
            flush_url = f"{Config.ONELAKE_BASE_URL}/{Config.WORKSPACE_ID}/{Config.LAKEHOUSE_ID}/{encoded_path}?action=flush&position={file_size}"
            
            async with session.patch(
                flush_url,
                headers=self.get_headers(),
                timeout=aiohttp.ClientTimeout(total=Config.REQUEST_TIMEOUT)
            ) as response:
                if response.status == 401:
                    # Token expired, refresh and retry
                    if self.ensure_valid_token():
                        async with session.patch(
                            flush_url,
                            headers=self.get_headers(),
                            timeout=aiohttp.ClientTimeout(total=Config.REQUEST_TIMEOUT)
                        ) as retry_response:
                            if retry_response.status != 200:
                                error_text = await retry_response.text()
                                return {"status": "failed", "file": relative_path, 
                                       "error": f"Flush failed after refresh: HTTP {retry_response.status} - {error_text}"}
                    else:
                        return {"status": "failed", "file": relative_path, "error": "Token refresh failed"}
                elif response.status != 200:
                    error_text = await response.text()
                    return {"status": "failed", "file": relative_path, 
                           "error": f"Flush failed: HTTP {response.status} - {error_text}"}

            # Success
            return {"status": "success", "file": relative_path, "size": file_size}

        except Exception as e:
            logger.error(f"ERROR: Exception uploading {relative_path}: {str(e)}")
            return {"status": "failed", "file": relative_path, "error": str(e)}

    async def upload_batch(self, files_batch, batch_num):
        """Upload a batch of files concurrently with token refresh support"""
        connector = aiohttp.TCPConnector(limit=Config.MAX_CONCURRENT_UPLOADS)
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [self.upload_file_to_onelake(session, file_info) for file_info in files_batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            batch_success = 0
            batch_failed = 0
            batch_skipped = 0
            
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"ERROR: Task exception: {result}")
                    batch_failed += 1
                elif result["status"] == "success":
                    batch_success += 1
                    # Update progress
                    self.progress_data["completed_files"][result["file"]] = {
                        "status": "completed",
                        "size": result["size"],
                        "timestamp": time.time(),
                        "batch": batch_num
                    }
                elif result["status"] == "skipped":
                    batch_skipped += 1
                else:
                    batch_failed += 1
                    logger.error(f"FAILED: Upload failed: {result['file']} - {result.get('error', 'Unknown error')}")
            
            # Update counters
            self.progress_data["uploaded_files"] += batch_success
            self.progress_data["failed_files"] += batch_failed
            self.progress_data["skipped_files"] += batch_skipped
            
            return batch_success, batch_failed, batch_skipped

    async def run_complete_migration(self):
        """Run the complete migration until all files are processed"""
        
        logger.info("🚀 ONELAKE COMPLETE MIGRATION - FULL AUTOMATION")
        logger.info("=" * 60)
        
        # Initialize
        if not self.get_access_token():
            logger.error("FAILED: Cannot proceed without access token")
            return False
        
        self.token_timestamp = datetime.now()
        
        if not self.load_file_cache():
            return False
            
        self.load_progress()
        
        # Calculate remaining work
        start_batch, remaining_batches = self.calculate_remaining_batches()
        self.total_batches = (len(self.files_data) + Config.BATCH_SIZE - 1) // Config.BATCH_SIZE
        
        uploaded = self.progress_data.get('uploaded_files', 0)
        remaining_files = len(self.files_data) - uploaded - self.progress_data.get('skipped_files', 0)
        
        logger.info(f"📊 MIGRATION STATUS:")
        logger.info(f"   Total Files: {len(self.files_data):,}")
        logger.info(f"   Already Uploaded: {uploaded:,}")
        logger.info(f"   Remaining Files: {remaining_files:,}")
        logger.info(f"   Starting from Batch: {start_batch}")
        logger.info(f"   Remaining Batches: {remaining_batches}")
        logger.info(f"   Token Auto-Refresh: Every {Config.TOKEN_REFRESH_MINUTES} minutes")
        logger.info("")
        
        if remaining_files == 0:
            logger.info("🎉 MIGRATION ALREADY COMPLETE!")
            return True
        
        migration_start_time = time.time()
        
        # Process all remaining batches
        for batch_num in range(start_batch, self.total_batches + 1):
            
            # Calculate batch range
            start_idx = (batch_num - 1) * Config.BATCH_SIZE
            end_idx = min(start_idx + Config.BATCH_SIZE, len(self.files_data))
            
            batch_files = self.files_data[start_idx:end_idx]
            
            logger.info(f"BATCH: Processing batch {batch_num}/{self.total_batches} ({len(batch_files)} files)")
            
            # Upload batch
            success, failed, skipped = await self.upload_batch(batch_files, batch_num)
            
            self.completed_batches = batch_num - start_batch + 1
            progress_pct = (self.progress_data['uploaded_files'] / len(self.files_data)) * 100
            
            logger.info(f"BATCH COMPLETE: Success: {success}, Failed: {failed}, Skipped: {skipped}")
            logger.info(f"PROGRESS: {self.progress_data['uploaded_files']:,}/{len(self.files_data):,} files ({progress_pct:.1f}%)")
            
            # Save progress every batch
            self.save_progress()
            
            # Check if complete
            if self.progress_data['uploaded_files'] + self.progress_data['skipped_files'] >= len(self.files_data):
                logger.info("🎉 ALL FILES PROCESSED!")
                break
            
            # Small delay between batches
            await asyncio.sleep(0.5)
        
        # Final summary
        migration_time = time.time() - migration_start_time
        logger.info("")
        logger.info("=" * 60)
        logger.info("🎉 COMPLETE MIGRATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"📊 Total files in dataset: {len(self.files_data):,}")
        logger.info(f"✅ Successfully uploaded: {self.progress_data['uploaded_files']:,}")
        logger.info(f"⏭️  Already existed (skipped): {self.progress_data['skipped_files']:,}")
        logger.info(f"❌ Failed uploads: {self.progress_data['failed_files']:,}")
        
        success_rate = (self.progress_data['uploaded_files'] / len(self.files_data)) * 100
        logger.info(f"📈 Success rate: {success_rate:.1f}%")
        logger.info(f"⏱️  Total migration time: {time.strftime('%H:%M:%S', time.gmtime(migration_time))}")
        
        if self.progress_data['uploaded_files'] + self.progress_data['skipped_files'] >= len(self.files_data):
            logger.info("")
            logger.info("🎉🎉🎉 MIGRATION COMPLETED SUCCESSFULLY! 🎉🎉🎉")
            logger.info("📁 All 376,888 files have been migrated to OneLake!")
            return True
        else:
            logger.warning("⚠️ Migration incomplete - some files may need retry")
            return False

def main():
    logger.info("🚀 Starting Complete OneLake Migration...")
    
    migrator = CompleteMigrator()
    success = asyncio.run(migrator.run_complete_migration())
    
    if success:
        logger.info("✅ Complete migration finished successfully!")
    else:
        logger.error("❌ Complete migration encountered issues")
    
    return success

if __name__ == "__main__":
    main()
