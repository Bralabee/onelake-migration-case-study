import os
import requests
from datetime import datetime
import time
import logging
from pathlib import Path
import json
import sys

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
    "local_download_path": os.environ.get("LOCAL_DOWNLOAD_PATH", "./downloaded_files")
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

# ✅ Download Functions
def get_fresh_download_url(drive_id, file_id, headers):
    """Get a fresh download URL for a file."""
    try:
        url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{file_id}"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        file_data = response.json()
        return file_data.get("@microsoft.graph.downloadUrl")
    except Exception as e:
        logger.warning(f"⚠️ Failed to get fresh download URL: {e}")
        return None

def download_file_safely(file_info, local_base_path, headers, drive_id=None, max_retries=3):
    """Download a single file with retry logic and error handling."""
    file_path = file_info["path"]
    download_url = file_info["download_url"]
    file_id = file_info.get("id")
    
    # Create local file path
    local_file_path = Path(local_base_path) / file_path
    local_file_path.parent.mkdir(parents=True, exist_ok=True)
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Downloading: {file_path} (attempt {attempt + 1})")
            
            # Use authorization headers for download instead of relying on tempauth URLs
            response = requests.get(download_url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()
            
            with open(local_file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            logger.info(f"✅ Downloaded: {file_path}")
            return {"status": "success", "file": file_path, "local_path": str(local_file_path)}
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401 and drive_id and file_id and attempt < max_retries - 1:
                # Try to get a fresh download URL
                logger.warning(f"⚠️ 401 error for {file_path}, attempting to get fresh download URL...")
                fresh_url = get_fresh_download_url(drive_id, file_id, headers)
                if fresh_url:
                    download_url = fresh_url
                    logger.info(f"🔄 Got fresh download URL, retrying...")
                    continue
            
            logger.warning(f"❌ Attempt {attempt + 1} failed for {file_path}: {e}")
            if attempt == max_retries - 1:
                return {"status": "failed", "file": file_path, "error": str(e)}
            time.sleep(2 ** attempt)  # Exponential backoff
            
        except Exception as e:
            logger.warning(f"❌ Attempt {attempt + 1} failed for {file_path}: {e}")
            if attempt == max_retries - 1:
                return {"status": "failed", "file": file_path, "error": str(e)}
            time.sleep(2 ** attempt)  # Exponential backoff

def download_all_files(file_list, local_download_path, headers, tenant_id, client_id, client_secret, drive_id=None):
    """Download all files with progress tracking, error logging, token refresh, and resume capability."""
    local_download_path = Path(local_download_path)
    local_download_path.mkdir(parents=True, exist_ok=True)
    
    # Progress tracking file
    progress_file = local_download_path / "download_progress.json"
    
    results = {"success": [], "failed": []}
    total_files = len(file_list)
    start_index = 0
    
    # Load previous progress if exists
    if progress_file.exists():
        try:
            with open(progress_file, 'r') as f:
                progress_data = json.load(f)
                results = progress_data.get("results", {"success": [], "failed": []})
                start_index = progress_data.get("last_processed_index", 0) + 1
                logger.info(f"📂 Resuming from file {start_index}/{total_files}")
                logger.info(f"📊 Previous progress: {len(results['success'])} successful, {len(results['failed'])} failed")
        except Exception as e:
            logger.warning(f"⚠️ Could not load progress file: {e}. Starting fresh.")
    
    logger.info(f"Starting download of {total_files - start_index} remaining files to {local_download_path}")
    
    # Track when we last refreshed the token
    last_token_refresh = time.time()
    token_refresh_interval = 3600  # Refresh every hour (3600 seconds)
    
    try:
        for i in range(start_index, total_files):
            file_info = file_list[i]
            progress_pct = ((i + 1) / total_files) * 100
            logger.info(f"Progress: {i + 1}/{total_files} ({progress_pct:.1f}%)")
            
            # Check if file already exists to avoid re-downloading
            expected_path = Path(local_download_path) / file_info["path"]
            if expected_path.exists():
                logger.info(f"⏭️ Skipping existing file: {file_info['path']}")
                results["success"].append({
                    "status": "success", 
                    "file": file_info["path"], 
                    "local_path": str(expected_path),
                    "skipped": True
                })
                continue
            
            # Refresh token if needed (every hour or on 401 errors)
            current_time = time.time()
            if current_time - last_token_refresh > token_refresh_interval:
                logger.info("🔄 Refreshing authentication token...")
                try:
                    new_token = get_graph_token(tenant_id, client_id, client_secret)
                    headers["Authorization"] = f"Bearer {new_token}"
                    last_token_refresh = current_time
                    logger.info("✅ Token refreshed successfully")
                except Exception as e:
                    logger.warning(f"⚠️ Token refresh failed: {e}")
            
            result = download_file_safely(file_info, local_download_path, headers, drive_id)
            
            # If we get a 401 error, try refreshing token and retry once
            if result["status"] == "failed" and "401" in str(result.get("error", "")):
                logger.info("🔄 401 error detected, refreshing token and retrying...")
                try:
                    new_token = get_graph_token(tenant_id, client_id, client_secret)
                    headers["Authorization"] = f"Bearer {new_token}"
                    last_token_refresh = current_time
                    logger.info("✅ Token refreshed, retrying download...")
                    result = download_file_safely(file_info, local_download_path, headers, drive_id, max_retries=1)
                except Exception as e:
                    logger.warning(f"⚠️ Token refresh failed: {e}")
            
            if result["status"] == "success":
                results["success"].append(result)
            else:
                results["failed"].append(result)
            
            # Save progress every 100 files
            if (i + 1) % 100 == 0:
                progress_data = {
                    "last_processed_index": i,
                    "results": results,
                    "timestamp": datetime.now().isoformat()
                }
                with open(progress_file, 'w') as f:
                    json.dump(progress_data, f, indent=2)
                logger.info(f"💾 Progress saved at file {i + 1}")
    
    except KeyboardInterrupt:
        logger.info("⏸️ Download interrupted by user")
        # Save progress before exiting
        progress_data = {
            "last_processed_index": i,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
        with open(progress_file, 'w') as f:
            json.dump(progress_data, f, indent=2)
        logger.info(f"💾 Progress saved. Resume by running the script again.")
        raise
    
    # Clean up progress file on successful completion
    if progress_file.exists():
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
        
        logger.info("🔐 Authenticating with Microsoft Graph...")
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
        
        # Check for cached file list to avoid re-scanning
        local_path = params.get("local_download_path", "./downloaded_files")
        cache_file = Path(local_path) / "file_list_cache.json"
        
        # Check if force refresh is requested
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
                    logger.info("💡 To detect new files, run: python dll_pdf_fabric.py --refresh")
            except Exception as e:
                logger.warning(f"⚠️ Could not load file cache: {e}. Will re-scan.")
                file_list = None
        else:
            if force_refresh:
                logger.info("🔄 Force refresh requested, ignoring cache")
            file_list = None
        
        # Scan files if no cache or cache failed to load
        if file_list is None:
            logger.info("📋 Listing files recursively...")
            file_list = list_files_recursively(drive_id, start_folder_id, headers)
            logger.info(f"✅ Total files found: {len(file_list)}")
            
            # Save file list to cache
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
        results = download_all_files(file_list, local_path, headers, tenant_id, client_id, client_secret, drive_id)
        
        # Summary
        success_count = len(results["success"])
        failed_count = len(results["failed"])
        
        logger.info(f"📊 Download Summary:")
        logger.info(f"✅ Successful: {success_count}")
        logger.info(f"❌ Failed: {failed_count}")
        
        if results["failed"]:
            logger.info("Failed files:")
            for failed in results["failed"]:
                logger.error(f"  - {failed['file']}: {failed['error']}")
        
        return results
        
    except Exception as e:
        logger.error(f"Script failed: {e}")
        raise

if __name__ == "__main__":
    # Check for command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--clear-cache":
            local_path = params.get("local_download_path", "./downloaded_files")
            clear_cache(local_path)
            sys.exit(0)
        elif sys.argv[1] == "--refresh" or sys.argv[1] == "--force-refresh":
            logger.info("🔄 Force refresh mode: Will re-scan SharePoint for new files")
            # Set a flag to force cache invalidation
            params["force_refresh"] = True
        elif sys.argv[1] == "--help":
            print("SharePoint File Download Automation")
            print("===================================")
            print("Usage:")
            print("  python dll_pdf_fabric.py              # Run normal download (uses cache if valid)")
            print("  python dll_pdf_fabric.py --refresh    # Force re-scan to detect new files")
            print("  python dll_pdf_fabric.py --clear-cache    # Clear all cache files")
            print("  python dll_pdf_fabric.py --help           # Show this help")
            print("")
            print("Features:")
            print("  • Automatic resume from interruptions")
            print("  • File list caching to avoid re-scanning (expires after 24h)")
            print("  • Token refresh for long-running downloads")
            print("  • Progress tracking every 100 files")
            print("  • Skip existing files automatically")
            print("")
            print("Cache Behavior:")
            print("  • Cache expires after 24 hours to detect new files")
            print("  • Use --refresh to force immediate re-scan")
            print("  • Use --clear-cache to remove all cached data")
            sys.exit(0)
    
    main()