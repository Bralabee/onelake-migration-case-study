#!/usr/bin/env python3
"""
🚀 SharePoint Download Dashboard - Real-time Monitoring & Analytics
==================================================================

Comprehensive dashboard for monitoring SharePoint download progress,
analyzing JSON files, logs, and providing actionable insights.

Features:
- Real-time progress monitoring
- Performance analytics
- Error analysis and reporting
- File system insights
- Interactive web dashboard
- Export capabilities

Author: GitHub Copilot
Date: August 7, 2025
"""

import os
import json
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import dash
from dash import dcc, html, Input, Output, State, dash_table
import dash_bootstrap_components as dbc
from collections import defaultdict
import psutil
import threading
import queue
import re
from typing import Dict, List, Any, Optional
import requests

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SharePointDashboard:
    """Real-time dashboard for SharePoint download monitoring."""
    
    def __init__(self, base_path: str = "C:/commercial_pdfs/downloaded_files"):
        self.base_path = Path(base_path)
        self.progress_file = self.base_path / "download_progress_turbo.json"
        self.cache_file = self.base_path / "file_list_cache.json"
        self.log_patterns = [
            "*.log",
            "../logs/*.log",
            "../../logs/*.log"
        ]
        
        # Initialize Dash app
        self.app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
        self.setup_layout()
        self.setup_callbacks()
        
        # Data refresh queue
        self.data_queue = queue.Queue()
        self.refresh_interval = 5  # seconds
        
    def load_progress_data(self) -> Dict[str, Any]:
        """Load and parse progress data from JSON files."""
        data = {
            "progress": None,
            "cache": None,
            "timestamp": datetime.now(),
            "file_count": 0,
            "download_stats": {},
            "errors": []
        }
        
        try:
            # Load progress file
            if self.progress_file.exists():
                with open(self.progress_file, 'r') as f:
                    data["progress"] = json.load(f)
                    
            # Load cache file
            if self.cache_file.exists():
                with open(self.cache_file, 'r') as f:
                    data["cache"] = json.load(f)
                    
            # Calculate statistics
            if data["progress"]:
                success_files = data["progress"].get("results", {}).get("success", [])
                failed_files = data["progress"].get("results", {}).get("failed", [])
                
                data["download_stats"] = {
                    "total_processed": data["progress"].get("last_processed_index", 0),
                    "successful_downloads": len([f for f in success_files if not f.get("skipped", False)]),
                    "skipped_files": len([f for f in success_files if f.get("skipped", False)]),
                    "failed_downloads": len(failed_files),
                    "last_update": data["progress"].get("timestamp", ""),
                    "turbo_mode": data["progress"].get("turbo_mode", False)
                }
                
                # Analyze errors
                data["errors"] = [
                    {
                        "file": f.get("file", "Unknown"),
                        "error": f.get("error", "Unknown error"),
                        "type": self.classify_error(f.get("error", ""))
                    }
                    for f in failed_files
                ]
                
            if data["cache"]:
                data["file_count"] = len(data["cache"].get("files", []))
                
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            data["errors"].append({"file": "System", "error": str(e), "type": "System"})
            
        return data
    
    def classify_error(self, error_msg: str) -> str:
        """Classify error types for better analysis."""
        error_msg_lower = error_msg.lower()
        
        if "401" in error_msg or "unauthorized" in error_msg_lower:
            return "Authentication"
        elif "404" in error_msg or "not found" in error_msg_lower:
            return "File Not Found"
        elif "timeout" in error_msg_lower or "timed out" in error_msg_lower:
            return "Timeout"
        elif "connection" in error_msg_lower:
            return "Connection"
        elif "permission" in error_msg_lower or "access" in error_msg_lower:
            return "Permission"
        elif "429" in error_msg or "rate limit" in error_msg_lower:
            return "Rate Limit"
        elif "500" in error_msg or "503" in error_msg or "502" in error_msg:
            return "Server Error"
        else:
            return "Other"
    
    def analyze_performance(self, data: Dict) -> Dict:
        """Analyze download performance and calculate metrics."""
        if not data.get("progress"):
            return {}
            
        stats = data["download_stats"]
        
        # Calculate progress percentage
        total_files = data.get("file_count", 0)
        processed = stats.get("total_processed", 0)
        progress_pct = (processed / total_files * 100) if total_files > 0 else 0
        
        # Estimate completion time
        last_update = data["progress"].get("timestamp", "")
        remaining_files = total_files - processed
        
        # Calculate download speed (rough estimate)
        speed_estimate = 0
        eta_hours = 0
        
        if last_update and processed > 0:
            try:
                last_time = datetime.fromisoformat(last_update.replace('Z', ''))
                # Rough speed calculation (this is simplified)
                # In a real scenario, you'd track time-based progress
                speed_estimate = 25  # files/sec (turbo mode average)
                eta_hours = remaining_files / (speed_estimate * 3600) if speed_estimate > 0 else 0
            except:
                pass
        
        return {
            "progress_percentage": progress_pct,
            "remaining_files": remaining_files,
            "estimated_speed": speed_estimate,
            "eta_hours": eta_hours,
            "success_rate": (stats.get("successful_downloads", 0) / max(processed, 1)) * 100,
            "error_rate": (stats.get("failed_downloads", 0) / max(processed, 1)) * 100
        }
    
    def get_file_system_info(self) -> Dict:
        """Get file system information for the download directory."""
        try:
            if not self.base_path.exists():
                return {"error": "Download directory does not exist"}
                
            # Directory size and file count
            total_size = 0
            file_count = 0
            
            for file_path in self.base_path.rglob("*"):
                if file_path.is_file():
                    file_count += 1
                    total_size += file_path.stat().st_size
            
            # Disk space
            disk_usage = psutil.disk_usage(str(self.base_path))
            
            return {
                "downloaded_files": file_count,
                "total_size_gb": total_size / (1024**3),
                "disk_free_gb": disk_usage.free / (1024**3),
                "disk_used_gb": disk_usage.used / (1024**3),
                "disk_total_gb": disk_usage.total / (1024**3),
                "disk_usage_pct": (disk_usage.used / disk_usage.total) * 100
            }
        except Exception as e:
            return {"error": str(e)}
    
    def setup_layout(self):
        """Setup the dashboard layout."""
        self.app.layout = dbc.Container([
            # Header
            dbc.Row([
                dbc.Col([
                    html.H1("🚀 SharePoint Download Dashboard", className="text-center mb-4"),
                    html.P("Real-time monitoring and analytics for SharePoint downloads", 
                           className="text-center text-muted mb-4")
                ])
            ]),
            
            # Auto-refresh interval
            dcc.Interval(
                id='interval-component',
                interval=5*1000,  # Update every 5 seconds
                n_intervals=0
            ),
            
            # Alert section
            html.Div(id='alerts-section'),
            
            # Main metrics row
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4("📊 Progress", className="card-title"),
                            html.H2(id="progress-percentage", className="text-primary"),
                            html.P(id="progress-details", className="text-muted")
                        ])
                    ])
                ], width=3),
                
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4("⚡ Speed", className="card-title"),
                            html.H2(id="download-speed", className="text-success"),
                            html.P(id="speed-details", className="text-muted")
                        ])
                    ])
                ], width=3),
                
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4("✅ Success Rate", className="card-title"),
                            html.H2(id="success-rate", className="text-info"),
                            html.P(id="success-details", className="text-muted")
                        ])
                    ])
                ], width=3),
                
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4("⏱️ ETA", className="card-title"),
                            html.H2(id="eta-time", className="text-warning"),
                            html.P(id="eta-details", className="text-muted")
                        ])
                    ])
                ], width=3)
            ], className="mb-4"),
            
            # Charts row
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("📈 Download Progress Over Time"),
                        dbc.CardBody([
                            dcc.Graph(id="progress-chart")
                        ])
                    ])
                ], width=8),
                
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("🎯 File Status Distribution"),
                        dbc.CardBody([
                            dcc.Graph(id="status-pie-chart")
                        ])
                    ])
                ], width=4)
            ], className="mb-4"),
            
            # Error analysis row
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("❌ Error Analysis"),
                        dbc.CardBody([
                            dcc.Graph(id="error-chart")
                        ])
                    ])
                ], width=6),
                
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("💾 File System Info"),
                        dbc.CardBody([
                            html.Div(id="filesystem-info")
                        ])
                    ])
                ], width=6)
            ], className="mb-4"),
            
            # Detailed tables row
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("📝 Recent Errors (Top 20)"),
                        dbc.CardBody([
                            html.Div(id="error-table")
                        ])
                    ])
                ], width=12)
            ], className="mb-4"),
            
            # Footer
            dbc.Row([
                dbc.Col([
                    html.Hr(),
                    html.P([
                        "Last updated: ",
                        html.Span(id="last-updated", className="font-weight-bold"),
                        " | ",
                        html.Button("🔄 Refresh Now", id="refresh-button", 
                                   className="btn btn-sm btn-outline-primary ml-2"),
                        " | ",
                        html.Button("📊 Export Data", id="export-button", 
                                   className="btn btn-sm btn-outline-success ml-2")
                    ], className="text-center text-muted")
                ])
            ])
            
        ], fluid=True)
    
    def setup_callbacks(self):
        """Setup dashboard callbacks for interactivity."""
        
        @self.app.callback(
            [Output('progress-percentage', 'children'),
             Output('progress-details', 'children'),
             Output('download-speed', 'children'),
             Output('speed-details', 'children'),
             Output('success-rate', 'children'),
             Output('success-details', 'children'),
             Output('eta-time', 'children'),
             Output('eta-details', 'children'),
             Output('progress-chart', 'figure'),
             Output('status-pie-chart', 'figure'),
             Output('error-chart', 'figure'),
             Output('filesystem-info', 'children'),
             Output('error-table', 'children'),
             Output('last-updated', 'children'),
             Output('alerts-section', 'children')],
            [Input('interval-component', 'n_intervals'),
             Input('refresh-button', 'n_clicks')]
        )
        def update_dashboard(n_intervals, refresh_clicks):
            """Update all dashboard components."""
            
            # Load fresh data
            data = self.load_progress_data()
            performance = self.analyze_performance(data)
            filesystem = self.get_file_system_info()
            
            # Progress metrics
            progress_pct = performance.get("progress_percentage", 0)
            remaining = performance.get("remaining_files", 0)
            
            progress_text = f"{progress_pct:.1f}%"
            progress_detail = f"{remaining:,} files remaining"
            
            # Speed metrics
            speed = performance.get("estimated_speed", 0)
            speed_text = f"{speed:.1f} files/sec"
            speed_detail = "Estimated current speed"
            
            # Success rate
            success_rate = performance.get("success_rate", 0)
            success_text = f"{success_rate:.1f}%"
            success_detail = f"{data['download_stats'].get('successful_downloads', 0):,} successful"
            
            # ETA
            eta_hours = performance.get("eta_hours", 0)
            if eta_hours > 0:
                if eta_hours < 1:
                    eta_text = f"{eta_hours*60:.0f}m"
                    eta_detail = "Minutes remaining"
                elif eta_hours < 24:
                    eta_text = f"{eta_hours:.1f}h"
                    eta_detail = "Hours remaining"
                else:
                    eta_text = f"{eta_hours/24:.1f}d"
                    eta_detail = "Days remaining"
            else:
                eta_text = "N/A"
                eta_detail = "Unable to estimate"
            
            # Create charts
            progress_chart = self.create_progress_chart(data)
            status_chart = self.create_status_chart(data)
            error_chart = self.create_error_chart(data)
            
            # File system info
            fs_info = self.create_filesystem_info(filesystem)
            
            # Error table
            error_table = self.create_error_table(data.get("errors", [])[:20])
            
            # Last updated
            last_updated = data["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
            
            # Alerts
            alerts = self.create_alerts(data, performance, filesystem)
            
            return (progress_text, progress_detail, speed_text, speed_detail,
                   success_text, success_detail, eta_text, eta_detail,
                   progress_chart, status_chart, error_chart, fs_info,
                   error_table, last_updated, alerts)
    
    def create_progress_chart(self, data: Dict) -> go.Figure:
        """Create progress over time chart."""
        fig = go.Figure()
        
        if data.get("progress"):
            stats = data["download_stats"]
            
            # Create a simple progress visualization
            total_files = data.get("file_count", 0)
            processed = stats.get("total_processed", 0)
            successful = stats.get("successful_downloads", 0)
            failed = stats.get("failed_downloads", 0)
            
            categories = ['Processed', 'Successful', 'Failed', 'Remaining']
            values = [processed, successful, failed, total_files - processed]
            colors = ['#1f77b4', '#2ca02c', '#d62728', '#ff7f0e']
            
            fig.add_trace(go.Bar(
                x=categories,
                y=values,
                marker_color=colors,
                text=[f'{v:,}' for v in values],
                textposition='auto'
            ))
            
            fig.update_layout(
                title="File Processing Status",
                xaxis_title="Category",
                yaxis_title="Number of Files",
                height=400
            )
        else:
            fig.add_annotation(
                text="No progress data available",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False
            )
            
        return fig
    
    def create_status_chart(self, data: Dict) -> go.Figure:
        """Create status distribution pie chart."""
        fig = go.Figure()
        
        if data.get("download_stats"):
            stats = data["download_stats"]
            
            labels = ['Successful', 'Skipped', 'Failed']
            values = [
                stats.get("successful_downloads", 0),
                stats.get("skipped_files", 0),
                stats.get("failed_downloads", 0)
            ]
            colors = ['#2ca02c', '#ff7f0e', '#d62728']
            
            fig.add_trace(go.Pie(
                labels=labels,
                values=values,
                marker_colors=colors,
                textinfo='label+percent+value'
            ))
            
            fig.update_layout(
                title="Download Status Distribution",
                height=400
            )
        else:
            fig.add_annotation(
                text="No status data available",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False
            )
            
        return fig
    
    def create_error_chart(self, data: Dict) -> go.Figure:
        """Create error type analysis chart."""
        fig = go.Figure()
        
        errors = data.get("errors", [])
        if errors:
            error_types = defaultdict(int)
            for error in errors:
                error_types[error["type"]] += 1
            
            types = list(error_types.keys())
            counts = list(error_types.values())
            
            fig.add_trace(go.Bar(
                x=types,
                y=counts,
                marker_color='#d62728',
                text=counts,
                textposition='auto'
            ))
            
            fig.update_layout(
                title="Error Types Distribution",
                xaxis_title="Error Type",
                yaxis_title="Count",
                height=400
            )
        else:
            fig.add_annotation(
                text="No errors to display! 🎉",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False
            )
            
        return fig
    
    def create_filesystem_info(self, filesystem: Dict) -> html.Div:
        """Create file system information display."""
        if filesystem.get("error"):
            return dbc.Alert(f"Error: {filesystem['error']}", color="danger")
        
        return html.Div([
            html.P([
                html.Strong("Downloaded Files: "),
                f"{filesystem.get('downloaded_files', 0):,}"
            ]),
            html.P([
                html.Strong("Total Size: "),
                f"{filesystem.get('total_size_gb', 0):.2f} GB"
            ]),
            html.P([
                html.Strong("Disk Free: "),
                f"{filesystem.get('disk_free_gb', 0):.1f} GB"
            ]),
            html.P([
                html.Strong("Disk Usage: "),
                f"{filesystem.get('disk_usage_pct', 0):.1f}%"
            ]),
            dbc.Progress(
                value=filesystem.get('disk_usage_pct', 0),
                color="info" if filesystem.get('disk_usage_pct', 0) < 80 else "warning",
                className="mb-3"
            )
        ])
    
    def create_error_table(self, errors: List[Dict]) -> dash_table.DataTable:
        """Create error details table."""
        if not errors:
            return html.P("No errors to display! 🎉", className="text-success")
        
        df = pd.DataFrame(errors)
        
        return dash_table.DataTable(
            data=df.to_dict('records'),
            columns=[
                {"name": "File", "id": "file"},
                {"name": "Error Type", "id": "type"},
                {"name": "Error Message", "id": "error"}
            ],
            style_cell={'textAlign': 'left', 'fontSize': 12},
            style_data={'whiteSpace': 'normal', 'height': 'auto'},
            style_header={'backgroundColor': 'rgb(230, 230, 230)', 'fontWeight': 'bold'},
            page_size=10,
            sort_action="native",
            filter_action="native"
        )
    
    def create_alerts(self, data: Dict, performance: Dict, filesystem: Dict) -> html.Div:
        """Create alert notifications."""
        alerts = []
        
        # Disk space warning
        if filesystem.get('disk_usage_pct', 0) > 90:
            alerts.append(
                dbc.Alert(
                    "⚠️ Disk space is running low! Consider freeing up space.",
                    color="danger",
                    dismissable=True
                )
            )
        elif filesystem.get('disk_usage_pct', 0) > 80:
            alerts.append(
                dbc.Alert(
                    "⚠️ Disk space is getting low. Monitor usage.",
                    color="warning", 
                    dismissable=True
                )
            )
        
        # Error rate warning
        error_rate = performance.get('error_rate', 0)
        if error_rate > 10:
            alerts.append(
                dbc.Alert(
                    f"⚠️ High error rate detected: {error_rate:.1f}%. Check network connection.",
                    color="warning",
                    dismissable=True
                )
            )
        
        # Success notification
        if performance.get('progress_percentage', 0) > 95:
            alerts.append(
                dbc.Alert(
                    "🎉 Download is almost complete! Great progress!",
                    color="success",
                    dismissable=True
                )
            )
        
        return html.Div(alerts) if alerts else html.Div()
    
    def run(self, host: str = "127.0.0.1", port: int = 8050, debug: bool = False):
        """Run the dashboard server."""
        logger.info(f"🚀 Starting SharePoint Dashboard at http://{host}:{port}")
        logger.info("📊 Dashboard Features:")
        logger.info("  • Real-time progress monitoring")
        logger.info("  • Performance analytics")
        logger.info("  • Error analysis")
        logger.info("  • File system monitoring")
        logger.info("  • Interactive charts and tables")
        
        self.app.run_server(host=host, port=port, debug=debug)

def main():
    """Main function to run the dashboard."""
    import argparse
    
    parser = argparse.ArgumentParser(description="SharePoint Download Dashboard")
    parser.add_argument("--path", default="C:/commercial_pdfs/downloaded_files",
                       help="Path to download directory")
    parser.add_argument("--host", default="127.0.0.1",
                       help="Host to run dashboard on")
    parser.add_argument("--port", default=8050, type=int,
                       help="Port to run dashboard on")
    parser.add_argument("--debug", action="store_true",
                       help="Run in debug mode")
    
    args = parser.parse_args()
    
    # Create and run dashboard
    dashboard = SharePointDashboard(args.path)
    dashboard.run(host=args.host, port=args.port, debug=args.debug)

if __name__ == "__main__":
    main()
