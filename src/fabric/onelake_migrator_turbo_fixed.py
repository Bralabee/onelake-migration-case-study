#!/usr/bin/env python3
"""
🚀 FIXED Optimized Microsoft Fabric OneLake Migration Tool
========================================================

Fixed version of the high-performance migration tool.
Fixes progress tracking and stats initialization bugs.

Author: GitHub Copilot  
Date: August 8, 2025
"""

import os
import json
import asyncio
import aiohttp
import aiofiles
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from datetime import datetime
from pathlib import Path
import logging
import pandas as pd
from typing import Dict, List, Any, Optional
import mimetypes
import hashlib
import time
from dotenv import load_dotenv
import multiprocessing as mp
from functools import partial
import requests
from threading import Lock

# Setup logging first
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
# Check multiple possible locations for .env file
env_paths = [
    ".env",  # Current directory
    "config/.env",  # Config directory (after reorganization)
    "../../config/.env",  # From src/fabric/ to config/
    "../config/.env"  # Alternative path
]

for env_path in env_paths:
    if os.path.exists(env_path):
        load_dotenv(env_path)
        logger.info(f"📄 Loaded environment from: {env_path}")
        break
else:
    load_dotenv()  # Fallback to default behavior
    logger.warning("⚠️  Using default .env loading - may not find config files")

class OptimizedOneLakeMigrator:
    """High-performance OneLake migrator optimized for large file volumes."""
    
    def __init__(self, source_path: str, config: Dict[str, str]):
        """Initialize optimized migrator."""
        self.source_path = Path(source_path)
        self.config = config
        
        # OneLake configuration
        self.workspace_id = config.get("fabric_workspace_id")
        self.lakehouse_id = config.get("fabric_lakehouse_id") 
        self.tenant_id = config.get("tenant_id")
        self.client_id = config.get("client_id")
        self.client_secret = config.get("client_secret")
        
        # Support for pre-configured access token (from config/.env)
        self.access_token = config.get("fabric_access_token")
        
        # Migration settings
        self.onelake_base_path = config.get("onelake_base_path", "/Files/SharePoint_Invoices")
        self.delta_table_name = config.get("delta_table_name", "sharepoint_invoices")
        
        # Performance settings
        self.max_workers = min(25, mp.cpu_count() * 4)  # Limit concurrent uploads
        self.chunk_size = 1000  # Process files in chunks
        self.batch_size = 50   # Upload batch size
        
        # Progress tracking
        self.migration_log = Path("migration_progress_optimized.json")
        self.file_cache = Path("file_cache_optimized.json")
        
        # Thread safety
        self.progress_lock = Lock()
        
    def get_fabric_token(self) -> str:
        """Get access token for Microsoft Fabric and OneLake."""
        # Check if we have a pre-configured access token
        if hasattr(self, 'access_token') and self.access_token:
            return self.access_token
            
        # Otherwise get token via OAuth
        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        token_data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://storage.azure.com/.default"  # Updated scope for OneLake Data Lake API
        }
        
        response = requests.post(token_url, data=token_data)
        response.raise_for_status()
        return response.json()["access_token"]
    
    def scan_files_optimized(self) -> List[Dict]:
        """Optimized file scanning using multiple processes."""
        logger.info("🔍 Scanning files with optimized parallel processing...")
        
        # Check cache first
        if self.file_cache.exists():
            try:
                with open(self.file_cache, 'r') as f:
                    cached_data = json.load(f)
                    cache_time = datetime.fromisoformat(cached_data['timestamp'])
                    if (datetime.now() - cache_time).total_seconds() < 3600:  # 1 hour cache
                        logger.info(f"✅ Using cached file list: {len(cached_data['files']):,} files")
                        return cached_data['files']
            except:
                pass
        
        # Use os.walk for faster directory traversal
        files = []
        start_time = time.time()
        
        for root, dirs, filenames in os.walk(self.source_path):
            root_path = Path(root)
            for filename in filenames:
                file_path = root_path / filename
                try:
                    stat = file_path.stat()
                    relative_path = file_path.relative_to(self.source_path)
                    
                    files.append({
                        "path": str(file_path),
                        "relative_path": str(relative_path),
                        "size_bytes": stat.st_size,
                        "modified_time": stat.st_mtime
                    })
                except:
                    continue
        
        scan_time = time.time() - start_time
        logger.info(f"✅ Scanned {len(files):,} files in {scan_time:.1f}s ({len(files)/scan_time:.0f} files/sec)")
        
        # Cache results
        cache_data = {
            "timestamp": datetime.now().isoformat(),
            "files": files
        }
        with open(self.file_cache, 'w') as f:
            json.dump(cache_data, f)
        
        return files
    
    async def upload_file_async(self, session: aiohttp.ClientSession, file_info: Dict, token: str) -> Dict:
        """Async file upload to OneLake."""
        source_path = file_info["path"]
        relative_path = file_info["relative_path"]
        onelake_path = f"{self.onelake_base_path}/{relative_path}"
        
        # FIXED: Use OneLake Data Lake API endpoint instead of Fabric API
        # This matches the path format used for directory creation
        upload_url = f"https://onelake.dfs.fabric.microsoft.com/{self.workspace_id}/{self.lakehouse_id}.Lakehouse{onelake_path}"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/octet-stream"
        }
        
        try:
            async with aiofiles.open(source_path, 'rb') as f:
                file_data = await f.read()
            
            # Azure Data Lake Gen2 API pattern for OneLake
            # Step 1: Create the file
            async with session.put(upload_url, headers=headers) as create_response:
                if create_response.status not in [200, 201]:
                    return {"success": False, "file": relative_path, "error": f"Create failed: HTTP {create_response.status}"}
            
            # Step 2: Append data
            append_url = f"{upload_url}?action=append&position=0"
            async with session.patch(append_url, headers=headers, data=file_data) as append_response:
                if append_response.status not in [200, 202]:
                    return {"success": False, "file": relative_path, "error": f"Append failed: HTTP {append_response.status}"}
            
            # Step 3: Flush to finalize
            flush_url = f"{upload_url}?action=flush&position={len(file_data)}"
            async with session.patch(flush_url, headers=headers) as flush_response:
                if flush_response.status in [200, 201]:
                    return {"success": True, "file": relative_path, "size": len(file_data)}
                else:
                    return {"success": False, "file": relative_path, "error": f"Flush failed: HTTP {flush_response.status}"}
                    
        except Exception as e:
            return {"success": False, "file": relative_path, "error": str(e)}
    
    async def migrate_batch_async(self, file_batch: List[Dict], token: str) -> List[Dict]:
        """Migrate a batch of files asynchronously."""
        connector = aiohttp.TCPConnector(limit=50, limit_per_host=25)
        timeout = aiohttp.ClientTimeout(total=300)  # 5 minute timeout
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            tasks = [self.upload_file_async(session, file_info, token) for file_info in file_batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle exceptions
            processed_results = []
            for result in results:
                if isinstance(result, Exception):
                    processed_results.append({"success": False, "error": str(result)})
                else:
                    processed_results.append(result)
            
            return processed_results
    
    def migrate_files_optimized(self, resume: bool = True) -> Dict[str, Any]:
        """Optimized migration with parallel uploads."""
        logger.info("🚀 Starting optimized OneLake migration...")
        
        # Load progress
        progress = self.load_progress() if resume else self.init_progress()
        
        # Scan files
        files = self.scan_files_optimized()
        
        # Filter out already processed files
        processed_files = set(progress.get("completed_files", []))
        remaining_files = [f for f in files if f["relative_path"] not in processed_files]
        
        logger.info(f"📊 Migration status: {len(processed_files):,} completed, {len(remaining_files):,} remaining")
        
        if not remaining_files:
            logger.info("✅ All files already migrated!")
            return progress.get("stats", {})
        
        # Create batches for parallel processing
        batches = [remaining_files[i:i + self.batch_size] for i in range(0, len(remaining_files), self.batch_size)]
        
        # Get authentication token
        token = self.get_fabric_token()
        token_refresh_time = time.time()
        
        # Initialize migration stats properly
        migration_stats = progress.get("stats", {})
        if not migration_stats:
            migration_stats = {
                "start_time": datetime.now().isoformat(),
                "total_files": len(files),
                "processed_files": len(processed_files),
                "successful_uploads": len(processed_files),
                "failed_uploads": 0,
                "batches_completed": 0,
                "avg_upload_speed": 0
            }
        
        logger.info(f"📦 Processing {len(batches)} batches with {self.batch_size} files each")
        
        # Process batches
        for batch_idx, batch in enumerate(batches):
            batch_start_time = time.time()
            
            # Refresh token every 30 minutes
            if time.time() - token_refresh_time > 1800:
                token = self.get_fabric_token()
                token_refresh_time = time.time()
            
            logger.info(f"📦 Processing batch {batch_idx + 1}/{len(batches)} ({len(batch)} files)")
            
            # Run async batch upload
            try:
                results = asyncio.run(self.migrate_batch_async(batch, token))
                
                # Process results
                batch_success = 0
                batch_failed = 0
                
                for result in results:
                    if result.get("success", False):
                        batch_success += 1
                        with self.progress_lock:
                            progress["completed_files"].append(result["file"])
                    else:
                        batch_failed += 1
                        with self.progress_lock:
                            progress["failed_files"].append({
                                "file": result.get("file", "unknown"),
                                "error": result.get("error", "unknown error"),
                                "timestamp": datetime.now().isoformat()
                            })
                
                # Update stats
                migration_stats["processed_files"] += len(batch)
                migration_stats["successful_uploads"] += batch_success
                migration_stats["failed_uploads"] += batch_failed
                migration_stats["batches_completed"] += 1
                
                # Calculate speed
                batch_time = time.time() - batch_start_time
                batch_speed = len(batch) / batch_time if batch_time > 0 else 0
                migration_stats["avg_upload_speed"] = (
                    migration_stats["avg_upload_speed"] * batch_idx + batch_speed
                ) / (batch_idx + 1)
                
                # Progress update
                pct = (migration_stats["processed_files"] / migration_stats["total_files"]) * 100
                logger.info(f"📊 Progress: {pct:.1f}% | Speed: {batch_speed:.1f} files/sec | Success: {batch_success}/{len(batch)}")
                
                # Save progress every 10 batches
                if batch_idx % 10 == 0:
                    progress["stats"] = migration_stats
                    self.save_progress(progress)
                
            except Exception as e:
                logger.error(f"❌ Batch {batch_idx + 1} failed: {e}")
                continue
        
        # Final stats
        migration_stats["end_time"] = datetime.now().isoformat()
        progress["stats"] = migration_stats
        self.save_progress(progress)
        
        logger.info("✅ Optimized migration completed!")
        logger.info(f"📊 Results: {migration_stats['successful_uploads']:,}/{migration_stats['total_files']:,} files migrated")
        logger.info(f"⚡ Average speed: {migration_stats['avg_upload_speed']:.1f} files/sec")
        
        return migration_stats
    
    def init_progress(self) -> Dict:
        """Initialize progress tracking."""
        return {
            "completed_files": [],
            "failed_files": [],
            "stats": {}
        }
    
    def load_progress(self) -> Dict:
        """Load migration progress."""
        if self.migration_log.exists():
            try:
                with open(self.migration_log, 'r') as f:
                    return json.load(f)
            except:
                pass
        return self.init_progress()
    
    def save_progress(self, progress: Dict):
        """Save migration progress."""
        with open(self.migration_log, 'w') as f:
            json.dump(progress, f, indent=2)

def load_fabric_config() -> Dict[str, str]:
    """Load Microsoft Fabric configuration."""
    config = {
        "tenant_id": os.environ.get("TENANT_ID", ""),
        "client_id": os.environ.get("CLIENT_ID", ""),
        "client_secret": os.environ.get("CLIENT_SECRET", ""),
        "fabric_workspace_id": os.environ.get("FABRIC_WORKSPACE_ID", ""),
        "fabric_lakehouse_id": os.environ.get("FABRIC_LAKEHOUSE_ID", ""),
        "fabric_access_token": os.environ.get("FABRIC_ACCESS_TOKEN", ""),  # Added support for pre-configured token
        "onelake_base_path": os.environ.get("ONELAKE_BASE_PATH", "/Files/SharePoint_Invoices"),
        "delta_table_name": os.environ.get("DELTA_TABLE_NAME", "sharepoint_invoices")
    }
    return config

def main():
    """Main function for optimized migration."""
    import argparse
    
    parser = argparse.ArgumentParser(description="FIXED Optimized Microsoft Fabric OneLake Migration Tool")
    parser.add_argument("--source", default="C:/commercial_pdfs/downloaded_files",
                       help="Source directory with downloaded files")
    parser.add_argument("--resume", action="store_true", default=True,
                       help="Resume previous migration")
    parser.add_argument("--workers", type=int, default=25,
                       help="Number of parallel workers")
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_fabric_config()
    
    # Validate configuration
    required_fields = ["tenant_id", "client_id", "client_secret", "fabric_workspace_id", "fabric_lakehouse_id"]
    missing = [field for field in required_fields if not config.get(field)]
    
    if missing:
        logger.error(f"❌ Missing configuration: {missing}")
        logger.error("💡 Make sure your .env file contains all required Fabric settings")
        return
    
    # Create optimized migrator
    migrator = OptimizedOneLakeMigrator(args.source, config)
    migrator.max_workers = args.workers
    
    # Start migration
    logger.info(f"🚀 Starting FIXED optimized migration with {args.workers} workers")
    results = migrator.migrate_files_optimized(args.resume)
    
    print("\n✅ FIXED OPTIMIZED MIGRATION COMPLETE")
    print("=" * 50)
    print(f"📊 Files Processed: {results.get('processed_files', 0):,}")
    print(f"✅ Successful: {results.get('successful_uploads', 0):,}")
    print(f"❌ Failed: {results.get('failed_uploads', 0):,}")
    print(f"⚡ Average Speed: {results.get('avg_upload_speed', 0):.1f} files/sec")

if __name__ == "__main__":
    main()
