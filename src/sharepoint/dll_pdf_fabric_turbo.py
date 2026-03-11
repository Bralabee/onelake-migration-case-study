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

def load_env_file_ordered(profile: str | None):
    """Load environment variables with profile precedence.

    Precedence (first found wins for each variable; existing os.environ not overwritten):
      1. config/profiles/<profile>.env (if --profile provided)
      2. .env in repo root / config/.env variants
    """
    searched = []
    def apply_file(path: str):
        try:
            with open(path, 'r') as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        if key not in os.environ:  # do not override existing env
                            os.environ[key] = value.strip('"\'')
            logger.info(f"📄 Loaded env file: {path}")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Failed loading {path}: {e}")
        return False

    # Candidate paths
    candidates = []
    if profile:
        candidates.append(f"config/profiles/{profile}.env")
        candidates.append(f"../../config/profiles/{profile}.env")  # relative from src/sharepoint
    # generic .env fallbacks
    candidates.extend([
        ".env",
        "config/.env",
        "../../config/.env",
        "../config/.env"
    ])
    loaded_any = False
    for c in candidates:
        searched.append(c)
        if os.path.exists(c):
            loaded_any = apply_file(c) or loaded_any
    if not loaded_any:
        logger.warning(f"⚠️ No env files loaded (searched: {searched})")

# Parse early for --profile before rest of logic (lightweight scan of sys.argv)
_profile = None
for idx, tok in enumerate(sys.argv[1:]):
    if tok == "--profile" and idx + 2 <= len(sys.argv[1:]):
        try:
            _profile = sys.argv[1:][idx + 1]
        except IndexError:
            pass
        break

load_env_file_ordered(_profile)

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
    "max_workers": 25,  # Default parallel workers
    "state_dir": os.environ.get("STATE_DIR", ".state"),
    "max_cache_age_hours": 24,
    "auto_refresh_if_limit_exceeds": False,
    "download_new_only": False
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

def list_files_recursively(drive_id, folder_id, headers, path_prefix="", limit=None, _collected=None):
    """Recursively list files up to an optional limit.

    Args:
        drive_id: SharePoint drive ID.
        folder_id: Current folder item ID ("root" for start).
        headers: Auth headers.
        path_prefix: Relative folder path prefix.
        limit: Optional int cap on number of files to collect.
        _collected: Internal accumulator list (do not pass manually).
    Returns:
        List[dict]: File metadata entries (up to limit if provided).
    """
    if _collected is None:
        _collected = []

    # Early exit if limit satisfied
    if limit is not None and len(_collected) >= limit:
        return _collected

    url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{folder_id}/children"

    while url:
        # Stop further paging if limit reached
        if limit is not None and len(_collected) >= limit:
            break

        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        for item in data.get("value", []):
            # Check limit before deeper work
            if limit is not None and len(_collected) >= limit:
                break

            if "folder" in item:
                logger.info(f"📁 Processing folder: {path_prefix}{item['name']}/")
                list_files_recursively(
                    drive_id,
                    item["id"],
                    headers,
                    f"{path_prefix}{item['name']}/",
                    limit=limit,
                    _collected=_collected
                )
            else:
                _collected.append({
                    "id": item["id"],
                    "name": item["name"],
                    "path": f"{path_prefix}{item['name']}",
                    "download_url": item["@microsoft.graph.downloadUrl"]
                })
                if limit is not None and len(_collected) >= limit:
                    break

        url = data.get("@odata.nextLink", None)

    return _collected

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
def download_all_files_turbo(file_list, local_download_path, headers, tenant_id, client_id, client_secret, drive_id=None, max_workers=10, state_base:Path|None=None, profile:str|None=None):
    """🚀 TURBO: Download all files with parallel processing for maximum speed."""
    local_download_path = Path(local_download_path)
    local_download_path.mkdir(parents=True, exist_ok=True)
    
    # Progress tracking
    if state_base is None:
        state_base = Path(params.get("state_dir", ".state"))
    profile_key = profile or params.get("profile") or "default"
    namespaced = state_base / profile_key / "downloader"
    namespaced.mkdir(parents=True, exist_ok=True)
    progress_file = namespaced / "download_progress_turbo.json"
    # Legacy fallback import
    legacy_progress = Path(local_download_path) / "download_progress_turbo.json"
    if not progress_file.exists() and legacy_progress.exists():
        try:
            progress_file.write_text(legacy_progress.read_text())
            logger.info("♻️ Imported legacy download_progress_turbo.json into namespaced state")
        except Exception:
            pass
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
    skipped_count = 0  # legacy count of existing files treated as skips in normal mode
    ignored_existing_count = 0  # new-only mode: existing files ignored (not counted as skips)
    new_only = params.get("download_new_only", False)
    for i, file_info in enumerate(file_list[start_index:], start_index):
        expected_path = Path(local_download_path) / file_info["path"]
        exists = expected_path.exists()
        if new_only and exists:
            # In new-only mode we neither enqueue nor mark as skipped; we just ignore and count separately.
            ignored_existing_count += 1
            continue
        if not exists:
            remaining_files.append((i, file_info))
        else:
            results["success"].append({
                "status": "success",
                "file": file_info["path"],
                "local_path": str(expected_path),
                "skipped": True
            })
            skipped_count += 1
    # (moved outside loop) announce how many will actually download once after scan
    logger.info(f"🚀 TURBO MODE: Starting parallel download of {len(remaining_files)} files using {max_workers} workers")
    if skipped_count > 0 and not new_only:
        logger.info(f"⏭️ Skipped {skipped_count} already downloaded files")
    if new_only and ignored_existing_count > 0:
        logger.info(f"🆕 New-only mode: ignored {ignored_existing_count} existing files (not counted as skips)")
    
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
    
    # Attach meta summary for caller/orchestrator (so ignored_existing persists)
    try:
        results["meta"] = {
            "ignored_existing": ignored_existing_count,
            "skipped_existing": skipped_count,
            "total_files_considered": total_files,
            "new_only": new_only,
            "remaining_attempted": len(remaining_files)
        }
    except Exception as _e:
        logger.warning(f"⚠️ Could not attach meta to results: {_e}")

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
            validate_cache(cache_file, site_id, drive_id, start_folder_id, max_age_hours=params.get("max_cache_age_hours",24))):
            logger.info("📂 Found valid cached file list, loading...")
            try:
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                    import hashlib as _hl
                    expected_ctx = f"{cache_data.get('site_id')}|{cache_data.get('drive_id')}|{cache_data.get('folder_id')}|{sp_hostname}|{sp_site_path}|{sp_library_name}"
                    expected_hash = _hl.sha256(expected_ctx.encode()).hexdigest()[:16]
                    stored_hash = cache_data.get("context_hash")
                    if stored_hash and stored_hash != expected_hash:
                        logger.warning("⚠️ Context hash mismatch; ignoring stale cache")
                        file_list = None
                    else:
                        file_list = cache_data.get("files", [])
                        cache_timestamp = cache_data.get("timestamp", "")
                        logger.info(f"✅ Loaded {len(file_list)} files from cache (created: {cache_timestamp})")
                        logger.info("💡 To detect new files, run: python dll_pdf_fabric_turbo.py --refresh")
                        # Conditional AUTO-REFRESH: only if flag enabled and user requested higher limit
                        requested_limit = params.get("limit")
                        if params.get("auto_refresh_if_limit_exceeds") and requested_limit and requested_limit > len(file_list):
                            logger.info(f"🔄 AUTO-REFRESH: Requested limit {requested_limit} exceeds cached {len(file_list)}; re-scanning SharePoint (flag enabled)")
                            file_list = None
            except Exception as e:
                logger.warning(f"⚠️ Could not load file cache: {e}. Will re-scan.")
                file_list = None
        else:
            if force_refresh:
                logger.info("🔄 Force refresh requested, ignoring cache")
            file_list = None
        
        # Determine if a limit is requested (set during arg parsing)
        limit = params.get("limit")

        # Scan files if needed
        if file_list is None:
            logger.info("📋 Listing files recursively...")
            file_list = list_files_recursively(drive_id, start_folder_id, headers, limit=limit)
            logger.info(f"✅ Total files discovered: {len(file_list)} (limit={'∞' if limit is None else limit})")
            
            # Save to cache
            try:
                Path(local_path).mkdir(parents=True, exist_ok=True)
                # Metadata + context hash for invalidation across profiles/config changes
                import hashlib as _hl
                context_str = f"{site_id}|{drive_id}|{start_folder_id}|{sp_hostname}|{sp_site_path}|{sp_library_name}"
                context_hash = _hl.sha256(context_str.encode()).hexdigest()[:16]
                cache_data = {
                    "schema_version": 1,
                    "profile": params.get("profile") or _profile or "default",
                    "files": file_list,
                    "timestamp": datetime.now().isoformat(),
                    "total_files": len(file_list),
                    "site_id": site_id,
                    "drive_id": drive_id,
                    "folder_id": start_folder_id,
                    "sp_hostname": sp_hostname,
                    "sp_site_path": sp_site_path,
                    "sp_library_name": sp_library_name,
                    "context_hash": context_hash
                }
                with open(cache_file, 'w') as f:
                    json.dump(cache_data, f, indent=2)
                logger.info(f"💾 File list cached for future runs")
            except Exception as e:
                logger.warning(f"⚠️ Could not save file cache: {e}")
        else:
            logger.info(f"✅ Using cached file list: {len(file_list)} files")
            # Apply limit on cached list if requested
            if limit is not None and len(file_list) > limit:
                logger.info(f"🎯 Applying limit to cached list: first {limit} of {len(file_list)} files")
                file_list = file_list[:limit]

        # 🚀 USE TURBO PARALLEL DOWNLOADS FOR MAXIMUM SPEED
        logger.info(f"🚀 TURBO MODE: Using {max_workers} parallel workers for maximum speed")

        results = download_all_files_turbo(
            file_list,
            local_path,
            headers,
            tenant_id,
            client_id,
            client_secret,
            drive_id,
            max_workers,
            state_base=Path(params.get("state_dir", ".state")),
            profile=_profile
        )

        # Summary section
        success_count = len([r for r in results["success"] if not r.get("skipped")])
        skipped_count = len([r for r in results["success"] if r.get("skipped")])
        failed_count = len(results["failed"])
        meta = results.get("meta", {})
        ignored_existing_count = meta.get("ignored_existing", 0)
        new_only_mode = meta.get("new_only", params.get("download_new_only", False))

        logger.info("🎉 TURBO Download Complete!")
        logger.info(f"✅ Successfully downloaded: {success_count}")
        logger.info(f"⏭️ Skipped (already existed): {skipped_count}")
        if new_only_mode:
            logger.info(f"📁 Ignored existing (new-only mode): {ignored_existing_count}")
        logger.info(f"❌ Failed: {failed_count}")

        try:
            total_available = len(file_list)
            summary = {
                "timestamp": datetime.now().isoformat(),
                "success_new": success_count,
                "skipped_existing": skipped_count if not new_only_mode else 0,
                "ignored_existing": ignored_existing_count if new_only_mode else 0,
                "failed": failed_count,
                "total_listed": total_available,
                "limit_requested": params.get("limit"),
                "total_available": total_available,
                "auto_refresh_if_limit_exceeds": params.get("auto_refresh_if_limit_exceeds", False),
                "max_cache_age_hours": params.get("max_cache_age_hours"),
                "download_new_only": new_only_mode,
                "profile": params.get("profile") or _profile or "default"
            }
            Path(local_path).mkdir(parents=True, exist_ok=True)
            (Path(local_path)/"last_run_summary.json").write_text(json.dumps(summary, indent=2))
            profile_key = summary["profile"]
            state_dir = Path(params.get("state_dir", ".state")) / profile_key / "downloader"
            state_dir.mkdir(parents=True, exist_ok=True)
            (state_dir/"last_run_summary.json").write_text(json.dumps(summary, indent=2))
        except Exception as e:
            logger.warning(f"⚠️ Could not write last_run_summary.json: {e}")

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
    # Enhanced argument parsing to allow multiple flags in any order
    args = sys.argv[1:]
    max_workers = params.get("max_workers", 10)
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--profile":
            # already processed early for env loading; skip its value here
            if i + 1 < len(args):
                i += 1  # skip value
            params["profile"] = _profile
            i += 1
            continue
        if arg == "--state-dir":
            if i + 1 >= len(args):
                print("❌ --state-dir requires a path argument")
                sys.exit(1)
            params["state_dir"] = args[i+1]
            logger.info(f"🗂️ State directory set to {args[i+1]}")
            i += 2
            continue
        if arg in ("--clear-cache",):
            local_path = params.get("local_download_path", "./downloaded_files")
            clear_cache(local_path)
            sys.exit(0)
        elif arg in ("--refresh", "--force-refresh"):
            logger.info("🔄 Force refresh mode: Will re-scan SharePoint for new files")
            params["force_refresh"] = True
        elif arg == "--turbo":
            max_workers = 25
            params["max_workers"] = max_workers
            logger.info("🚀 TURBO MODE: Using 25 parallel workers for maximum speed!")
        elif arg == "--fast":
            max_workers = 15
            params["max_workers"] = max_workers
            logger.info("⚡ FAST MODE: Using 15 parallel workers")
        elif arg == "--normal":
            max_workers = 10
            params["max_workers"] = max_workers
            logger.info("📈 NORMAL MODE: Using 10 parallel workers")
        elif arg == "--conservative":
            max_workers = 5
            params["max_workers"] = max_workers
            logger.info("🐌 CONSERVATIVE MODE: Using 5 parallel workers (safest)")
        elif arg == "--limit":
            # Next token should be an integer
            if i + 1 >= len(args):
                print("❌ --limit requires an integer argument")
                sys.exit(1)
            try:
                limit_val = int(args[i + 1])
                if limit_val <= 0:
                    raise ValueError
                params["limit"] = limit_val
                logger.info(f"🎯 LIMIT MODE: Will process only first {limit_val} files")
            except ValueError:
                print("❌ --limit value must be a positive integer")
                sys.exit(1)
            i += 1  # Skip value token
        elif arg == "--validate-config":
            missing = [k for k in ["tenant_id","client_id","client_secret","sp_hostname","sp_site_path","sp_library_name"] if not params.get(k)]
            if missing:
                print(f"❌ Missing config: {missing}")
                sys.exit(1)
            try:
                token = get_graph_token(params['tenant_id'], params['client_id'], params['client_secret'])
                headers = {"Authorization": f"Bearer {token}"}
                site_id = get_site_id(params['sp_hostname'], params['sp_site_path'], headers)
                _ = get_drive_id(site_id, params['sp_library_name'], headers)
                print("✅ Downloader configuration valid")
                sys.exit(0)
            except Exception as e:
                print(f"❌ Validation failed: {e}")
                sys.exit(2)
        elif arg == "--max-age":
            if i + 1 >= len(args):
                print("❌ --max-age requires integer hours")
                sys.exit(1)
            try:
                hours = int(args[i+1])
                if hours <= 0:
                    raise ValueError
                params["max_cache_age_hours"] = hours
                logger.info(f"⏰ Max cache age set to {hours}h")
            except ValueError:
                print("❌ --max-age must be positive integer hours")
                sys.exit(1)
            i += 1
        elif arg == "--auto-refresh-if-limit-exceeds":
            params["auto_refresh_if_limit_exceeds"] = True
            logger.info("🔄 Auto-refresh on limit exceed ENABLED")
        elif arg == "--download-new-only":
            params["download_new_only"] = True
            logger.info("🆕 Download NEW files only (existing files ignored)")
        elif arg == "--help":
            print("🚀 SharePoint TURBO File Download Automation")
            print("============================================")
            print("Usage:")
            print("  python dll_pdf_fabric_turbo.py [mode flags] [--limit N] [--refresh] [--clear-cache]")
            print("")
            print("Mode Flags (choose one, optional):")
            print("  --conservative   Use 5 workers (safest)")
            print("  --normal         Use 10 workers (default)")
            print("  --fast           Use 15 workers")
            print("  --turbo          Use 25 workers (max speed)")
            print("")
            print("Additional Options:")
            print("  --limit N        Only list & download first N files (respects cache)")
            print("  --refresh        Force re-scan (ignore cache)")
            print("  --clear-cache    Remove cached file list & progress files")
            print("  --download-new-only  Only attempt downloading files not already present (ignored files not counted as skips)")
            print("  --validate-config Validate configuration & API access then exit (0=ok)")
            print("  --help           Show this help message")
            print("")
            print("Features:")
            print("  • Parallel downloads with connection pooling")
            print("  • Automatic resume from interruptions")
            print("  • Smart caching with 24h auto-expiration")
            print("  • Real-time speed monitoring")
            print("  • Thread-safe progress tracking")
            print("  • Optimized for SharePoint tempauth handling")
            print("  • NEW: --limit for controlled sample downloads")
            sys.exit(0)
        else:
            print(f"⚠️  Unknown argument ignored: {arg}")
        i += 1

    main()
