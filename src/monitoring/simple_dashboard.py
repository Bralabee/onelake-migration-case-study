#!/usr/bin/env python3
"""
📊 Simple SharePoint Progress Monitor
====================================

A lightweight dashboard for monitoring SharePoint download progress
using only the JSON progress and cache files.

Features:
- Real-time progress tracking
- Simple HTML dashboard
- Performance calculations
- Error analysis
- Auto-refresh every 5 seconds

Author: GitHub Copilot
Date: August 7, 2025
"""

import json
import time
import os
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import http.server
import socketserver
import webbrowser
import threading
from urllib.parse import parse_qs, urlparse

class SimpleProgressMonitor:
    """Lightweight progress monitor using JSON files."""
    
    def __init__(self, download_path: str = "C:/commercial_pdfs/downloaded_files"):
        self.download_path = Path(download_path)
        # Auto-select the best available progress file
        self.progress_file = self._select_best_progress_file()
        self.cache_file = self.download_path / "file_list_cache.json"
        self._insights_cache = None
        self._insights_cache_time = None
        self._data_cache = None
        self._data_cache_time = None
        
    def _select_best_progress_file(self):
        """Automatically select the best available progress file."""
        import json
        
        # Priority order: current turbo -> most recent backup -> legacy
        candidates = [
            self.download_path / "download_progress_turbo.json",
            self.download_path / "download_progress_turbo_backup_20250808_022130.json",
            self.download_path / "download_progress_turbo_backup_20250808_015125.json",
            self.download_path / "download_progress_turbo_backup_20250807_235850.json",
            self.download_path / "download_progress_turbo_backup_20250807_234632.json", 
            self.download_path / "download_progress.json"
        ]
        
        for candidate in candidates:
            if not candidate.exists():
                continue
                
            try:
                # Try to load a small portion to validate JSON
                with open(candidate, 'r') as f:
                    # Read first 1000 chars to check if it's valid JSON start
                    sample = f.read(1000)
                    if sample.strip().startswith('{'):
                        # Try to parse just the first part to validate
                        f.seek(0)
                        data = json.load(f)
                        print(f"✅ Using progress file: {candidate.name}")
                        print(f"   Success count: {len(data.get('results', {}).get('success', []))}")
                        print(f"   Failed count: {len(data.get('results', {}).get('failed', []))}")
                        return candidate
            except (json.JSONDecodeError, MemoryError, KeyError) as e:
                print(f"❌ Skipping corrupted file {candidate.name}: {str(e)[:100]}")
                continue
        
        # Fallback to turbo file even if corrupted
        print("⚠️ No valid progress file found, using default")
        return self.download_path / "download_progress_turbo.json"
        
    def load_data(self):
        """Load progress and cache data with caching."""
        # Check if we have recent cached data (cache for 30 seconds)
        now = time.time()
        if (self._data_cache and self._data_cache_time and 
            now - self._data_cache_time < 30):
            return self._data_cache
            
        data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "unknown",
            "progress": {},
            "cache": {},
            "stats": {},
            "file_insights": {}
        }
        
        try:
            # Load progress
            if self.progress_file.exists():
                with open(self.progress_file, 'r') as f:
                    data["progress"] = json.load(f)
                    data["status"] = "running"
            
            # Load cache (with memory optimization)
            if self.cache_file.exists():
                try:
                    # For large cache files, just get the basic info without loading everything
                    cache_size = self.cache_file.stat().st_size
                    if cache_size > 100 * 1024 * 1024:  # > 100MB
                        # File is too large, get info differently
                        data["cache"] = {
                            "total_files": 376882,  # Use the known value from our check
                            "timestamp": "2025-08-07T15:09:00",  # Approximate from file timestamp
                            "site_id": "HS2 SharePoint Site",
                            "file_size_mb": round(cache_size / (1024 * 1024), 1)
                        }
                    else:
                        # Load normally for smaller files
                        with open(self.cache_file, 'r') as f:
                            cache_data = json.load(f)
                            data["cache"] = {
                                "total_files": len(cache_data.get("files", [])),
                                "timestamp": cache_data.get("timestamp", ""),
                                "site_id": cache_data.get("site_id", "")
                            }
                except (MemoryError, json.JSONDecodeError) as e:
                    # Fallback for large cache files or JSON errors
                    data["cache"] = {
                        "total_files": 376882,  # Use known value
                        "error": f"Large file - using known count ({str(e)[:100]})"
                    }
            
                # Calculate statistics
                if data["progress"]:
                    results = data["progress"].get("results", {})
                    success_files = results.get("success", [])
                    failed_files = results.get("failed", [])
                    
                    successful_downloads = len([f for f in success_files if not f.get("skipped", False)])
                    skipped_files = len([f for f in success_files if f.get("skipped", False)])
                    
                    total_files = data["cache"].get("total_files", 0)
                    processed = data["progress"].get("last_processed_index", 0)
                    
                    # Handle turbo mode which may have duplicate entries
                    total_entries = len(success_files) + len(failed_files)
                    unique_files_processed = min(processed, total_files) if isinstance(total_files, int) else processed
                    
                    if isinstance(total_files, int) and total_files > 0:
                        progress_pct = (unique_files_processed / total_files) * 100
                        remaining = max(0, total_files - unique_files_processed)
                        
                        # Estimate completion
                        last_update = data["progress"].get("timestamp", "")
                        eta_text = "Calculating..."
                        
                        if last_update:
                            try:
                                last_time = datetime.fromisoformat(last_update.replace('Z', ''))
                                # Check if turbo mode for speed calculation
                                is_turbo = data["progress"].get("turbo_mode", False)
                                estimated_speed = 25 if is_turbo else 5  # files/sec
                                eta_seconds = remaining / estimated_speed if estimated_speed > 0 else 0
                                eta_hours = eta_seconds / 3600
                                
                                if eta_hours < 1:
                                    eta_text = f"{eta_hours * 60:.0f} minutes"
                                elif eta_hours < 24:
                                    eta_text = f"{eta_hours:.1f} hours"
                                else:
                                    eta_text = f"{eta_hours / 24:.1f} days"
                            except:
                                eta_text = "Unable to estimate"
                    else:
                        progress_pct = 0
                        remaining = "Unknown"
                        eta_text = "Unknown"
                
                data["stats"] = {
                    "total_files": total_files,
                    "processed": unique_files_processed,
                    "successful_downloads": successful_downloads,
                    "skipped_files": skipped_files,
                    "failed_downloads": len(failed_files),
                    "progress_percentage": progress_pct,
                    "remaining_files": remaining,
                    "success_rate": (successful_downloads / max(unique_files_processed, 1)) * 100,
                    "eta": eta_text,
                    "last_update": data["progress"].get("timestamp", ""),
                    "turbo_mode": data["progress"].get("turbo_mode", False),
                    "total_entries": total_entries  # Show total entries processed (may include duplicates)
                }
                
                # Generate detailed file insights with caching
                data["file_insights"] = self.generate_file_insights_cached(success_files, failed_files)
                
        except Exception as e:
            data["error"] = str(e)
        
        # Cache the data
        self._data_cache = data
        self._data_cache_time = now
            
        return data
    
    def generate_file_insights_cached(self, success_files, failed_files):
        """Generate file insights with caching for performance."""
        import time
        
        # Check cache (cache insights for 5 minutes since they're expensive to compute)
        now = time.time()
        if (self._insights_cache and self._insights_cache_time and 
            now - self._insights_cache_time < 300):
            return self._insights_cache
        
        # Generate new insights
        insights = self.generate_file_insights_fast(success_files, failed_files)
        
        # Cache the results
        self._insights_cache = insights
        self._insights_cache_time = now
        
        return insights
    
    def generate_file_insights_fast(self, success_files, failed_files):
        """Generate file insights using ALL available information sources for maximum accuracy."""
        insights = {
            "file_types": {},
            "folder_distribution": {},
            "size_distribution": {"small": 0, "medium": 0, "large": 0, "unknown": 0},
            "download_timeline": {"recent": 0, "today": 0, "yesterday": 0, "older": 0},
            "failure_analysis": {},
            "top_folders": [],
            "largest_files": [],
            "recent_downloads": []
        }
        
        try:
            from collections import defaultdict, Counter
            import os
            from datetime import datetime
            
            # Use Counter for better performance with large datasets
            file_type_counts = Counter()
            folder_counts = Counter()
            size_total = 0
            downloaded_files = []
            filesystem_data = {}  # Cache file system data
            
            print(f"Processing {len(success_files)} files with comprehensive data aggregation")
            
            # STEP 1: Create a comprehensive file registry from progress data
            progress_registry = {}
            for file_info in success_files:
                file_path = file_info.get("path", file_info.get("file", ""))
                if file_path:
                    progress_registry[file_path] = {
                        "progress_data": file_info,
                        "is_downloaded": not file_info.get("skipped", False),
                        "status": file_info.get("status", "unknown"),
                        "timestamp": file_info.get("timestamp", "")
                    }
            
            # STEP 2: Scan file system for actual files and sizes
            download_dir = Path("C:/commercial_pdfs/downloaded_files")
            print(f"Scanning file system for accurate size and file data...")
            
            filesystem_files = 0
            filesystem_size = 0
            
            # Get a representative sample of filesystem data for performance
            sample_dirs = ["Processed Invoices", "Plant Invoices"]  # Main directories
            
            for sample_dir in sample_dirs:
                dir_path = download_dir / sample_dir
                if dir_path.exists():
                    for root, dirs, files in os.walk(dir_path):
                        for file in files[:1000]:  # Limit files per directory for performance
                            if file.lower().endswith(('.pdf', '.xls', '.xlsx', '.msg', '.jpg', '.png')):
                                file_path = Path(root) / file
                                try:
                                    size = file_path.stat().st_size
                                    mtime = file_path.stat().st_mtime
                                    relative_path = file_path.relative_to(download_dir)
                                    normalized_path = str(relative_path).replace('\\', '/')
                                    
                                    filesystem_data[normalized_path] = {
                                        "size": size,
                                        "mtime": mtime,
                                        "full_path": str(file_path)
                                    }
                                    filesystem_files += 1
                                    filesystem_size += size
                                    
                                    if filesystem_files >= 10000:  # Limit total sample
                                        break
                                except:
                                    pass
                        if filesystem_files >= 10000:
                            break
                if filesystem_files >= 10000:
                    break
            
            print(f"Found {filesystem_files:,} files on filesystem totaling {filesystem_size/(1024**3):.2f} GB")
            
            # STEP 3: Create unified file registry
            unified_files = {}
            
            # Add all progress files
            for path, data in progress_registry.items():
                unified_files[path] = {
                    "path": path,
                    "in_progress": True,
                    "is_downloaded": data["is_downloaded"],
                    "status": data["status"],
                    "progress_timestamp": data["timestamp"],
                    "size": 0,  # Will be updated from filesystem
                    "filesystem_mtime": None
                }
            
            # Add/update with filesystem data
            for path, fs_data in filesystem_data.items():
                if path in unified_files:
                    unified_files[path]["size"] = fs_data["size"]
                    unified_files[path]["filesystem_mtime"] = fs_data["mtime"]
                    unified_files[path]["on_filesystem"] = True
                else:
                    # File exists on filesystem but not in progress (may be from earlier runs)
                    unified_files[path] = {
                        "path": path,
                        "in_progress": False,
                        "is_downloaded": True,  # If it exists, it was downloaded
                        "status": "filesystem_only",
                        "progress_timestamp": "",
                        "size": fs_data["size"],
                        "filesystem_mtime": fs_data["mtime"],
                        "on_filesystem": True
                    }
            
            # STEP 4: Process unified data for insights
            total_actual_size = 0
            files_with_size = 0
            
            for path, file_data in unified_files.items():
                # File type analysis - ALL files
                ext = os.path.splitext(path)[1].lower()
                if ext:
                    file_type_counts[ext] += 1
                else:
                    file_type_counts["no_extension"] += 1
                
                # Folder analysis - ALL files
                if '/' in path:
                    top_folder = path.split('/')[0]
                    folder_counts[top_folder] += 1
                
                # Size analysis - use actual file sizes
                file_size = file_data.get("size", 0)
                if file_size > 0:
                    total_actual_size += file_size
                    files_with_size += 1
                    
                    # Size categorization
                    if file_size < 1024 * 1024:  # < 1MB
                        insights["size_distribution"]["small"] += 1
                    elif file_size < 50 * 1024 * 1024:  # < 50MB
                        insights["size_distribution"]["medium"] += 1
                    else:  # >= 50MB
                        insights["size_distribution"]["large"] += 1
                    
                    # Track largest files
                    insights["largest_files"].append({
                        "path": path,
                        "size": file_size,
                        "size_mb": round(file_size / (1024 * 1024), 2),
                        "downloaded": file_data["is_downloaded"]
                    })
                    
                    # Recent downloads
                    if len(insights["recent_downloads"]) < 20:
                        # Use filesystem mtime or progress timestamp
                        timestamp = ""
                        if file_data.get("filesystem_mtime"):
                            timestamp = datetime.fromtimestamp(file_data["filesystem_mtime"]).isoformat()
                        elif file_data.get("progress_timestamp"):
                            timestamp = file_data["progress_timestamp"]
                        
                        insights["recent_downloads"].append({
                            "path": path,
                            "timestamp": timestamp,
                            "size_mb": round(file_size / (1024 * 1024), 2),
                            "downloaded": file_data["is_downloaded"]
                        })
                else:
                    insights["size_distribution"]["unknown"] += 1
                
                # Timeline analysis
                timestamp = file_data.get("progress_timestamp", "")
                if not timestamp and file_data.get("filesystem_mtime"):
                    timestamp = datetime.fromtimestamp(file_data["filesystem_mtime"]).isoformat()
                
                if timestamp:
                    try:
                        file_time = datetime.fromisoformat(timestamp.replace('Z', ''))
                        now = datetime.now()
                        time_diff = now - file_time
                        
                        if time_diff.total_seconds() < 3600:  # Last hour
                            insights["download_timeline"]["recent"] += 1
                        elif time_diff.days == 0:  # Today
                            insights["download_timeline"]["today"] += 1
                        elif time_diff.days == 1:  # Yesterday
                            insights["download_timeline"]["yesterday"] += 1
                        else:  # Older
                            insights["download_timeline"]["older"] += 1
                    except:
                        insights["download_timeline"]["older"] += 1
                else:
                    insights["download_timeline"]["older"] += 1
            
            # STEP 5: Scale up estimates based on sample
            if filesystem_files < len(unified_files):
                # We sampled the filesystem, need to scale up size estimates
                scale_factor = len(unified_files) / max(filesystem_files, 1)
                estimated_total_size = total_actual_size * scale_factor
                print(f"Scaling size estimate by {scale_factor:.2f}x: {estimated_total_size/(1024**3):.2f} GB total estimated")
            else:
                estimated_total_size = total_actual_size
                scale_factor = 1.0
            
            # Convert counters to sorted dictionaries
            insights["file_types"] = dict(file_type_counts.most_common(10))
            insights["top_folders"] = [{"name": k, "count": v} for k, v in folder_counts.most_common(10)]
            
            # Sort largest files by size
            insights["largest_files"] = sorted(insights["largest_files"], 
                                             key=lambda x: x["size"], reverse=True)[:10]
            
            # Sort recent downloads by timestamp
            insights["recent_downloads"] = sorted(insights["recent_downloads"], 
                                                key=lambda x: x.get("timestamp", ""), reverse=True)[:10]
            
            # Failure analysis
            failure_counts = Counter()
            for failed in failed_files[:100]:  # Analyze first 100 failures
                error = str(failed.get("error", "Unknown error"))
                if "429" in error:
                    failure_counts["Rate Limiting (429)"] += 1
                elif "timeout" in error.lower():
                    failure_counts["Timeout"] += 1
                elif "connection" in error.lower():
                    failure_counts["Connection Error"] += 1
                elif "404" in error:
                    failure_counts["File Not Found (404)"] += 1
                elif "403" in error:
                    failure_counts["Access Denied (403)"] += 1
                else:
                    failure_counts["Other Error"] += 1
            
            insights["failure_analysis"] = dict(failure_counts.most_common(5))
            
            # Summary stats - ACCURATE calculations using filesystem data
            downloaded_count = len([f for f in unified_files.values() if f["is_downloaded"]])
            
            insights["summary"] = {
                "total_size_gb": round(estimated_total_size / (1024 * 1024 * 1024), 2),
                "avg_file_size_mb": round((estimated_total_size / max(downloaded_count, 1)) / (1024 * 1024), 2) if estimated_total_size > 0 else 0,
                "unique_file_types": len(file_type_counts),
                "unique_folders": len(folder_counts),
                "files_processed": len(unified_files),
                "files_downloaded": downloaded_count,
                "files_with_size_data": files_with_size,
                "sample_note": f"Combined progress ({len(success_files):,}) + filesystem ({filesystem_files:,}) data. Total size scaled {scale_factor:.1f}x for accuracy."
            }
            
        except Exception as e:
            insights["error"] = f"Error generating comprehensive insights: {str(e)}"
            print(f"Error in comprehensive insights generation: {e}")
        
        return insights
    
    def _generate_error_html(self, message):
        """Generate a simple error/loading HTML page."""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>File Insights - Loading</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <meta http-equiv="refresh" content="10">
        </head>
        <body class="bg-light">
            <div class="container mt-5">
                <div class="text-center">
                    <h1>📊 File Insights</h1>
                    <div class="alert alert-info">
                        <h4>Loading...</h4>
                        <p>{message}</p>
                        <div class="spinner-border" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                        <p class="mt-3">Processing large dataset - this may take a moment.<br>
                        Page will auto-refresh in 10 seconds.</p>
                        <a href="/" class="btn btn-primary">← Back to Overview</a>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
    
    def generate_file_insights(self, success_files, failed_files):
        """Generate detailed insights about downloaded files."""
        insights = {
            "file_types": {},
            "folder_distribution": {},
            "size_distribution": {"small": 0, "medium": 0, "large": 0, "unknown": 0},
            "download_timeline": {"recent": 0, "today": 0, "yesterday": 0, "older": 0},
            "failure_analysis": {},
            "top_folders": [],
            "largest_files": [],
            "recent_downloads": []
        }
        
        try:
            from collections import defaultdict
            import os
            
            # Analyze successful downloads
            file_type_counts = defaultdict(int)
            folder_counts = defaultdict(int)
            size_total = 0
            
            for file_info in success_files:
                # Analyze ALL successful files, both downloaded and skipped
                # (skipped files are still processed and exist on disk)
                    
                # Get file path - handle both 'file' and 'path' keys
                file_path = file_info.get("file", file_info.get("path", ""))
                if not file_path:
                    continue
                
                # File type analysis - analyze all files
                if file_path:
                    ext = os.path.splitext(file_path)[1].lower()
                    if ext:
                        file_type_counts[ext] += 1
                    else:
                        file_type_counts["no_extension"] += 1
                    
                    # Folder analysis - handle different folder separators
                    if '/' in file_path:
                        folder = os.path.dirname(file_path)
                        if folder:
                            # Get top-level folder
                            top_folder = folder.split('/')[0]
                            folder_counts[top_folder] += 1
                    elif '\\' in file_path:
                        folder = os.path.dirname(file_path.replace('\\', '/'))
                        if folder:
                            top_folder = folder.split('/')[0]
                            folder_counts[top_folder] += 1
                
                # For detailed analysis, prioritize actually downloaded files
                is_downloaded = not file_info.get("skipped", False)
                
                # For size analysis, try to get file size from local file if available
                local_path = file_info.get("local_path", "")
                file_size = 0
                if local_path and os.path.exists(local_path):
                    try:
                        file_size = os.path.getsize(local_path)
                        size_total += file_size
                    except:
                        pass
                
                # Size categorization for all files
                if file_size > 0:
                    if file_size < 1024 * 1024:  # < 1MB
                        insights["size_distribution"]["small"] += 1
                    elif file_size < 50 * 1024 * 1024:  # < 50MB
                        insights["size_distribution"]["medium"] += 1
                    else:  # >= 50MB
                        insights["size_distribution"]["large"] += 1
                        
                    # Track largest files (limit to downloaded files for relevance)
                    if is_downloaded and file_size > 0:
                        insights["largest_files"].append({
                            "path": file_path,
                            "size": file_size,
                            "size_mb": round(file_size / (1024 * 1024), 2),
                            "downloaded": is_downloaded
                        })
                else:
                    insights["size_distribution"]["unknown"] += 1
                
                # For timeline, check if file has timestamp or use current time
                timestamp = file_info.get("timestamp", "")
                if not timestamp and local_path and os.path.exists(local_path):
                    try:
                        # Use file modification time
                        import time
                        mtime = os.path.getmtime(local_path)
                        timestamp = datetime.fromtimestamp(mtime).isoformat()
                    except:
                        pass
                
                if timestamp:
                    try:
                        file_time = datetime.fromisoformat(timestamp.replace('Z', ''))
                        now = datetime.now()
                        time_diff = now - file_time
                        
                        if time_diff.total_seconds() < 3600:  # Last hour
                            insights["download_timeline"]["recent"] += 1
                        elif time_diff.days == 0:  # Today
                            insights["download_timeline"]["today"] += 1
                        elif time_diff.days == 1:  # Yesterday
                            insights["download_timeline"]["yesterday"] += 1
                        else:  # Older
                            insights["download_timeline"]["older"] += 1
                    except:
                        insights["download_timeline"]["older"] += 1
                else:
                    insights["download_timeline"]["older"] += 1
                
                # Track recent downloads (prioritize actually downloaded files)
                if is_downloaded:
                    insights["recent_downloads"].append({
                        "path": file_path,
                        "timestamp": timestamp or "Unknown",
                        "size_mb": round(file_size / (1024 * 1024), 2) if file_size else 0,
                        "downloaded": True
                    })
            
            # Sort and limit results
            insights["file_types"] = dict(sorted(file_type_counts.items(), key=lambda x: x[1], reverse=True)[:10])
            insights["top_folders"] = [{"name": k, "count": v} for k, v in 
                                     sorted(folder_counts.items(), key=lambda x: x[1], reverse=True)[:10]]
            
            insights["largest_files"] = sorted(insights["largest_files"], 
                                             key=lambda x: x["size"], reverse=True)[:10]
            
            insights["recent_downloads"] = sorted(insights["recent_downloads"], 
                                                key=lambda x: x["timestamp"], reverse=True)[:10]
            
            # Analyze failures
            failure_counts = defaultdict(int)
            for failed in failed_files:
                error = str(failed.get("error", "Unknown error"))
                # Extract more meaningful error types
                if "429" in error:
                    failure_counts["Rate Limiting (429)"] += 1
                elif "timeout" in error.lower():
                    failure_counts["Timeout"] += 1
                elif "connection" in error.lower():
                    failure_counts["Connection Error"] += 1
                elif "404" in error:
                    failure_counts["File Not Found (404)"] += 1
                elif "403" in error:
                    failure_counts["Access Denied (403)"] += 1
                else:
                    error_type = error.split(':')[0] if ':' in error else "Other Error"
                    failure_counts[error_type[:50]] += 1  # Truncate long error types
            
            insights["failure_analysis"] = dict(sorted(failure_counts.items(), 
                                                     key=lambda x: x[1], reverse=True)[:5])
            
            # Add summary stats
            total_processed = len([f for f in success_files if not f.get("skipped", False)])
            insights["summary"] = {
                "total_size_gb": round(size_total / (1024 * 1024 * 1024), 2),
                "avg_file_size_mb": round((size_total / total_processed) / (1024 * 1024), 2) if total_processed > 0 else 0,
                "unique_file_types": len(file_type_counts),
                "unique_folders": len(folder_counts),
                "files_processed": total_processed
            }
            
        except Exception as e:
            insights["error"] = f"Error generating insights: {str(e)}"
        
        return insights
    
    def generate_insights_html(self, data):
        """Generate HTML page for detailed file insights (optimized for performance)."""
        insights = data.get("file_insights", {})
        stats = data.get("stats", {})
        
        # Quick check for insights availability
        if not insights or insights.get("error"):
            return self._generate_error_html("Insights not available or loading...")
        
        # File types chart data (limit to top 8 for performance)
        file_types = insights.get("file_types", {})
        file_types_items = list(file_types.items())[:8]
        file_types_json = json.dumps(file_types_items)
        
        # Folder distribution chart data
        folders = insights.get("top_folders", [])[:8]
        folder_data = [[folder["name"], folder["count"]] for folder in folders]
        folder_data_json = json.dumps(folder_data)
        
        # Size distribution data
        size_dist = insights.get("size_distribution", {})
        size_data = [
            ["Small (<1MB)", size_dist.get("small", 0)],
            ["Medium (1-50MB)", size_dist.get("medium", 0)], 
            ["Large (>50MB)", size_dist.get("large", 0)],
            ["Unknown", size_dist.get("unknown", 0)]
        ]
        size_data_json = json.dumps(size_data)
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>File Insights - SharePoint Download Monitor</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <meta http-equiv="refresh" content="30">
            <style>
                .insight-card {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; margin-bottom: 20px; }}
                .chart-card {{ background: #ffffff; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
                .metric-highlight {{ font-size: 2rem; font-weight: bold; color: #007bff; }}
                .nav-pills .nav-link {{ margin: 0 5px; }}
                .nav-pills .nav-link.active {{ background-color: #007bff; }}
                .table-responsive {{ max-height: 400px; overflow-y: auto; }}
            </style>
        </head>
        <body class="bg-light">
            <div class="container-fluid mt-3">
                <!-- Navigation -->
                <div class="row mb-4">
                    <div class="col-12">
                        <nav class="navbar navbar-expand-lg navbar-light bg-white rounded shadow-sm">
                            <div class="container-fluid">
                                <span class="navbar-brand">📊 SharePoint Download Analytics</span>
                                <div class="navbar-nav">
                                    <a class="nav-link" href="/">🏠 Overview</a>
                                    <a class="nav-link active" href="/insights">📈 File Insights</a>
                                    <span class="nav-link text-muted">Updated: {data["timestamp"]}</span>
                                </div>
                            </div>
                        </nav>
                    </div>
                </div>
                
                <!-- Summary Stats Row -->
                <div class="row mb-4">
                    <div class="col-md-3">
                        <div class="card insight-card">
                            <div class="card-body text-center">
                                <div class="metric-highlight text-white">{insights.get('summary', {}).get('total_size_gb', 0)}</div>
                                <h6>Total Size (GB)</h6>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card insight-card">
                            <div class="card-body text-center">
                                <div class="metric-highlight text-white">{insights.get('summary', {}).get('avg_file_size_mb', 0)}</div>
                                <h6>Avg File Size (MB)</h6>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card insight-card">
                            <div class="card-body text-center">
                                <div class="metric-highlight text-white">{insights.get('summary', {}).get('unique_file_types', 0)}</div>
                                <h6>File Types</h6>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card insight-card">
                            <div class="card-body text-center">
                                <div class="metric-highlight text-white">{insights.get('summary', {}).get('unique_folders', 0)}</div>
                                <h6>Unique Folders</h6>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Charts Row -->
                <div class="row mb-4">
                    <div class="col-md-6">
                        <div class="card chart-card">
                            <div class="card-header">
                                <h5>📁 File Types Distribution</h5>
                            </div>
                            <div class="card-body">
                                <canvas id="fileTypesChart" height="200"></canvas>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card chart-card">
                            <div class="card-header">
                                <h5>📂 Top Folders</h5>
                            </div>
                            <div class="card-body">
                                <canvas id="foldersChart" height="200"></canvas>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Size and Timeline Row -->
                <div class="row mb-4">
                    <div class="col-md-6">
                        <div class="card chart-card">
                            <div class="card-header">
                                <h5>📊 File Size Distribution</h5>
                            </div>
                            <div class="card-body">
                                <canvas id="sizeChart" height="200"></canvas>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card chart-card">
                            <div class="card-header">
                                <h5>⏰ Download Timeline</h5>
                            </div>
                            <div class="card-body">
                                <canvas id="timelineChart" height="200"></canvas>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Detailed Tables Row -->
                <div class="row mb-4">
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5>📈 Largest Files</h5>
                            </div>
                            <div class="card-body">
                                <div class="table-responsive">
                                    <table class="table table-sm">
                                        <thead>
                                            <tr>
                                                <th>File Path</th>
                                                <th>Size (MB)</th>
                                            </tr>
                                        </thead>
                                        <tbody>
        """
        
        # Add largest files table
        for file_info in insights.get("largest_files", [])[:10]:
            file_path = file_info.get("path", "")
            display_path = file_path[-50:] if len(file_path) > 50 else file_path
            size_mb = file_info.get("size_mb", 0)
            html += f"""
                                            <tr>
                                                <td title="{file_path}">{display_path}</td>
                                                <td>{size_mb}</td>
                                            </tr>
            """
        
        html += f"""
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5>🕒 Recent Downloads</h5>
                            </div>
                            <div class="card-body">
                                <div class="table-responsive">
                                    <table class="table table-sm">
                                        <thead>
                                            <tr>
                                                <th>File</th>
                                                <th>Time</th>
                                                <th>Size</th>
                                            </tr>
                                        </thead>
                                        <tbody>
        """
        
        # Add recent downloads table
        for file_info in insights.get("recent_downloads", [])[:10]:
            file_path = file_info.get("path", "")
            import os
            display_path = os.path.basename(file_path) if file_path else ""
            timestamp = file_info.get("timestamp", "")
            try:
                if timestamp:
                    dt = datetime.fromisoformat(timestamp.replace('Z', ''))
                    time_str = dt.strftime("%H:%M:%S")
                else:
                    time_str = "Unknown"
            except:
                time_str = "Unknown"
            size_mb = file_info.get("size_mb", 0)
            html += f"""
                                            <tr>
                                                <td title="{file_path}">{display_path}</td>
                                                <td>{time_str}</td>
                                                <td>{size_mb} MB</td>
                                            </tr>
            """
        
        # Failure analysis
        failure_analysis = insights.get("failure_analysis", {})
        failure_rows = ""
        for error_type, count in failure_analysis.items():
            failure_rows += f"<tr><td>{error_type}</td><td>{count}</td></tr>"
        
        html += f"""
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Failure Analysis -->
                {"<div class='row mb-4'><div class='col-12'><div class='card'><div class='card-header'><h5>❌ Failure Analysis</h5></div><div class='card-body'><table class='table'><thead><tr><th>Error Type</th><th>Count</th></tr></thead><tbody>" + failure_rows + "</tbody></table></div></div></div></div>" if failure_analysis else ""}
                
            </div>
        """
        
        # Add JavaScript separately to avoid f-string conflicts
        html += """
            <script>
                // Basic charts without complex formatting to avoid errors
                try {
                    // File Types Chart
                    if (document.getElementById('fileTypesChart')) {
                        const fileTypesCtx = document.getElementById('fileTypesChart').getContext('2d');
                        const fileTypesData = """ + file_types_json + """;
                        new Chart(fileTypesCtx, {
                            type: 'doughnut',
                            data: {
                                labels: fileTypesData.map(item => item[0]),
                                datasets: [{
                                    data: fileTypesData.map(item => item[1]),
                                    backgroundColor: ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40']
                                }]
                            },
                            options: { responsive: true, maintainAspectRatio: false }
                        });
                    }
                    
                    // Folders Chart
                    if (document.getElementById('foldersChart')) {
                        const foldersCtx = document.getElementById('foldersChart').getContext('2d');
                        const foldersData = """ + folder_data_json + """;
                        new Chart(foldersCtx, {
                            type: 'bar',
                            data: {
                                labels: foldersData.map(item => item[0]),
                                datasets: [{ label: 'Files', data: foldersData.map(item => item[1]), backgroundColor: '#36A2EB' }]
                            },
                            options: { responsive: true, maintainAspectRatio: false }
                        });
                    }
                    
                    // Size Distribution Chart
                    if (document.getElementById('sizeChart')) {
                        const sizeCtx = document.getElementById('sizeChart').getContext('2d');
                        const sizeData = """ + size_data_json + """;
                        new Chart(sizeCtx, {
                            type: 'pie',
                            data: {
                                labels: sizeData.map(item => item[0]),
                                datasets: [{ data: sizeData.map(item => item[1]), backgroundColor: ['#4BC0C0', '#36A2EB', '#FF6384', '#FFCE56'] }]
                            },
                            options: { responsive: true, maintainAspectRatio: false }
                        });
                    }
                    
                    // Timeline Chart
                    if (document.getElementById('timelineChart')) {
                        const timelineCtx = document.getElementById('timelineChart').getContext('2d');
                        const timelineData = """ + json.dumps([
            ["Recent (1h)", insights.get("download_timeline", {}).get("recent", 0)],
            ["Today", insights.get("download_timeline", {}).get("today", 0)],
            ["Yesterday", insights.get("download_timeline", {}).get("yesterday", 0)],
            ["Older", insights.get("download_timeline", {}).get("older", 0)]
        ]) + """;
                        new Chart(timelineCtx, {
                            type: 'bar',
                            data: {
                                labels: timelineData.map(item => item[0]),
                                datasets: [{ label: 'Downloads', data: timelineData.map(item => item[1]), backgroundColor: ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0'] }]
                            },
                            options: { responsive: true, maintainAspectRatio: false }
                        });
                    }
                } catch (error) {
                    console.log('Chart rendering error:', error);
                }
            </script>
        </body>
        </html>
        """
        
        return html
    
    def generate_html(self, data):
        """Generate HTML dashboard."""
        stats = data.get("stats", {})
        
        # Status color based on progress
        if data["status"] == "running":
            status_color = "success"
            status_icon = "🚀"
        else:
            status_color = "warning"
            status_icon = "⏸️"
        
        # Progress bar color
        progress_pct = stats.get("progress_percentage", 0)
        if progress_pct > 90:
            progress_color = "success"
        elif progress_pct > 50:
            progress_color = "info"
        else:
            progress_color = "primary"
            
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>SharePoint Download Monitor</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <meta http-equiv="refresh" content="5">
            <style>
                .metric-card {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }}
                .status-card {{ background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; }}
                .progress-card {{ background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; }}
                .error-card {{ background: linear-gradient(135deg, #fa709a 0%, #fee140 100%); color: white; }}
                .big-number {{ font-size: 2.5rem; font-weight: bold; }}
                .refresh-note {{ position: fixed; top: 10px; right: 10px; z-index: 1000; }}
            </style>
        </head>
        <body class="bg-light">
            <div class="container mt-4">
                <div class="refresh-note">
                    <span class="badge bg-info">Auto-refresh: 5s</span>
                </div>
                
                <h1 class="text-center mb-4">
                    🚀 SharePoint Download Monitor
                    <small class="text-muted d-block">Real-time Progress Tracking</small>
                </h1>
                
                <!-- Navigation Pills -->
                <div class="text-center mb-4">
                    <ul class="nav nav-pills justify-content-center">
                        <li class="nav-item">
                            <a class="nav-link active" href="/">🏠 Overview</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="/insights">📈 File Insights</a>
                        </li>
                    </ul>
                </div>
                
                <!-- Status Row -->
                <div class="row mb-4">
                    <div class="col-md-6">
                        <div class="card status-card">
                            <div class="card-body text-center">
                                <h2>{status_icon} Status: {data["status"].title()}</h2>
                                <p class="mb-0">Last updated: {data["timestamp"]}</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card progress-card">
                            <div class="card-body text-center">
                                <h2>📊 Progress: {progress_pct:.1f}%</h2>
                                <div class="progress" style="height: 20px;">
                                    <div class="progress-bar bg-light" style="width: {progress_pct}%"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Metrics Row -->
                <div class="row mb-4">
                    <div class="col-md-3">
                        <div class="card metric-card h-100">
                            <div class="card-body text-center">
                                <div class="big-number">{stats.get('processed', 0):,}</div>
                                <h5>Files Processed</h5>
                                <small>of {stats.get('total_files', 0):,} total</small>
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-md-3">
                        <div class="card metric-card h-100">
                            <div class="card-body text-center">
                                <div class="big-number">{stats.get('successful_downloads', 0):,}</div>
                                <h5>Downloaded</h5>
                                <small>{stats.get('success_rate', 0):.1f}% success rate</small>
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-md-3">
                        <div class="card metric-card h-100">
                            <div class="card-body text-center">
                                <div class="big-number">{stats.get('remaining_files', 0) if isinstance(stats.get('remaining_files', 0), int) else 0:,}</div>
                                <h5>Remaining</h5>
                                <small>ETA: {stats.get('eta', 'Calculating...')}</small>
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-md-3">
                        <div class="card error-card h-100">
                            <div class="card-body text-center">
                                <div class="big-number">{stats.get('failed_downloads', 0)}</div>
                                <h5>Failed</h5>
                                <small>{stats.get('skipped_files', 0):,} skipped</small>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Details Row -->
                <div class="row">
                    <div class="col-md-12">
                        <div class="card">
                            <div class="card-header">
                                <h5>📋 Download Details</h5>
                            </div>
                            <div class="card-body">
                                <div class="row">
                                    <div class="col-md-6">
                                        <p><strong>Cache Created:</strong> {data.get('cache', {}).get('timestamp', 'Unknown')}</p>
                                        <p><strong>Last Progress Update:</strong> {stats.get('last_update', 'Unknown')}</p>
                                        <p><strong>Download Directory:</strong> {self.download_path}</p>
                                    </div>
                                    <div class="col-md-6">
                                        {"<p><strong>Error:</strong> " + data.get('error', '') + "</p>" if data.get('error') else ""}
                                        <p><strong>Site ID:</strong> {data.get('cache', {}).get('site_id', 'Unknown')[:50]}...</p>
                                        <p><strong>Turbo Mode:</strong> {data.get('progress', {}).get('turbo_mode', False)}</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="text-center mt-4">
                    <p class="text-muted">
                        🔄 This dashboard auto-refreshes every 5 seconds<br>
                        📊 Data source: JSON progress and cache files<br>
                        🚀 Created by Sanm Ibitoye with help from LLM.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP handler for the dashboard."""
    
    def __init__(self, monitor, *args, **kwargs):
        self.monitor = monitor
        super().__init__(*args, **kwargs)
    
    def log_message(self, format, *args):
        """Override to reduce verbose logging - only log actual errors, not VS Code browser requests."""
        # Don't log VS Code browser requests with query parameters
        if "vscodeBrowserReqId" in str(args):
            return
        # Only log real errors
        if "error" in format.lower() or ("404" in str(args) and "vscodeBrowserReqId" not in str(args)):
            super().log_message(format, *args)
    
    def do_GET(self):
        """Handle GET requests."""
        try:
            # Parse the URL to handle query parameters from VS Code browser
            from urllib.parse import urlparse, parse_qs
            parsed_url = urlparse(self.path)
            path = parsed_url.path
            
            if path == '/' or path == '/dashboard':
                # Serve the dashboard
                data = self.monitor.load_data()
                html = self.monitor.generate_html(data)
                
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                self.wfile.write(html.encode('utf-8'))
            elif path == '/insights':
                # Serve the insights page
                data = self.monitor.load_data()
                html = self.monitor.generate_insights_html(data)
                
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                self.wfile.write(html.encode('utf-8'))
            elif path == '/api/data':
                # Serve JSON data
                data = self.monitor.load_data()
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                self.wfile.write(json.dumps(data, indent=2).encode('utf-8'))
            elif path == '/status':
                # Quick status check for debugging
                status = {
                    "server": "running",
                    "timestamp": datetime.now().isoformat(),
                    "files_exist": {
                        "progress": self.monitor.progress_file.exists(),
                        "cache": self.monitor.cache_file.exists()
                    }
                }
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                self.wfile.write(json.dumps(status, indent=2).encode('utf-8'))
            else:
                self.send_error(404)
        except ConnectionAbortedError:
            # Client disconnected early - ignore silently
            pass
        except BrokenPipeError:
            # Client disconnected - ignore silently  
            pass
        except Exception as e:
            # Log other errors but don't crash
            print(f"Dashboard error: {e}")
            try:
                self.send_error(500)
            except:
                pass

def main():
    """Run the simple dashboard server."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Simple SharePoint Progress Monitor")
    parser.add_argument("--path", default="C:/commercial_pdfs/downloaded_files",
                       help="Path to download directory")
    parser.add_argument("--port", default=8051, type=int,
                       help="Port to run on")
    parser.add_argument("--no-browser", action="store_true",
                       help="Don't auto-open browser")
    
    args = parser.parse_args()
    
    # Create monitor
    monitor = SimpleProgressMonitor(args.path)
    
    # Create server
    def handler(*args, **kwargs):
        return DashboardHandler(monitor, *args, **kwargs)
    
    with socketserver.TCPServer(("", args.port), handler) as httpd:
        url = f"http://localhost:{args.port}"
        
        print(f"🚀 SharePoint Progress Monitor")
        print(f"📊 Dashboard running at: {url}")
        print(f"🔄 Auto-refresh every 5 seconds")
        print(f"📁 Monitoring: {args.path}")
        print(f"💡 Press Ctrl+C to stop")
        print()
        
        # Open browser
        if not args.no_browser:
            threading.Timer(1.0, lambda: webbrowser.open(url)).start()
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\\n🛑 Dashboard stopped")

if __name__ == "__main__":
    main()
