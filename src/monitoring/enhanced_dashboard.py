#!/usr/bin/env python3
"""
📊 Enhanced SharePoint Download Dashboard
========================================

Comprehensive real-time dashboard for monitoring SharePoint download progress
with detailed analytics, statistics, and insights.

Features:
- Detailed progress tracking with file-level insights
- Download speed analysis and trends
- File type distribution and size analytics
- Error tracking with detailed reporting
- Storage analysis and space utilization
- Time estimates and completion predictions
- Interactive charts and visualizations
- Auto-refreshing interface with enhanced UI

Author: GitHub Copilot
Date: August 7, 2025
"""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
import http.server
import socketserver
import threading
import webbrowser
from urllib.parse import urlparse, parse_qs
import logging
import glob
from collections import defaultdict, Counter
import mimetypes

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EnhancedProgressMonitor:
    """Enhanced progress monitor with detailed analytics."""
    
    def __init__(self, download_path: str = "C:/commercial_pdfs/downloaded_files"):
        self.download_path = Path(download_path)
        self.progress_file = self.download_path / "download_progress_turbo.json"
        self.cache_file = self.download_path / "file_list_cache.json"
        self.stats_history = []
    
    def safe_json_load(self, file_path, fallback=None):
        """Safely load JSON with fallback handling."""
        if fallback is None:
            fallback = {}
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error in {file_path}: {e}")
            # Try to repair common JSON issues
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Try to fix common issues
                    content = content.rstrip(',\n\r\t ')  # Remove trailing commas
                    if not content.endswith('}') and not content.endswith(']'):
                        content += '}'  # Add missing closing brace
                    return json.loads(content)
            except Exception as repair_error:
                logger.error(f"Could not repair JSON in {file_path}: {repair_error}")
                return fallback
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            return fallback
        
    def get_file_size_formatted(self, size_bytes):
        """Convert bytes to human readable format."""
        if size_bytes == 0:
            return "0 B"
        size_names = ["B", "KB", "MB", "GB", "TB"]
        import math
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_names[i]}"
    
    def analyze_downloaded_files(self):
        """Analyze actual downloaded files on disk."""
        if not self.download_path.exists():
            return {}
            
        file_stats = {
            "total_files": 0,
            "total_size": 0,
            "file_types": Counter(),
            "size_by_type": defaultdict(int),
            "folders": set(),
            "largest_files": [],
            "recent_files": []
        }
        
        try:
            # Scan all files recursively
            for file_path in self.download_path.rglob("*"):
                if file_path.is_file() and not file_path.name.startswith('.'):
                    file_stats["total_files"] += 1
                    file_size = file_path.stat().st_size
                    file_stats["total_size"] += file_size
                    
                    # File type analysis
                    ext = file_path.suffix.lower()
                    if not ext:
                        ext = "no_extension"
                    file_stats["file_types"][ext] += 1
                    file_stats["size_by_type"][ext] += file_size
                    
                    # Folder tracking
                    folder = str(file_path.parent.relative_to(self.download_path))
                    file_stats["folders"].add(folder)
                    
                    # Track largest files
                    file_info = {
                        "path": str(file_path.relative_to(self.download_path)),
                        "size": file_size,
                        "size_formatted": self.get_file_size_formatted(file_size),
                        "modified": datetime.fromtimestamp(file_path.stat().st_mtime)
                    }
                    file_stats["largest_files"].append(file_info)
                    file_stats["recent_files"].append(file_info)
            
            # Sort and limit largest files
            file_stats["largest_files"].sort(key=lambda x: x["size"], reverse=True)
            file_stats["largest_files"] = file_stats["largest_files"][:10]
            
            # Sort and limit recent files
            file_stats["recent_files"].sort(key=lambda x: x["modified"], reverse=True)
            file_stats["recent_files"] = file_stats["recent_files"][:10]
            
            file_stats["folders"] = len(file_stats["folders"])
            
        except Exception as e:
            logger.error(f"Error analyzing files: {e}")
            
        return file_stats
    
    def load_comprehensive_data(self):
        """Load all available data and perform comprehensive analysis."""
        data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "unknown",
            "progress": {},
            "cache": {},
            "file_analysis": {},
            "performance": {},
            "errors": [],
            "predictions": {}
        }
        
        try:
            # Load progress data with safe JSON loading
            if self.progress_file.exists():
                progress_data = self.safe_json_load(self.progress_file, {"downloaded_count": 0, "total_count": 0})
                data["progress"] = progress_data
                data["status"] = "active" if progress_data.get("is_running", False) else "stopped"
            
            # Load cache data with safe JSON loading
            if self.cache_file.exists():
                cache_data = self.safe_json_load(self.cache_file, {"files": []})
                data["cache"] = cache_data
            
            # Analyze downloaded files (this should work regardless of JSON issues)
            data["file_analysis"] = self.analyze_downloaded_files()
            
            # Calculate performance metrics
            data["performance"] = self.calculate_performance_metrics(data)
            
            # Extract error information
            data["errors"] = self.extract_error_info(data)
            
            # Generate predictions
            data["predictions"] = self.generate_predictions(data)
            
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            data["status"] = "error"
            data["error"] = str(e)
        
        return data
    
    def calculate_performance_metrics(self, data):
        """Calculate detailed performance metrics."""
        metrics = {
            "download_speed": 0,
            "avg_file_size": 0,
            "completion_rate": 0,
            "efficiency": 0,
            "time_running": "Unknown",
            "files_per_minute": 0
        }
        
        try:
            progress = data.get("progress", {})
            file_analysis = data.get("file_analysis", {})
            
            # Download speed calculation
            if progress.get("downloaded_count", 0) > 0 and progress.get("start_time"):
                start_time = datetime.fromisoformat(progress["start_time"].replace('Z', '+00:00'))
                elapsed = (datetime.now() - start_time.replace(tzinfo=None)).total_seconds()
                
                if elapsed > 0:
                    metrics["files_per_minute"] = round((progress["downloaded_count"] / elapsed) * 60, 2)
                    metrics["time_running"] = str(timedelta(seconds=int(elapsed)))
                    
                    # Download speed in MB/s
                    total_mb = file_analysis.get("total_size", 0) / (1024 * 1024)
                    metrics["download_speed"] = round(total_mb / elapsed, 2)
            
            # Completion rate
            total_files = progress.get("total_count", 0)
            downloaded_files = progress.get("downloaded_count", 0)
            if total_files > 0:
                metrics["completion_rate"] = round((downloaded_files / total_files) * 100, 2)
            
            # Average file size
            if file_analysis.get("total_files", 0) > 0:
                metrics["avg_file_size"] = file_analysis["total_size"] / file_analysis["total_files"]
            
        except Exception as e:
            logger.error(f"Error calculating performance: {e}")
        
        return metrics
    
    def extract_error_info(self, data):
        """Extract and analyze error information."""
        errors = []
        
        try:
            progress = data.get("progress", {})
            
            # Failed files
            failed_files = progress.get("failed_files", [])
            for failed_file in failed_files:
                if isinstance(failed_file, dict):
                    errors.append({
                        "type": "download_failure",
                        "file": failed_file.get("path", "Unknown"),
                        "error": failed_file.get("error", "Unknown error"),
                        "timestamp": failed_file.get("timestamp", "Unknown")
                    })
                elif isinstance(failed_file, str):
                    errors.append({
                        "type": "download_failure",
                        "file": failed_file,
                        "error": "Download failed",
                        "timestamp": "Unknown"
                    })
            
            # Check for authentication errors
            error_count = progress.get("error_count", 0)
            if error_count > 0:
                errors.append({
                    "type": "system_error",
                    "file": "Multiple files",
                    "error": f"{error_count} errors encountered during download",
                    "timestamp": data["timestamp"]
                })
        
        except Exception as e:
            logger.error(f"Error extracting error info: {e}")
        
        return errors
    
    def generate_predictions(self, data):
        """Generate time and completion predictions."""
        predictions = {
            "estimated_completion": "Unknown",
            "remaining_time": "Unknown",
            "remaining_files": 0,
            "remaining_size": "Unknown",
            "projected_total_size": "Unknown"
        }
        
        try:
            progress = data.get("progress", {})
            performance = data.get("performance", {})
            
            total_files = progress.get("total_count", 0)
            downloaded_files = progress.get("downloaded_count", 0)
            remaining_files = total_files - downloaded_files
            
            predictions["remaining_files"] = remaining_files
            
            if performance.get("files_per_minute", 0) > 0 and remaining_files > 0:
                remaining_minutes = remaining_files / performance["files_per_minute"]
                predictions["remaining_time"] = str(timedelta(minutes=int(remaining_minutes)))
                
                completion_time = datetime.now() + timedelta(minutes=remaining_minutes)
                predictions["estimated_completion"] = completion_time.strftime("%Y-%m-%d %H:%M:%S")
            
            # Size predictions
            file_analysis = data.get("file_analysis", {})
            if performance.get("avg_file_size", 0) > 0:
                estimated_remaining_size = remaining_files * performance["avg_file_size"]
                predictions["remaining_size"] = self.get_file_size_formatted(estimated_remaining_size)
                
                projected_total = file_analysis.get("total_size", 0) + estimated_remaining_size
                predictions["projected_total_size"] = self.get_file_size_formatted(projected_total)
        
        except Exception as e:
            logger.error(f"Error generating predictions: {e}")
        
        return predictions

def create_enhanced_html(data):
    """Create enhanced HTML dashboard with detailed analytics."""
    
    progress = data.get("progress", {})
    file_analysis = data.get("file_analysis", {})
    performance = data.get("performance", {})
    errors = data.get("errors", [])
    predictions = data.get("predictions", {})
    
    # Calculate percentages and formatted values
    downloaded_count = progress.get("downloaded_count", 0)
    total_count = progress.get("total_count", 0)
    percentage = (downloaded_count / total_count * 100) if total_count > 0 else 0
    
    # File type analysis for charts
    file_types = file_analysis.get("file_types", {})
    size_by_type = file_analysis.get("size_by_type", {})
    
    # Top file types by count
    top_types_by_count = sorted(file_types.items(), key=lambda x: x[1], reverse=True)[:5]
    top_types_by_size = sorted(size_by_type.items(), key=lambda x: x[1], reverse=True)[:5]
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>📊 SharePoint Download Dashboard</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css">
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            .card-metric {{ font-size: 2rem; font-weight: bold; }}
            .metric-label {{ font-size: 0.9rem; color: #6c757d; }}
            .progress-ring {{ transform: rotate(-90deg); }}
            .chart-container {{ position: relative; height: 300px; }}
            .status-badge {{ font-size: 1.1rem; }}
            .error-item {{ border-left: 4px solid #dc3545; }}
            .recent-file {{ font-size: 0.85rem; }}
            body {{ background-color: #f8f9fa; }}
            .dashboard-card {{ box-shadow: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.075); }}
        </style>
        <script>
            setTimeout(function() {{ location.reload(); }}, 5000);
        </script>
    </head>
    <body>
        <div class="container-fluid py-3">
            <!-- Header -->
            <div class="row mb-4">
                <div class="col-12">
                    <div class="card dashboard-card border-0">
                        <div class="card-body">
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <h1 class="mb-1"><i class="bi bi-cloud-download"></i> SharePoint Download Dashboard</h1>
                                    <p class="text-muted mb-0">Real-time monitoring and analytics • Last updated: {data["timestamp"]}</p>
                                </div>
                                <div class="text-end">
                                    <span class="badge {"bg-success" if data["status"] == "active" else "bg-warning"} status-badge">
                                        <i class="bi bi-{"play-circle" if data["status"] == "active" else "pause-circle"}"></i> 
                                        {data["status"].title()}
                                    </span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Key Metrics -->
            <div class="row mb-4">
                <div class="col-md-3">
                    <div class="card dashboard-card border-0 text-center">
                        <div class="card-body">
                            <div class="card-metric text-primary">{downloaded_count:,}</div>
                            <div class="metric-label">Files Downloaded</div>
                            <small class="text-muted">of {total_count:,} total ({percentage:.1f}%)</small>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card dashboard-card border-0 text-center">
                        <div class="card-body">
                            <div class="card-metric text-success">{EnhancedProgressMonitor("").get_file_size_formatted(file_analysis.get("total_size", 0))}</div>
                            <div class="metric-label">Data Downloaded</div>
                            <small class="text-muted">across {file_analysis.get("folders", 0)} folders</small>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card dashboard-card border-0 text-center">
                        <div class="card-body">
                            <div class="card-metric text-info">{performance.get("files_per_minute", 0)}</div>
                            <div class="metric-label">Files/Minute</div>
                            <small class="text-muted">{performance.get("download_speed", 0)} MB/s</small>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card dashboard-card border-0 text-center">
                        <div class="card-body">
                            <div class="card-metric text-warning">{predictions.get("remaining_files", 0):,}</div>
                            <div class="metric-label">Files Remaining</div>
                            <small class="text-muted">~{predictions.get("remaining_time", "Unknown")}</small>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Progress Bar -->
            <div class="row mb-4">
                <div class="col-12">
                    <div class="card dashboard-card border-0">
                        <div class="card-body">
                            <h5 class="card-title"><i class="bi bi-graph-up"></i> Download Progress</h5>
                            <div class="progress mb-3" style="height: 30px;">
                                <div class="progress-bar bg-gradient" role="progressbar" 
                                     style="width: {percentage}%" aria-valuenow="{percentage}" 
                                     aria-valuemin="0" aria-valuemax="100">
                                    {percentage:.1f}%
                                </div>
                            </div>
                            <div class="row">
                                <div class="col-md-6">
                                    <small><strong>Started:</strong> {progress.get("start_time", "Unknown")}</small><br>
                                    <small><strong>Running Time:</strong> {performance.get("time_running", "Unknown")}</small><br>
                                    <small><strong>Estimated Completion:</strong> {predictions.get("estimated_completion", "Unknown")}</small>
                                </div>
                                <div class="col-md-6">
                                    <small><strong>Average File Size:</strong> {EnhancedProgressMonitor("").get_file_size_formatted(performance.get("avg_file_size", 0))}</small><br>
                                    <small><strong>Projected Total Size:</strong> {predictions.get("projected_total_size", "Unknown")}</small><br>
                                    <small><strong>Remaining Size:</strong> {predictions.get("remaining_size", "Unknown")}</small>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- File Type Analysis -->
            <div class="row mb-4">
                <div class="col-md-6">
                    <div class="card dashboard-card border-0">
                        <div class="card-body">
                            <h5 class="card-title"><i class="bi bi-pie-chart"></i> File Types by Count</h5>
                            <div class="chart-container">
                                <canvas id="fileTypesChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card dashboard-card border-0">
                        <div class="card-body">
                            <h5 class="card-title"><i class="bi bi-bar-chart"></i> Storage by File Type</h5>
                            <div class="chart-container">
                                <canvas id="storageSizeChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Detailed Statistics -->
            <div class="row mb-4">
                <div class="col-md-6">
                    <div class="card dashboard-card border-0">
                        <div class="card-body">
                            <h5 class="card-title"><i class="bi bi-list-ul"></i> Top File Types</h5>
                            <div class="table-responsive">
                                <table class="table table-sm">
                                    <thead>
                                        <tr>
                                            <th>Extension</th>
                                            <th class="text-end">Count</th>
                                            <th class="text-end">Size</th>
                                        </tr>
                                    </thead>
                                    <tbody>
    """
    
    # Add file type rows
    for ext, count in top_types_by_count:
        size = size_by_type.get(ext, 0)
        size_formatted = EnhancedProgressMonitor("").get_file_size_formatted(size)
        html += f"""
                                        <tr>
                                            <td><span class="badge bg-secondary">{ext}</span></td>
                                            <td class="text-end">{count:,}</td>
                                            <td class="text-end">{size_formatted}</td>
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
                    <div class="card dashboard-card border-0">
                        <div class="card-body">
                            <h5 class="card-title"><i class="bi bi-files"></i> Recent Downloads</h5>
                            <div class="recent-files" style="max-height: 300px; overflow-y: auto;">
    """
    
    # Add recent files
    recent_files = file_analysis.get("recent_files", [])[:5]
    for file_info in recent_files:
        html += f"""
                                <div class="d-flex justify-content-between align-items-center py-2 border-bottom recent-file">
                                    <div class="text-truncate me-2">
                                        <i class="bi bi-file-earmark"></i> {file_info.get("path", "Unknown")[:50]}...
                                    </div>
                                    <div class="text-end">
                                        <small class="text-muted">{file_info.get("size_formatted", "Unknown")}</small>
                                    </div>
                                </div>
        """
    
    html += f"""
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Error Analysis -->
            {"" if not errors else f'''
            <div class="row mb-4">
                <div class="col-12">
                    <div class="card dashboard-card border-0">
                        <div class="card-body">
                            <h5 class="card-title text-danger"><i class="bi bi-exclamation-triangle"></i> Error Analysis ({len(errors)} errors)</h5>
                            <div class="row">
                                {"".join([f'''
                                <div class="col-md-6 mb-2">
                                    <div class="alert alert-danger error-item">
                                        <strong>{error.get("type", "Unknown").replace("_", " ").title()}:</strong> {error.get("file", "Unknown")}<br>
                                        <small>{error.get("error", "Unknown error")}</small>
                                    </div>
                                </div>
                                ''' for error in errors[:4]])}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            '''}
            
        </div>
        
        <!-- Chart Scripts -->
        <script>
            // File Types Chart
            const fileTypesCtx = document.getElementById('fileTypesChart').getContext('2d');
            new Chart(fileTypesCtx, {{
                type: 'doughnut',
                data: {{
                    labels: {json.dumps([ext for ext, _ in top_types_by_count])},
                    datasets: [{{
                        data: {json.dumps([count for _, count in top_types_by_count])},
                        backgroundColor: ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF']
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ position: 'bottom' }}
                    }}
                }}
            }});
            
            // Storage Size Chart
            const storageSizeCtx = document.getElementById('storageSizeChart').getContext('2d');
            new Chart(storageSizeCtx, {{
                type: 'bar',
                data: {{
                    labels: {json.dumps([ext for ext, _ in top_types_by_size])},
                    datasets: [{{
                        label: 'Size (MB)',
                        data: {json.dumps([size / (1024 * 1024) for _, size in top_types_by_size])},
                        backgroundColor: '#36A2EB'
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {{
                        y: {{ beginAtZero: true }}
                    }}
                }}
            }});
        </script>
    </body>
    </html>
    """
    
    return html

class EnhancedDashboardServer:
    """Enhanced HTTP server for the dashboard."""
    
    def __init__(self, port=8052):
        self.port = port
        self.monitor = EnhancedProgressMonitor()
        
    def start_server(self):
        """Start the HTTP server."""
        handler = self.create_handler()
        
        try:
            with socketserver.TCPServer(("", self.port), handler) as httpd:
                logger.info(f"🚀 Enhanced Dashboard running at http://localhost:{self.port}")
                logger.info("📊 Features: Real-time analytics, detailed statistics, file type analysis")
                logger.info("🔄 Auto-refresh every 5 seconds")
                
                # Open browser
                threading.Timer(1.0, lambda: webbrowser.open(f'http://localhost:{self.port}')).start()
                
                httpd.serve_forever()
        except OSError as e:
            if e.errno == 10048:  # Port already in use
                logger.error(f"❌ Port {self.port} is already in use. Try a different port.")
            else:
                logger.error(f"❌ Error starting server: {e}")
    
    def create_handler(self):
        """Create HTTP request handler."""
        monitor = self.monitor
        
        class EnhancedDashboardHandler(http.server.SimpleHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/' or self.path == '/dashboard':
                    # Serve main dashboard
                    data = monitor.load_comprehensive_data()
                    html_content = create_enhanced_html(data)
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html; charset=utf-8')
                    self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                    self.send_header('Pragma', 'no-cache')
                    self.send_header('Expires', '0')
                    self.end_headers()
                    self.wfile.write(html_content.encode('utf-8'))
                    
                elif self.path == '/api/data':
                    # Serve JSON API
                    data = monitor.load_comprehensive_data()
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json; charset=utf-8')
                    self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                    self.end_headers()
                    self.wfile.write(json.dumps(data, indent=2, default=str).encode('utf-8'))
                    
                else:
                    self.send_error(404)
            
            def log_message(self, format, *args):
                pass  # Suppress default logging
        
        return EnhancedDashboardHandler

def main():
    """Main function to start the enhanced dashboard."""
    logger.info("🚀 Starting Enhanced SharePoint Download Dashboard...")
    
    # Try different ports if 8052 is taken
    ports = [8052, 8053, 8054, 8055]
    
    for port in ports:
        try:
            server = EnhancedDashboardServer(port)
            server.start_server()
            break
        except OSError as e:
            if e.errno == 10048 and port != ports[-1]:
                logger.warning(f"Port {port} in use, trying {ports[ports.index(port) + 1]}")
                continue
            else:
                logger.error(f"Failed to start server on port {port}: {e}")
                break

if __name__ == "__main__":
    main()
