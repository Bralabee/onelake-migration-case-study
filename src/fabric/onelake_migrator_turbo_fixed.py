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
import sys
import json
import contextlib
import asyncio
import aiohttp
import aiofiles
import logging
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from email.utils import formatdate
import time
from dotenv import load_dotenv
import multiprocessing as mp
from threading import Lock
import random
import argparse
import hashlib

# Setup logging first
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def _load_env_profile(profile: str | None):
    """Layered env loading with optional profile.
    Precedence (first assignment wins; no overwrite of existing):
      1. config/profiles/<profile>.env variants
      2. generic .env variants
    """
    searched = []
    def apply(path: str):
        try:
            with open(path, 'r') as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        k,v = line.strip().split('=',1)
                        if k not in os.environ:
                            os.environ[k] = v.strip('"\'')
            logger.info(f"📄 Loaded env: {path}")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Failed loading {path}: {e}")
            return False
    base_candidates = [
        ".env","config/.env","../../config/.env","../config/.env"
    ]
    prof_candidates = []
    if profile:
        prof_candidates = [
            f"config/profiles/{profile}.env",
            f"../../config/profiles/{profile}.env",
            f"../config/profiles/{profile}.env"
        ]
    loaded = False
    for c in prof_candidates + base_candidates:
        searched.append(c)
        if os.path.exists(c):
            loaded = apply(c) or loaded
    if not loaded:
        logger.warning(f"⚠️ No env files loaded (searched: {searched})")

# Early lightweight parse of --profile (before argparse overwrite)
_profile = None
for i, tok in enumerate(sys.argv[1:]):
    if tok == '--profile' and i + 2 <= len(sys.argv[1:]):
        try:
            _profile = sys.argv[1:][i+1]
        except IndexError:
            pass
        break
_load_env_profile(_profile)

# Transient status codes to retry
TRANSIENT_STATUS = {408, 429, 500, 502, 503, 504}
logger = logging.getLogger(__name__)

# Helper for backoff delay
def _compute_backoff(attempt:int, base:float=1.0, jitter:float=0.3):
    exp = base * (2 ** (attempt-1))
    return exp + random.uniform(0, jitter*exp)

class OptimizedOneLakeMigrator:
    """High-performance OneLake migrator optimized for large file volumes."""
    
    def __init__(self, source_path: str, config: Dict[str, str], verbose: bool=False, fail_fast: bool=False, dry_run_metadata: bool=False, enable_resume_chunks: bool=False, precreate_dirs: bool=False, chunk_size_bytes: Optional[int]=None, state_dir: Optional[str]=None, profile: Optional[str]=None):
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
        self.max_workers = min(25, mp.cpu_count() * 4)
        self.chunk_size = 1000
        self.batch_size = 50

        # State directory (namespaced)
        base_state = Path(state_dir or os.environ.get("STATE_DIR", ".state"))
        prof = profile or os.environ.get("PROFILE") or "default"
        self.state_root = base_state / prof / "migrator"
        self.state_root.mkdir(parents=True, exist_ok=True)

        # Progress tracking (namespaced paths)
        self.migration_log = self.state_root / "migration_progress_optimized.json"
        self.file_cache = self.state_root / "file_cache_optimized.json"
        # Legacy fallback handling: archive instead of blind import to avoid duplicates
        legacy_progress = Path("migration_progress_optimized.json")
        legacy_cache = Path("file_cache_optimized.json")
        archive_dir = Path("_legacy_archive")
        archive_dir.mkdir(exist_ok=True)
        if legacy_progress.exists():
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            try:
                archived = archive_dir / f"migration_progress_optimized_{ts}.json"
                legacy_progress.replace(archived)
                logger.info(f"📦 Archived legacy progress to {archived}")
            except Exception as e:
                logger.warning(f"Legacy progress archive failed: {e}")
        if legacy_cache.exists():
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            try:
                archived = archive_dir / f"file_cache_optimized_{ts}.json"
                legacy_cache.replace(archived)
                logger.info(f"📦 Archived legacy cache to {archived}")
            except Exception as e:
                logger.warning(f"Legacy cache archive failed: {e}")

        # Thread safety
        self.progress_lock = Lock()

        # Retry settings
        self.retry_max_attempts = int(os.environ.get('RETRY_MAX_ATTEMPTS', '5'))
        try:
            self.retry_base_delay = float(os.environ.get('RETRY_BASE_DELAY_SECONDS', '1.0'))
        except ValueError:
            self.retry_base_delay = 1.0

        # Flags
        self.verbose = verbose
        self.fail_fast = fail_fast
        self.dry_run_metadata = dry_run_metadata
        self.enable_resume_chunks = enable_resume_chunks
        self.precreate_dirs = precreate_dirs
        self.configured_chunk_size = chunk_size_bytes

        # Endpoint
        self.one_lake_endpoint = os.environ.get("ONE_LAKE_ENDPOINT", "onelake.dfs.fabric.microsoft.com")

        # Directory cache
        self._dir_cache = set()
        self._dir_cache_file = self.state_root / "dir_cache.json"
        if self._dir_cache_file.exists():
            try:
                data = json.load(self._dir_cache_file.open())
                if isinstance(data, list):
                    self._dir_cache.update(data)
                    if self.verbose:
                        logger.info(f"📂 Loaded {len(self._dir_cache)} cached directories")
            except Exception as e:
                if self.verbose:
                    logger.warning(f"Could not load dir cache: {e}")

        # Partial upload state
        self.partial_state_file = self.state_root / "partial_uploads.json"
        self.partial_uploads = {}
        if self.enable_resume_chunks and self.partial_state_file.exists():
            try:
                self.partial_uploads = json.load(self.partial_state_file.open())
            except Exception:
                self.partial_uploads = {}
        # Legacy partial uploads
        if self.enable_resume_chunks and not self.partial_state_file.exists():
            legacy_partial = Path("partial_uploads.json")
            if legacy_partial.exists():
                try:
                    self.partial_uploads = json.load(legacy_partial.open())
                    json.dump(self.partial_uploads, self.partial_state_file.open('w'))
                    logger.info("♻️ Imported legacy partial_uploads.json into namespaced state")
                except Exception:
                    pass
    
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
    
    def get_fabric_token_with_expiry(self) -> dict:
        """Acquire token returning token and expiry epoch seconds.
        Uses existing access_token if provided without expiry metadata.
        """
        if hasattr(self, 'access_token') and self.access_token:
            # Assume long-lived or externally refreshed; set distant expiry
            return {"token": self.access_token, "expires_at": time.time() + 3600}
        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        token_data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://storage.azure.com/.default"
        }
        response = requests.post(token_url, data=token_data)
        response.raise_for_status()
        payload = response.json()
        expires_in = int(payload.get('expires_in', 3600))
        return {"token": payload['access_token'], "expires_at": time.time() + expires_in}

    def _ensure_fresh_token(self, token_state: dict, safety_margin: int = 300) -> dict:
        """Refresh token if it will expire within safety_margin seconds."""
        if time.time() >= token_state.get('expires_at', 0) - safety_margin:
            new_state = self.get_fabric_token_with_expiry()
            logger.info("🔐 Refreshed Fabric token proactively")
            return new_state
        return token_state

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
    
    async def _ensure_directories(self, session: aiohttp.ClientSession, base_headers: Dict[str,str], upload_url: str, relative_path: str):
        """Create intermediate directories required by the file path.
        upload_url points to /Files/.../file
        We iteratively create each directory with ?resource=directory.
        """
        # Extract path after workspace/lakehouse base (everything after lakehouse GUID)
        # upload_url: https://endpoint/{workspace}/{lakehouse}/Files/.../file
        parts = upload_url.split('/')
        # index: scheme(0) '', host(2) ... we rebuild easier by splitting after lakehouse id
        # Simpler: find '/Files/' substring
        try:
            idx = upload_url.index('/Files/')
        except ValueError:
            return
        path_after = upload_url[idx+1:]  # remove leading slash
        # path_after like Files/SharePoint_Invoices/demo/a.txt
        segments = path_after.split('/')
        # Exclude last (file)
        dirs = segments[:-1]
        cumulative = []
        for seg in dirs:
            cumulative.append(seg)
            dir_key = '/'.join(cumulative)
            if dir_key in self._dir_cache:
                continue
            dir_url = upload_url[:idx+1] + dir_key + '?resource=directory'
            async with session.put(dir_url, headers={**base_headers, 'Content-Length': '0'}) as resp:
                if self.verbose:
                    body = await resp.text()
                    logger.info(f"DIR {dir_key} status={resp.status} body={body[:120]}")
                if resp.status not in (200,201,409):  # 409 if already exists
                    # Stop further attempts if directory can't be created
                    return
            self._dir_cache.add(dir_key)
            # Persist incrementally (small write)
            try:
                json.dump(list(self._dir_cache), self._dir_cache_file.open('w'))
            except Exception as e:
                if self.verbose:
                    logger.warning(f"Dir cache write failed: {e}")

    async def upload_file_async(self, session: aiohttp.ClientSession, file_info: Dict, token: str) -> Dict:
        """Async file upload to OneLake with chunked streaming & optional resume."""
        source_path = file_info["path"]
        relative_path = file_info["relative_path"]
        if self.dry_run_metadata:
            return {"success": True, "file": relative_path, "size": os.path.getsize(source_path), "dry_run": True}
        base = self.onelake_base_path
        if not base.startswith('/'):
            base = '/' + base
        target_path = f"{base.rstrip('/')}/{relative_path}".replace('//','/')
        upload_url = f"https://{self.one_lake_endpoint}/{self.workspace_id}/{self.lakehouse_id}{target_path}"
        create_url = f"{upload_url}?resource=file"
        file_size = os.path.getsize(source_path)
        chunk_size = self._adaptive_chunk_size(file_size)
        attempt = 0
        resume_position = 0
        if self.enable_resume_chunks and relative_path in self.partial_uploads:
            resume_position = min(self.partial_uploads.get(relative_path, 0), file_size)
        if self.verbose:
            logger.info(f"UPLOAD URL: {upload_url} size={file_size} resume_pos={resume_position} chunk={chunk_size}")
        while True:
            attempt += 1
            try:
                now_http = formatdate(usegmt=True)
                base_headers = {
                    "Authorization": f"Bearer {token}",
                    "x-ms-version": "2023-11-03",
                    "x-ms-date": now_http
                }
                await self._ensure_directories(session, base_headers, upload_url, relative_path)
                if resume_position == 0:
                    async with session.put(create_url, headers={**base_headers, "Content-Length": "0"}) as create_resp:
                        c_body = await create_resp.text()
                        if self.verbose:
                            logger.info(f"CREATE status={create_resp.status} body={c_body[:120]}")
                        if create_resp.status in TRANSIENT_STATUS:
                            if attempt < self.retry_max_attempts:
                                delay = _compute_backoff(attempt, self.retry_base_delay)
                                logger.warning(f"Transient create {create_resp.status} {relative_path} retry {attempt} in {delay:.2f}s")
                                await asyncio.sleep(delay)
                                continue
                            return {"success": False, "file": relative_path, "step": "create", "error": f"HTTP {create_resp.status} after retries", "body": c_body[:300]}
                        if create_resp.status not in (201,200,409):
                            return {"success": False, "file": relative_path, "step": "create", "error": f"HTTP {create_resp.status}", "body": c_body[:300]}
                position = resume_position
                hasher = hashlib.sha256()
                async for position, chunk_index, data in self._stream_file_chunks(source_path, position, file_size, chunk_size):
                    hasher.update(data)
                    append_url = f"{upload_url}?action=append&position={position}"
                    headers = {**base_headers, "Content-Length": str(len(data))}
                    async with session.patch(append_url, headers=headers, data=data) as a_resp:
                        a_body = await a_resp.text()
                        if self.verbose:
                            logger.info(f"APPEND chunk={chunk_index} pos={position} size={len(data)} status={a_resp.status}")
                        if a_resp.status in TRANSIENT_STATUS:
                            if attempt < self.retry_max_attempts:
                                if self.enable_resume_chunks:
                                    self.partial_uploads[relative_path] = position
                                    json.dump(self.partial_uploads, self.partial_state_file.open('w'))
                                delay = _compute_backoff(attempt, self.retry_base_delay)
                                logger.warning(f"Transient append {a_resp.status} {relative_path} retry {attempt} in {delay:.2f}s")
                                await asyncio.sleep(delay)
                                continue
                            return {"success": False, "file": relative_path, "step": "append", "error": f"HTTP {a_resp.status} after retries", "body": a_body[:300], "position": position}
                        if a_resp.status not in (200,202):
                            if self.enable_resume_chunks:
                                self.partial_uploads[relative_path] = position
                                json.dump(self.partial_uploads, self.partial_state_file.open('w'))
                            return {"success": False, "file": relative_path, "step": "append", "error": f"HTTP {a_resp.status}", "body": a_body[:300], "position": position}
                position = file_size
                flush_url = f"{upload_url}?action=flush&position={position}&close=true"
                async with session.patch(flush_url, headers={**base_headers, "Content-Length": "0"}) as f_resp:
                    f_body = await f_resp.text()
                    if self.verbose:
                        logger.info(f"FLUSH status={f_resp.status} body={f_body[:140]}")
                    if f_resp.status in TRANSIENT_STATUS:
                        if attempt < self.retry_max_attempts:
                            if self.enable_resume_chunks:
                                self.partial_uploads[relative_path] = position
                                json.dump(self.partial_uploads, self.partial_state_file.open('w'))
                            delay = _compute_backoff(attempt, self.retry_base_delay)
                            logger.warning(f"Transient flush {f_resp.status} {relative_path} retry {attempt} in {delay:.2f}s")
                            await asyncio.sleep(delay)
                            continue
                        return {"success": False, "file": relative_path, "step": "flush", "error": f"HTTP {f_resp.status} after retries", "body": f_body[:300]}
                    if f_resp.status not in (200,201):
                        if self.enable_resume_chunks:
                            self.partial_uploads[relative_path] = position
                            json.dump(self.partial_uploads, self.partial_state_file.open('w'))
                        return {"success": False, "file": relative_path, "step": "flush", "error": f"HTTP {f_resp.status}", "body": f_body[:300]}
                if self.enable_resume_chunks and relative_path in self.partial_uploads:
                    self.partial_uploads.pop(relative_path, None)
                    try:
                        json.dump(self.partial_uploads, self.partial_state_file.open('w'))
                    except Exception:
                        pass
                file_hash = hasher.hexdigest()
                return {"success": True, "file": relative_path, "size": position, "attempts": attempt, "sha256": file_hash}
            except Exception as e:
                if attempt < self.retry_max_attempts:
                    delay = _compute_backoff(attempt, self.retry_base_delay)
                    if self.verbose:
                        logger.warning(f"Exception {relative_path}: {e} retry {attempt} in {delay:.2f}s")
                    await asyncio.sleep(delay)
                    continue
                return {"success": False, "file": relative_path, "error": str(e), "attempts": attempt}

    def _adaptive_chunk_size(self, file_size: int) -> int:
        """Determine chunk size dynamically if not explicitly configured.
        Strategy: respect explicit configured_chunk_size; else scale:
          <16MB => 4MB, <128MB => 8MB, <512MB => 16MB, else 32MB
        Allow env override CHUNK_SIZE_BYTES.
        """
        if self.configured_chunk_size:
            return self.configured_chunk_size
        env_override = os.environ.get("CHUNK_SIZE_BYTES")
        if env_override and env_override.isdigit():
            return int(env_override)
        if file_size < 16*1024*1024:
            return 4*1024*1024
        if file_size < 128*1024*1024:
            return 8*1024*1024
        if file_size < 512*1024*1024:
            return 16*1024*1024
        return 32*1024*1024

    async def _stream_file_chunks(self, path: str, start_pos: int, file_size: int, chunk_size: int):
        """Async generator yielding (position, chunk_index, data)."""
        async with aiofiles.open(path, 'rb') as f:
            if start_pos:
                await f.seek(start_pos)
            position = start_pos
            index = 0
            while position < file_size:
                data = await f.read(chunk_size)
                if not data:
                    break
                yield position, index, data
                position += len(data)
                index += 1

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
    def migrate_files_optimized(self, resume: bool = True, limit: int | None = None, reset_progress: bool = False) -> Dict[str, Any]:
        """Optimized migration with parallel uploads.
        Limit semantics (Sept 2025): limit caps *new successful uploads* this run.
        Returns stats dict (progress['stats']).
        """
        # Handle reset
        if reset_progress:
            for p in (self.migration_log, self.file_cache):
                if p.exists():
                    try:
                        p.unlink()
                    except Exception:
                        pass
            resume = False
            logger.info("🧹 Progress reset requested; starting fresh")
        logger.info("🚀 Starting optimized OneLake migration...")
        progress = self.load_progress() if resume else self.init_progress()
        files = self.scan_files_optimized()
        # Deduplicate completed entries in progress
        if progress.get("completed_files"):
            seen_cf: set[str] = set()
            deduped_cf: list[Any] = []
            for entry in progress["completed_files"]:
                name = entry.get("file") if isinstance(entry, dict) else entry
                if not name:
                    continue
                if name in seen_cf:
                    continue
                seen_cf.add(name)
                deduped_cf.append(entry)
            if len(deduped_cf) != len(progress["completed_files"]):
                logger.info(f"🧹 Deduplicated completed_files: {len(progress['completed_files'])} -> {len(deduped_cf)}")
                progress["completed_files"] = deduped_cf
        # Orphan pruning (remove entries for files no longer present in scan)
        canonical_set = {f["relative_path"] for f in files}
        if progress.get("completed_files"):
            pruned_list: list[Any] = []
            removed_orphans = 0
            for entry in progress["completed_files"]:
                name = entry.get("file") if isinstance(entry, dict) else entry
                if name in canonical_set:
                    pruned_list.append(entry)
                else:
                    removed_orphans += 1
            if removed_orphans:
                logger.info(f"🧽 Orphan pruning: removed {removed_orphans} entries not found in current scan")
                progress["completed_files"] = pruned_list
        if limit is not None:
            logger.info(f"🔒 Will stop after {limit} new successful uploads")
        # Build processed set
        processed_files: set[str] = set()
        for entry in progress.get("completed_files", []):
            if isinstance(entry, dict):
                name = entry.get("file") or entry.get("path") or entry.get("relative_path")
                if name:
                    processed_files.add(name)
            else:
                processed_files.add(entry)
        remaining_files = [f for f in files if f["relative_path"] not in processed_files]
        stats_existing = progress.get("stats", {})
        # Exclude meta/support files (cache listings, run summaries, progress artifacts) from migration stats
        EXCLUDE_SUFFIXES = {
            "file_list_cache.json",
            "last_run_summary.json",
            "migration_progress_optimized.json",
            "download_progress_turbo.json"
        }
        canonical_files = [
            f for f in files
            if not any(f["relative_path"].endswith(suf) for suf in EXCLUDE_SUFFIXES)
        ]
        base_stats = {
            "start_time": stats_existing.get("start_time", datetime.now().isoformat()),
            "total_files": len(canonical_files),
            "processed_files": stats_existing.get("processed_files", len(processed_files)),
            "successful_uploads": min(len(processed_files), len(canonical_files)),
            "failed_uploads": stats_existing.get("failed_uploads", 0),
            "batches_completed": stats_existing.get("batches_completed", 0),
            "avg_upload_speed": stats_existing.get("avg_upload_speed", 0),
            "uploaded_bytes": min(stats_existing.get("uploaded_bytes", 0), stats_existing.get("total_bytes", 10**18)),
            "total_bytes": sum(f["size_bytes"] for f in canonical_files),
            "successful_this_run": 0
        }
        logger.info(f"📊 Migration status: {len(processed_files):,} completed, {len(remaining_files):,} remaining")
        def _finalize_and_prune(stats_dict: dict):
            """Apply meta/support file pruning & clamp stats before returning."""
            EXCLUDE_SUFFIXES_LOCAL = {
                "file_list_cache.json",
                "last_run_summary.json",
                "migration_progress_optimized.json",
                "download_progress_turbo.json"
            }
            if progress.get("completed_files"):
                filtered_local = []
                for entry in progress["completed_files"]:
                    name = entry.get("file") if isinstance(entry, dict) else entry
                    if name and any(name.endswith(suf) for suf in EXCLUDE_SUFFIXES_LOCAL):
                        continue
                    filtered_local.append(entry)
                if len(filtered_local) != len(progress["completed_files"]):
                    logger.info(f"🧹 Early/Final meta-file pruning: {len(progress['completed_files'])} -> {len(filtered_local)}")
                    progress["completed_files"] = filtered_local
                    stats_dict["successful_uploads"] = min(len(filtered_local), stats_dict.get("total_files", len(filtered_local)))
            # Clamp invariants
            if stats_dict.get("successful_uploads",0) > stats_dict.get("total_files",0):
                stats_dict["successful_uploads"] = stats_dict.get("total_files",0)
            if stats_dict.get("uploaded_bytes",0) > stats_dict.get("total_bytes",0):
                stats_dict["uploaded_bytes"] = stats_dict.get("total_bytes",0)
            # Clamp successful_this_run to never exceed successful_uploads or total_files
            if stats_dict.get("successful_this_run",0) > stats_dict.get("successful_uploads",0):
                stats_dict["successful_this_run"] = min(stats_dict.get("successful_uploads",0), stats_dict.get("total_files",0))
            if stats_dict.get("successful_this_run",0) > stats_dict.get("total_files",0):
                stats_dict["successful_this_run"] = stats_dict.get("total_files",0)
            # Normalize processed_files & total_files after pruning for consistency
            try:
                completed_len = len(progress.get("completed_files", []))
                # Preserve original value for audit if it differs
                if "original_processed_files" not in stats_dict and stats_dict.get("processed_files") not in (None, completed_len):
                    stats_dict["original_processed_files"] = stats_dict.get("processed_files")
                stats_dict["processed_files"] = completed_len
                # total_files should reflect canonical pruned universe
                stats_dict["total_files"] = max(stats_dict.get("total_files", completed_len), completed_len)
                # successful_uploads cannot exceed processed_files/total_files
                stats_dict["successful_uploads"] = min(stats_dict.get("successful_uploads", completed_len), completed_len, stats_dict.get("total_files", completed_len))
            except Exception as e:
                logger.warning(f"Normalization step failed: {e}")
            stats_dict.setdefault("end_time", datetime.now().isoformat())
            progress["stats"] = stats_dict
            self.save_progress(progress)
            return stats_dict

        if not remaining_files or (limit == 0):
            logger.info("✅ Nothing to do (all files migrated or limit=0)")
            return _finalize_and_prune(base_stats)
        # Working stats copy
        stats = base_stats.copy()
        failure_samples: list[dict] = []
        new_successes_this_run = 0
        # Optional directory pre-create
        token_state = self.get_fabric_token_with_expiry()
        if self.precreate_dirs and remaining_files:
            try:
                token_state = self._ensure_fresh_token(token_state)
                token = token_state['token']
                now_http = formatdate(usegmt=True)
                base_headers = {"Authorization": f"Bearer {token}", "x-ms-version": "2023-11-03", "x-ms-date": now_http}
                async def precreate():
                    connector = aiohttp.TCPConnector(limit=50, limit_per_host=25)
                    async with aiohttp.ClientSession(connector=connector) as session:
                        tasks = []
                        seen_dirs: set[str] = set()
                        for fobj in remaining_files:
                            rel = fobj["relative_path"]
                            basep = self.onelake_base_path if self.onelake_base_path.startswith('/') else '/' + self.onelake_base_path
                            target_path = f"{basep.rstrip('/')}/{rel}".replace('//','/')
                            upload_url = f"https://{self.one_lake_endpoint}/{self.workspace_id}/{self.lakehouse_id}{target_path}"
                            dir_key = str(Path(rel).parent)
                            if dir_key in seen_dirs:
                                continue
                            seen_dirs.add(dir_key)
                            tasks.append(self._ensure_directories(session, base_headers, upload_url, rel))
                        if tasks:
                            await asyncio.gather(*tasks)
                asyncio.run(precreate())
                logger.info("📂 Pre-created directory structure")
            except Exception as e:
                logger.warning(f"Pre-create directories skipped: {e}")
        # Batching
        batches = [remaining_files[i:i + self.batch_size] for i in range(0, len(remaining_files), self.batch_size)]
        for batch_idx, batch in enumerate(batches):
            batch_start = time.time()
            token_state = self._ensure_fresh_token(token_state)
            token = token_state['token']
            logger.info(f"📦 Batch {batch_idx+1}/{len(batches)} ({len(batch)} files)")
            try:
                results = asyncio.run(self.migrate_batch_async(batch, token))
            except Exception as e:
                logger.error(f"❌ Batch {batch_idx+1} failed: {e}")
                continue
            batch_success = 0
            batch_failed = 0
            for result in results:
                if result.get("success"):
                    with self.progress_lock:
                        if "sha256" in result:
                            progress["completed_files"].append({"file": result["file"], "sha256": result["sha256"], "size": result.get("size")})
                        else:
                            progress["completed_files"].append(result["file"])
                    batch_success += 1
                    if limit is None or new_successes_this_run < limit:
                        new_successes_this_run += 1
                    if limit is not None and new_successes_this_run >= limit:
                        logger.info(f"🛑 Limit reached after {new_successes_this_run} new uploads – stopping")
                        stats["processed_files"] += (batch_success + batch_failed)
                        stats["successful_uploads"] = len(progress["completed_files"])
                        stats["successful_this_run"] = new_successes_this_run
                        stats["failed_uploads"] += batch_failed
                        stats["uploaded_bytes"] += sum(r.get("size",0) for r in results if r.get("success"))
                        stats["batches_completed"] += 1
                        batch_time = time.time() - batch_start
                        batch_speed = batch_success / batch_time if batch_time > 0 else 0
                        prev_weight = batch_idx
                        stats["avg_upload_speed"] = (stats["avg_upload_speed"] * prev_weight + batch_speed)/(prev_weight+1)
                        stats["end_time"] = datetime.now().isoformat()
                        # Early clamp before saving when limit hit
                        if stats.get("successful_this_run",0) > stats.get("successful_uploads",0):
                            stats["successful_this_run"] = min(stats.get("successful_uploads",0), stats.get("total_files",0))
                        if stats.get("successful_this_run",0) > stats.get("total_files",0):
                            stats["successful_this_run"] = stats.get("total_files",0)
                        progress["stats"] = stats
                        self.save_progress(progress)
                        return stats
                else:
                    failure_entry = {"file": result.get("file","unknown"), "step": result.get("step"), "error": result.get("error"), "body": result.get("body","")[:200]}
                    failure_samples.append(failure_entry)
                    with self.progress_lock:
                        progress["failed_files"].append({
                            "file": failure_entry["file"],
                            "error": failure_entry["error"],
                            "step": failure_entry.get("step"),
                            "body": failure_entry.get("body"),
                            "timestamp": datetime.now().isoformat()
                        })
                    if self.verbose:
                        logger.error(f"FAIL {failure_entry['file']} step={failure_entry['step']} err={failure_entry['error']} body={failure_entry['body']}")
                    if self.fail_fast:
                        logger.error("⛔ Fail-fast engaged; aborting")
                        stats["end_time"] = datetime.now().isoformat()
                        progress["stats"] = stats
                        self.save_progress(progress)
                        return stats
                    batch_failed += 1
            # Update stats after batch
            stats["processed_files"] += (batch_success + batch_failed)
            stats["successful_uploads"] = min(len([c for c in progress["completed_files"] if isinstance(c, dict) or isinstance(c, str)]), stats["total_files"])  # clamp
            stats["successful_this_run"] = new_successes_this_run
            stats["failed_uploads"] += batch_failed
            stats["uploaded_bytes"] = min(stats["uploaded_bytes"] + sum(r.get("size",0) for r in results if r.get("success")), stats["total_bytes"])  # clamp
            stats["batches_completed"] += 1
            batch_time = time.time() - batch_start
            batch_speed = batch_success / batch_time if batch_time > 0 else 0
            prev_weight = batch_idx
            stats["avg_upload_speed"] = (stats["avg_upload_speed"] * prev_weight + batch_speed)/(prev_weight+1)
            if batch_idx % 10 == 0:
                progress["stats"] = stats
                self.save_progress(progress)
        stats["end_time"] = datetime.now().isoformat()
        # Guard: ensure consistency
        if stats.get("successful_uploads",0) > stats.get("total_files",0):
            stats["successful_uploads"] = stats.get("total_files",0)
        if stats.get("uploaded_bytes",0) > stats.get("total_bytes",0):
            stats["uploaded_bytes"] = stats.get("total_bytes",0)
        # Apply finalization & pruning
        stats = _finalize_and_prune(stats)
        logger.info("✅ Optimized migration completed!")
        logger.info(f"📊 Results: {stats['successful_uploads']:,}/{stats['total_files']:,} files migrated")
        if failure_samples:
            logger.error(f"❌ Failure summary (up to 5 of {len(failure_samples)}):")
            for entry in failure_samples[:5]:
                logger.error(f" - {entry['file']} step={entry.get('step')} err={entry.get('error')} body={entry.get('body')}")
        if self.dry_run_metadata:
            logger.info("📝 Dry-run metadata mode: no uploads were performed.")
        return stats
    
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
                    data = json.load(f)
                    meta = data.get("metadata", {})
                    stored_hash = meta.get("context_hash")
                    if stored_hash:
                        import hashlib as _hl
                        ctx = f"{self.workspace_id}|{self.lakehouse_id}|{self.onelake_base_path}"
                        expected = _hl.sha256(ctx.encode()).hexdigest()[:16]
                        if expected != stored_hash:
                            logger.warning("⚠️ Migration progress context hash mismatch; starting fresh state")
                            return self.init_progress()
                    return data
            except:
                pass
        return self.init_progress()
    
    def save_progress(self, progress: Dict):
        """Save migration progress."""
        # Inject metadata/context hash once per save
        meta = progress.setdefault("metadata", {})
        meta.setdefault("profile", os.environ.get("PROFILE") or "default")
        meta.setdefault("workspace_id", self.workspace_id)
        meta.setdefault("lakehouse_id", self.lakehouse_id)
        meta.setdefault("onelake_base_path", self.onelake_base_path)
        meta.setdefault("schema_version", 1)
        if "generated_at" not in meta:
            meta["generated_at"] = datetime.utcnow().isoformat() + "Z"
        # Context hash for invalidation
        import hashlib as _hl
        ctx = f"{self.workspace_id}|{self.lakehouse_id}|{self.onelake_base_path}"
        meta["context_hash"] = _hl.sha256(ctx.encode()).hexdigest()[:16]
        # File locking (simple lock file strategy)
        lock_path = Path(str(self.migration_log) + ".lock")
        start = time.time()
        while True:
            try:
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                break
            except FileExistsError:
                if time.time() - start > 10:  # 10s timeout
                    logger.warning("⚠️ Timeout acquiring progress file lock; writing without lock")
                    break
                time.sleep(0.05)
        try:
            with open(self.migration_log, 'w') as f:
                json.dump(progress, f, indent=2)
        finally:
            try:
                if lock_path.exists():
                    lock_path.unlink()
            except Exception:
                pass

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
    parser = argparse.ArgumentParser(description="FIXED Optimized Microsoft Fabric OneLake Migration Tool")
    parser.add_argument("--source", default="C:/commercial_pdfs/downloaded_files", help="Source directory with downloaded files")
    parser.add_argument("--resume", action="store_true", default=True, help="Resume previous migration")
    parser.add_argument("--workers", type=int, default=25, help="Number of parallel workers")
    parser.add_argument("--limit", type=int, default=None, help="Upload at most N NEW files this run (smoke test)")
    parser.add_argument("--reset-progress", action="store_true", help="Ignore and delete existing progress & cache for a clean run")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose error output")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on first failure")
    parser.add_argument("--dry-run-metadata", action="store_true", help="Scan & report file metadata only (no uploads)")
    parser.add_argument("--enable-resume-chunks", action="store_true", help="Enable resumable chunked uploads")
    parser.add_argument("--precreate-dirs", action="store_true", help="Pre-scan and create directory tree before uploads")
    parser.add_argument("--chunk-size-bytes", type=int, default=None, help="Override chunk size for streaming uploads (default 8MB)")
    parser.add_argument("--profile", help="Profile name: loads config/profiles/<profile>.env before default .env")
    parser.add_argument("--state-dir", default=os.environ.get("STATE_DIR", ".state"), help="Base state directory (.state by default) for namespaced progress & caches")
    parser.add_argument("--validate-config", action="store_true", help="Validate required Fabric configuration & connectivity then exit")
    args = parser.parse_args()
    # If user passed --profile through argparse (not just early), we ensure any missing vars can load (idempotent)
    if args.profile and args.profile != _profile:
        _load_env_profile(args.profile)
    config = load_fabric_config()
    required_fields = ["tenant_id", "client_id", "client_secret", "fabric_workspace_id", "fabric_lakehouse_id"]
    missing = [field for field in required_fields if not config.get(field)]
    if missing:
        logger.error(f"❌ Missing configuration: {missing}")
        logger.error("💡 Make sure your .env file contains all required Fabric settings")
        if args.validate_config:
            sys.exit(1)
        return
    if args.validate_config:
        # Lightweight token acquisition check
        try:
            token_state = OptimizedOneLakeMigrator(".", config, state_dir=args.state_dir, profile=args.profile or _profile).get_fabric_token_with_expiry()
            if token_state.get("token"):
                print("✅ Migrator configuration valid (token acquired)")
                sys.exit(0)
        except Exception as e:
            logger.error(f"❌ Validation failed: {e}")
            sys.exit(2)
    migrator = OptimizedOneLakeMigrator(
        args.source,
        config,
        verbose=args.verbose,
        fail_fast=args.fail_fast,
        dry_run_metadata=args.dry_run_metadata,
        enable_resume_chunks=args.enable_resume_chunks,
        precreate_dirs=args.precreate_dirs,
        chunk_size_bytes=args.chunk_size_bytes,
        state_dir=args.state_dir,
        profile=args.profile or _profile,
    )
    migrator.max_workers = args.workers
    logger.info(f"🚀 Starting FIXED optimized migration with {args.workers} workers")
    results = migrator.migrate_files_optimized(args.resume, limit=args.limit, reset_progress=args.reset_progress)
    print("\n✅ FIXED OPTIMIZED MIGRATION COMPLETE")
    print("=" * 50)
    print(f"📊 Files Processed: {results.get('processed_files', 0):,}")
    print(f"✅ Successful: {results.get('successful_uploads', 0):,}")
    print(f"❌ Failed: {results.get('failed_uploads', 0):,}")
    total_bytes = results.get('uploaded_bytes', 0)
    total_time = 0
    if results.get('end_time') and results.get('start_time'):
        try:
            total_time = (datetime.fromisoformat(results['end_time']) - datetime.fromisoformat(results['start_time'])).total_seconds()
        except Exception:
            total_time = 0
    mb_sec = (total_bytes/1_048_576)/(total_time or 1)
    print(f"⚡ Average Speed: {results.get('avg_upload_speed', 0):.1f} files/sec | {mb_sec:.2f} MB/sec")
    if 'uploaded_bytes' in results:
        print(f"📦 Data Uploaded: {total_bytes/1_048_576:.2f} MB of {results.get('total_bytes',0)/1_048_576:.2f} MB")

if __name__ == "__main__":
    main()
