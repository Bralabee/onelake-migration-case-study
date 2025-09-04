import os
import requests
from datetime import datetime
import time
import logging
from pathlib import Path
import json
import sys
import concurrent.futures
import threading
from queue import Queue
try:
    import requests.adapters
    from urllib3.util.retry import Retry
except ImportError:
    # Fallback for older requests versions
    try:
        from requests.packages.urllib3.util.retry import Retry
        import requests.adapters
    except ImportError:
        Retry = None
        requests.adapters = None

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ✅ Environment File Support
def load_env_file(env_file=".env"):
    """Load environment variables from .env file if it exists."""
    # Check multiple possible locations for .env file
    possible_paths = [
        env_file,  # Current directory
        f"config/{env_file}",  # Config directory (after reorganization)
        f"../../config/{env_file}",  # From src/sharepoint/ to config/
        f"../config/{env_file}"  # Alternative path
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            logger.info(f"📄 Loading environment from: {path}")
            with open(path, 'r') as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        os.environ[key] = value.strip('"\'')
            return
    
    logger.warning(f"⚠️  No .env file found in any of these locations: {possible_paths}")

# Load .env file if it exists
load_env_file()

# ✅ Configuration Parameters
default_params = {
    "tenant_id": os.environ.get("TENANT_ID", ""),
    "client_id": os.environ.get("CLIENT_ID", ""),
    "client_secret": os.environ.get("CLIENT_SECRET", ""),
    "sp_hostname": os.environ.get("SP_HOSTNAME", ""),
    "sp_site_path": os.environ.get("SP_SITE_PATH", ""),
    "sp_library_name": os.environ.get("SP_LIBRARY_NAME", "Documents"),
    "sp_start_folder": os.environ.get("SP_START_FOLDER", "/"),
    "local_download_path": os.environ.get("LOCAL_DOWNLOAD_PATH", "./downloaded_files"),
    "max_workers": 25  # Default parallel workers
}

params = default_params

# ✅ Parameter Validation
def validate_parameters(params):
    """Validate required parameters."""
    required_params = [
        "tenant_id", "client_id", "client_secret", 
        "sp_hostname", "sp_site_path", "sp_library_name", "sp_start_folder"
    ]
    
    missing = [param for param in required_params if not params.get(param)]
    if missing:
        raise ValueError(f"Missing required parameters: {missing}")
    
    return True

# ✅ Cache Management Functions
def validate_cache(cache_file, site_id, drive_id, folder_id, max_age_hours=24):
    """Validate if the cache is still valid for the current configuration and age."""
    if not cache_file.exists():
        return False
    
    try:
        with open(cache_file, 'r') as f:
            cache_data = json.load(f)
        
        # Check if cache matches current configuration
        if not (cache_data.get("site_id") == site_id and 
                cache_data.get("drive_id") == drive_id and 
                cache_data.get("folder_id") == folder_id):
            logger.warning("⚠️ Cache configuration mismatch. Will re-scan.")
            return False
        
        # Check cache age
        cache_timestamp = cache_data.get("timestamp")
        if cache_timestamp:
            from datetime import datetime, timedelta
            cache_time = datetime.fromisoformat(cache_timestamp.replace('Z', '+00:00') if 'Z' in cache_timestamp else cache_timestamp)
            cache_age = datetime.now() - cache_time
            if cache_age > timedelta(hours=max_age_hours):
                logger.info(f"⏰ Cache is {cache_age.total_seconds()/3600:.1f} hours old (max: {max_age_hours}h). Will re-scan to detect new files.")
                return False
        
        return True
        
    except Exception as e:
        logger.warning(f"⚠️ Cache validation failed: {e}")
        return False

def clear_cache(local_path):
    """Clear the file list cache."""
    cache_file = Path(local_path) / "file_list_cache.json"
    progress_file = Path(local_path) / "download_progress.json"
    
    removed_files = []
    if cache_file.exists():
        cache_file.unlink()
        removed_files.append("file_list_cache.json")
    
    if progress_file.exists():
        progress_file.unlink()
        removed_files.append("download_progress.json")
    
    if removed_files:
        logger.info(f"🗑️ Cleared cache files: {', '.join(removed_files)}")
    else:
        logger.info("ℹ️ No cache files to clear")

# ✅ Authentication Functions
def get_graph_token(tenant_id, client_id, client_secret):
    """Get access token for Microsoft Graph API."""
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    token_data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://graph.microsoft.com/.default"
    }
    response = requests.post(token_url, data=token_data)
    response.raise_for_status()
    return response.json()["access_token"]

def get_site_id(sp_hostname, sp_site_path, headers):
    """Get SharePoint site ID."""
    site_url = f"https://graph.microsoft.com/v1.0/sites/{sp_hostname}:/{sp_site_path}"
    response = requests.get(site_url, headers=headers)
    response.raise_for_status()
    return response.json()["id"]

def get_drive_id(site_id, library_name, headers):
    """Get document library (drive) ID."""
    drive_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
    response = requests.get(drive_url, headers=headers)
    response.raise_for_status()
    
    drives = response.json()["value"]
    logger.info("📂 Available Drives:")
    for d in drives:
        logger.info(f"- Name: {d['name']}, ID: {d['id']}")
    
    drive_id = next(
        (d["id"] for d in drives if d["name"].lower() == library_name.lower()),
        None
    )
    
    if not drive_id:
        available = [d["name"] for d in drives]
        raise ValueError(f"❌ Drive '{library_name}' not found. Available: {available}")
    
    return drive_id

def get_folder_id(drive_id, folder_path, headers):
    """Navigate to folder and get its ID."""
    folder_id = "root"
    if folder_path and folder_path != "/":
        folder_parts = folder_path.strip("/").split("/")
        for part in folder_parts:
            url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{folder_id}/children"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            items = response.json()["value"]
            match = next((i for i in items if i["name"] == part and "folder" in i), None)
            if match:
                folder_id = match["id"]
                logger.info(f"✅ Found folder: {part}")
            else:
                raise ValueError(f"❌ Folder '{part}' not found.")
    return folder_id

def list_files_recursively(drive_id, folder_id, headers, path_prefix=""):
    """Recursively list all files in a folder."""
    all_files = []
    url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{folder_id}/children"

    while url:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        for item in data.get("value", []):
            if "folder" in item:
                # Recursively process subfolders
                logger.info(f"📁 Processing folder: {path_prefix}{item['name']}/")
                all_files.extend(list_files_recursively(
                    drive_id, item["id"], headers, f"{path_prefix}{item['name']}/"
                ))
            else:
                # Add file to list
                all_files.append({
                    "id": item["id"],
                    "name": item["name"],
                    "path": f"{path_prefix}{item['name']}",
                    "download_url": item["@microsoft.graph.downloadUrl"]
                })
        
        url = data.get("@odata.nextLink", None)
    
    return all_files

# 🚀 OPTIMIZED SESSION MANAGEMENT
def create_optimized_session():
    """Create a requests session optimized for high-volume downloads."""
    session = requests.Session()
    
    # Connection pooling and keep-alive
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=30,  # Number of connection pools
        pool_maxsize=100,     # Max connections per pool
        max_retries=Retry(
            total=2,
            status_forcelist=[429, 500, 502, 503, 504],
            backoff_factor=0.2
        )
    )
    
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    # Optimize headers
    session.headers.update({
        'Connection': 'keep-alive',
        'User-Agent': 'SharePoint-TurboDownloader/1.0'
    })
    
    return session

# ✅ Download Functions
def get_fresh_download_url(drive_id, file_id, headers, session=None):
    """Get a fresh download URL for a file."""
    if session is None:
        session = requests
    
    try:
        url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{file_id}"
        response = session.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        file_data = response.json()
        return file_data.get("@microsoft.graph.downloadUrl")
    except Exception as e:
        logger.warning(f"⚠️ Failed to get fresh download URL: {e}")
        return None

def download_file_safely_turbo(file_info, local_base_path, headers, drive_id=None, session=None, max_retries=2):
    """🚀 TURBO: Optimized download function with connection reuse and reduced retries."""
    if session is None:
        session = create_optimized_session()
    
    file_path = file_info["path"]
    download_url = file_info["download_url"]
    file_id = file_info.get("id")
    
    # Create local file path
    local_file_path = Path(local_base_path) / file_path
    local_file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Skip if file already exists
    if local_file_path.exists():
        return {"status": "success", "file": file_path, "local_path": str(local_file_path), "skipped": True}
    
    for attempt in range(max_retries):
        try:
            logger.info(f"🚀 Downloading: {file_path} (attempt {attempt + 1})")
            
            # Reduced timeout for faster failure detection
            response = session.get(download_url, headers=headers, stream=True, timeout=15)
            response.raise_for_status()
            
            # Optimized chunk size for better performance (64KB chunks)
            with open(local_file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
            
            logger.info(f"✅ Downloaded: {file_path}")
            return {"status": "success", "file": file_path, "local_path": str(local_file_path)}
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401 and drive_id and file_id and attempt < max_retries - 1:
                # Get fresh URL on 401
                logger.warning(f"⚠️ 401 error for {file_path}, attempting to get fresh download URL...")
                fresh_url = get_fresh_download_url(drive_id, file_id, headers, session)
                if fresh_url:
                    download_url = fresh_url
                    logger.info(f"🔄 Got fresh download URL, retrying...")
                    continue
            
            logger.warning(f"❌ Attempt {attempt + 1} failed for {file_path}: {e}")
            if attempt == max_retries - 1:
                return {"status": "failed", "file": file_path, "error": str(e)}
            time.sleep(0.3)  # Reduced wait time
            
        except Exception as e:
            logger.warning(f"❌ Attempt {attempt + 1} failed for {file_path}: {e}")
            if attempt == max_retries - 1:
                return {"status": "failed", "file": file_path, "error": str(e)}
            time.sleep(0.3)
    
    return {"status": "failed", "file": file_path, "error": "Max retries exceeded"}

# 🚀 PARALLEL DOWNLOAD ENGINE
def download_all_files_turbo(file_list, local_download_path, headers, tenant_id, client_id, client_secret, drive_id=None, max_workers=10):
    """🚀 TURBO: Download all files with parallel processing for maximum speed."""
    local_download_path = Path(local_download_path)
    local_download_path.mkdir(parents=True, exist_ok=True)
    
    # Progress tracking
    progress_file = local_download_path / "download_progress_turbo.json"
    results = {"success": [], "failed": []}
    total_files = len(file_list)
    start_index = 0
    
    # Load previous progress
    if progress_file.exists():
        try:
            with open(progress_file, 'r') as f:
                progress_data = json.load(f)
                results = progress_data.get("results", {"success": [], "failed": []})
                start_index = progress_data.get("last_processed_index", 0) + 1
                logger.info(f"📂 TURBO: Resuming from file {start_index}/{total_files}")
                logger.info(f"📊 Previous progress: {len(results['success'])} successful, {len(results['failed'])} failed")
        except Exception as e:
            logger.warning(f"⚠️ Could not load progress file: {e}. Starting fresh.")
    
    # Filter out already downloaded files
    remaining_files = []
    skipped_count = 0
    for i, file_info in enumerate(file_list[start_index:], start_index):
        expected_path = Path(local_download_path) / file_info["path"]
        if not expected_path.exists():
            remaining_files.append((i, file_info))
        else:
            results["success"].append({
                "status": "success", 
                "file": file_info["path"], 
                "local_path": str(expected_path),
                "skipped": True
            })
            skipped_count += 1
    
    logger.info(f"🚀 TURBO MODE: Starting parallel download of {len(remaining_files)} files using {max_workers} workers")
    if skipped_count > 0:
        logger.info(f"⏭️ Skipped {skipped_count} already downloaded files")
    
    # Thread-safe progress tracking
    progress_lock = threading.Lock()
    completed_count = len([r for r in results["success"] if not r.get("skipped", False)])
    total_processed = len(results["success"])
    
    # Create session pool for workers
    session_pool = Queue()
    for _ in range(max_workers):
        session_pool.put(create_optimized_session())
    
    def download_worker(file_data):
        """🚀 TURBO: Worker function for parallel downloads."""
        index, file_info = file_data
        
        # Get session from pool
        session = session_pool.get()
        
        try:
            # Get fresh token for this thread if needed
            thread_headers = headers.copy()
            
            result = download_file_safely_turbo(file_info, local_download_path, thread_headers, drive_id, session)
            
            # Handle 401 errors with token refresh
            if result["status"] == "failed" and "401" in str(result.get("error", "")):
                try:
                    new_token = get_graph_token(tenant_id, client_id, client_secret)
                    thread_headers["Authorization"] = f"Bearer {new_token}"
                    result = download_file_safely_turbo(file_info, local_download_path, thread_headers, drive_id, session, max_retries=1)
                except Exception as e:
                    logger.warning(f"⚠️ Token refresh failed for {file_info['path']}: {e}")
            
            # Thread-safe progress update
            with progress_lock:
                nonlocal completed_count, total_processed
                total_processed += 1
                
                if result["status"] == "success":
                    results["success"].append(result)
                    if not result.get("skipped", False):
                        completed_count += 1
                else:
                    results["failed"].append(result)
                
                # Log progress every 50 files for more frequent updates
                if total_processed % 50 == 0:
                    progress_pct = (total_processed / total_files) * 100
                    logger.info(f"🔥 TURBO Progress: {total_processed}/{total_files} ({progress_pct:.1f}%) - {completed_count} new downloads")
                
                # Save progress every 1000 files
                if total_processed % 1000 == 0:
                    progress_data = {
                        "last_processed_index": index,
                        "results": results,
                        "timestamp": datetime.now().isoformat(),
                        "turbo_mode": True
                    }
                    with open(progress_file, 'w') as f:
                        json.dump(progress_data, f, indent=2)
                    logger.info(f"💾 Progress saved at {total_processed} files")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Worker error for {file_info['path']}: {e}")
            return {"status": "failed", "file": file_info["path"], "error": str(e)}
        finally:
            # Return session to pool
            session_pool.put(session)
    
    # Execute parallel downloads
    start_time = time.time()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all download tasks
            future_to_file = {executor.submit(download_worker, file_data): file_data for file_data in remaining_files}
            
            # Process completed downloads
            completed_futures = 0
            for future in concurrent.futures.as_completed(future_to_file):
                completed_futures += 1
                try:
                    result = future.result()
                    
                    # Log speed statistics every 1000 completed tasks
                    if completed_futures % 1000 == 0:
                        elapsed_time = time.time() - start_time
                        speed = completed_futures / elapsed_time
                        eta_seconds = (len(remaining_files) - completed_futures) / speed if speed > 0 else 0
                        eta_hours = eta_seconds / 3600
                        logger.info(f"🚀 Speed: {speed:.1f} files/sec | ETA: {eta_hours:.1f} hours")
                        
                except Exception as e:
                    file_data = future_to_file[future]
                    logger.error(f"❌ Download failed for {file_data[1]['path']}: {e}")
    
    except KeyboardInterrupt:
        logger.info("⏸️ TURBO: Download interrupted by user")
        # Save final progress
        progress_data = {
            "last_processed_index": total_processed,
            "results": results,
            "timestamp": datetime.now().isoformat(),
            "turbo_mode": True
        }
        with open(progress_file, 'w') as f:
            json.dump(progress_data, f, indent=2)
        logger.info(f"💾 Progress saved. Resume by running the script again.")
        raise
    
    # Final statistics
    elapsed_time = time.time() - start_time
    if elapsed_time > 0:
        avg_speed = completed_count / elapsed_time
        logger.info(f"🏁 TURBO Complete! Average speed: {avg_speed:.1f} files/sec")
    
    # Clean up progress file on completion
    if progress_file.exists() and len(results["failed"]) == 0:
        progress_file.unlink()
        logger.info("🗑️ Progress file cleaned up")
    
    return results

# ✅ Main Execution
def main():
    try:
        # Validate parameters
        validate_parameters(params)
        
        # Extract parameters
        tenant_id = params["tenant_id"]
        client_id = params["client_id"]
        client_secret = params["client_secret"]
        sp_hostname = params["sp_hostname"]
        sp_site_path = params["sp_site_path"]
        sp_library_name = params["sp_library_name"]
        sp_start_folder = params["sp_start_folder"]
        max_workers = params.get("max_workers", 10)
        
        logger.info("🔐 TURBO: Authenticating with Microsoft Graph...")
        access_token = get_graph_token(tenant_id, client_id, client_secret)
        headers = {"Authorization": f"Bearer {access_token}"}
        
        logger.info("🌐 Getting SharePoint site...")
        site_id = get_site_id(sp_hostname, sp_site_path, headers)
        logger.info(f"✅ Site found: {site_id}")
        
        logger.info("📚 Getting document library...")
        drive_id = get_drive_id(site_id, sp_library_name, headers)
        logger.info(f"✅ Drive found: {drive_id}")
        
        logger.info("📁 Navigating to start folder...")
        start_folder_id = get_folder_id(drive_id, sp_start_folder, headers)
        logger.info(f"✅ Folder found: {start_folder_id}")
        
        # Check for cached file list
        local_path = params.get("local_download_path", "./downloaded_files")
        cache_file = Path(local_path) / "file_list_cache.json"
        force_refresh = params.get("force_refresh", False)
        
        if (not force_refresh and 
            cache_file.exists() and 
            validate_cache(cache_file, site_id, drive_id, start_folder_id)):
            logger.info("📂 Found valid cached file list, loading...")
            try:
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                    file_list = cache_data.get("files", [])
                    cache_timestamp = cache_data.get("timestamp", "")
                    logger.info(f"✅ Loaded {len(file_list)} files from cache (created: {cache_timestamp})")
                    logger.info("💡 To detect new files, run: python dll_pdf_fabric_turbo.py --refresh")
            except Exception as e:
                logger.warning(f"⚠️ Could not load file cache: {e}. Will re-scan.")
                file_list = None
        else:
            if force_refresh:
                logger.info("🔄 Force refresh requested, ignoring cache")
            file_list = None
        
        # Scan files if needed
        if file_list is None:
            logger.info("📋 Listing files recursively...")
            file_list = list_files_recursively(drive_id, start_folder_id, headers)
            logger.info(f"✅ Total files found: {len(file_list)}")
            
            # Save to cache
            try:
                Path(local_path).mkdir(parents=True, exist_ok=True)
                cache_data = {
                    "files": file_list,
                    "timestamp": datetime.now().isoformat(),
                    "total_files": len(file_list),
                    "site_id": site_id,
                    "drive_id": drive_id,
                    "folder_id": start_folder_id
                }
                with open(cache_file, 'w') as f:
                    json.dump(cache_data, f, indent=2)
                logger.info(f"💾 File list cached for future runs")
            except Exception as e:
                logger.warning(f"⚠️ Could not save file cache: {e}")
        else:
            logger.info(f"✅ Using cached file list: {len(file_list)} files")
        
        # 🚀 USE TURBO PARALLEL DOWNLOADS FOR MAXIMUM SPEED
        logger.info(f"🚀 TURBO MODE: Using {max_workers} parallel workers for maximum speed")
        
        results = download_all_files_turbo(
            file_list, local_path, headers, tenant_id, client_id, client_secret, drive_id, max_workers
        )
        
        # Summary
        success_count = len([r for r in results["success"] if not r.get("skipped")])
        skipped_count = len([r for r in results["success"] if r.get("skipped")])
        failed_count = len(results["failed"])
        
        logger.info(f"🎉 TURBO Download Complete!")
        logger.info(f"✅ Successfully downloaded: {success_count}")
        logger.info(f"⏭️ Skipped (already existed): {skipped_count}")
        logger.info(f"❌ Failed: {failed_count}")
        
        if results["failed"]:
            logger.info("Failed files (first 10):")
            for failed in results["failed"][:10]:
                logger.error(f"  - {failed['file']}: {failed['error']}")
            if len(results["failed"]) > 10:
                logger.info(f"  ... and {len(results['failed']) - 10} more failures")
        
        return results
        
    except Exception as e:
        logger.error(f"TURBO script failed: {e}")
        raise

if __name__ == "__main__":
    # Parse command line arguments for speed optimization
    max_workers = 10  # Default
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--clear-cache":
            local_path = params.get("local_download_path", "./downloaded_files")
            clear_cache(local_path)
            sys.exit(0)
        elif sys.argv[1] == "--refresh" or sys.argv[1] == "--force-refresh":
            logger.info("🔄 Force refresh mode: Will re-scan SharePoint for new files")
            params["force_refresh"] = True
        elif sys.argv[1] == "--turbo":
            max_workers = 25
            logger.info("🚀 TURBO MODE: Using 25 parallel workers for maximum speed!")
            params["max_workers"] = max_workers
        elif sys.argv[1] == "--fast":
            max_workers = 15
            logger.info("⚡ FAST MODE: Using 15 parallel workers")
            params["max_workers"] = max_workers
        elif sys.argv[1] == "--normal":
            max_workers = 10
            logger.info("📈 NORMAL MODE: Using 10 parallel workers")
            params["max_workers"] = max_workers
        elif sys.argv[1] == "--conservative":
            max_workers = 5
            logger.info("🐌 CONSERVATIVE MODE: Using 5 parallel workers (safest)")
            params["max_workers"] = max_workers
        elif sys.argv[1] == "--help":
            print("🚀 SharePoint TURBO File Download Automation")
            print("============================================")
            print("Usage:")
            print("  python dll_pdf_fabric_turbo.py                # Normal mode (10 workers)")
            print("  python dll_pdf_fabric_turbo.py --conservative # Conservative (5 workers)")
            print("  python dll_pdf_fabric_turbo.py --fast         # Fast mode (15 workers)")
            print("  python dll_pdf_fabric_turbo.py --turbo        # Turbo mode (25 workers)")
            print("  python dll_pdf_fabric_turbo.py --refresh      # Force re-scan for new files")
            print("  python dll_pdf_fabric_turbo.py --clear-cache  # Clear all cache files")
            print("  python dll_pdf_fabric_turbo.py --help         # Show this help")
            print("")
            print("🚀 Speed Modes:")
            print("  • Conservative: ~5-8 files/sec   (5 workers)  - Safest")
            print("  • Normal:       ~10-15 files/sec (10 workers) - Balanced")
            print("  • Fast:         ~15-20 files/sec (15 workers) - Faster")
            print("  • Turbo:        ~20-30 files/sec (25 workers) - Maximum speed")
            print("")
            print("⏱️  Estimated completion times for 376,882 files:")
            print("  • Conservative: ~12-20 hours")
            print("  • Normal:       ~6-10 hours")
            print("  • Fast:         ~4-6 hours")
            print("  • Turbo:        ~3-4 hours")
            print("")
            print("🎯 Features:")
            print("  • Parallel downloads with connection pooling")
            print("  • Automatic resume from interruptions")
            print("  • Smart caching with 24h auto-expiration")
            print("  • Real-time speed monitoring")
            print("  • Thread-safe progress tracking")
            print("  • Optimized for SharePoint tempauth handling")
            sys.exit(0)
    
    main()
