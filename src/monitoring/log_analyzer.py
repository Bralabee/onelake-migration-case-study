#!/usr/bin/env python3
"""
📊 Log Analyzer for SharePoint Downloads
========================================

Comprehensive log analysis tool for monitoring download performance,
error patterns, and system insights.

Features:
- Real-time log parsing
- Performance metrics extraction
- Error pattern analysis
- Speed calculations
- Timeline analysis
- Export capabilities

Author: GitHub Copilot
Date: August 7, 2025
"""

import re
import json
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, List, Any, Tuple
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

class LogAnalyzer:
    """Comprehensive log analyzer for SharePoint downloads."""
    
    def __init__(self, log_paths: List[str] = None):
        self.log_paths = log_paths or [
            "*.log",
            "../logs/*.log", 
            "../../logs/*.log"
        ]
        
        # Log patterns for parsing
        self.patterns = {
            'timestamp': r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})',
            'level': r'- (INFO|WARNING|ERROR|DEBUG) -',
            'turbo_progress': r'🔥 TURBO Progress: (\d+)/(\d+) \((\d+\.?\d*)%\) - (\d+) new downloads',
            'speed': r'🚀 Speed: ([\d\.]+) files/sec',
            'eta': r'ETA: ([\d\.]+) hours',
            'download_success': r'✅ Downloaded: (.+)',
            'download_failed': r'❌ (.+) failed for (.+): (.+)',
            'auth_token': r'🔐 .*Authenticating',
            'folder_processing': r'📁 Processing folder: (.+)',
            'turbo_mode': r'🚀 TURBO MODE: Using (\d+) parallel workers',
            'resume': r'📂 TURBO: Resuming from file (\d+)/(\d+)',
        }
        
    def find_log_files(self) -> List[Path]:
        """Find all log files matching the patterns."""
        log_files = []
        base_path = Path.cwd()
        
        for pattern in self.log_paths:
            log_files.extend(base_path.glob(pattern))
            
        return sorted(log_files, key=lambda x: x.stat().st_mtime, reverse=True)
    
    def parse_log_file(self, log_file: Path) -> List[Dict]:
        """Parse a single log file and extract structured data."""
        events = []
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    event = self.parse_log_line(line.strip(), line_num)
                    if event:
                        event['file'] = str(log_file)
                        events.append(event)
                        
        except Exception as e:
            print(f"Error reading {log_file}: {e}")
            
        return events
    
    def parse_log_line(self, line: str, line_num: int) -> Dict:
        """Parse a single log line and extract information."""
        if not line:
            return None
            
        event = {
            'line_number': line_num,
            'raw_line': line,
            'timestamp': None,
            'level': None,
            'message': line,
            'event_type': 'unknown',
            'data': {}
        }
        
        # Extract timestamp
        timestamp_match = re.search(self.patterns['timestamp'], line)
        if timestamp_match:
            try:
                event['timestamp'] = datetime.strptime(
                    timestamp_match.group(1), 
                    '%Y-%m-%d %H:%M:%S,%f'
                )
            except:
                pass
        
        # Extract log level
        level_match = re.search(self.patterns['level'], line)
        if level_match:
            event['level'] = level_match.group(1)
        
        # Parse specific event types
        for event_type, pattern in self.patterns.items():
            if event_type in ['timestamp', 'level']:
                continue
                
            match = re.search(pattern, line)
            if match:
                event['event_type'] = event_type
                event['data'] = self.extract_event_data(event_type, match)
                break
        
        return event
    
    def extract_event_data(self, event_type: str, match) -> Dict:
        """Extract specific data based on event type."""
        data = {}
        
        if event_type == 'turbo_progress':
            data = {
                'current': int(match.group(1)),
                'total': int(match.group(2)),
                'percentage': float(match.group(3)),
                'new_downloads': int(match.group(4))
            }
        elif event_type == 'speed':
            data = {'files_per_sec': float(match.group(1))}
        elif event_type == 'eta':
            data = {'eta_hours': float(match.group(1))}
        elif event_type == 'download_success':
            data = {'file_path': match.group(1)}
        elif event_type == 'download_failed':
            data = {
                'error_type': match.group(1),
                'file_path': match.group(2),
                'error_message': match.group(3)
            }
        elif event_type == 'folder_processing':
            data = {'folder_path': match.group(1)}
        elif event_type == 'turbo_mode':
            data = {'workers': int(match.group(1))}
        elif event_type == 'resume':
            data = {
                'resume_from': int(match.group(1)),
                'total_files': int(match.group(2))
            }
        
        return data
    
    def analyze_logs(self) -> Dict[str, Any]:
        """Perform comprehensive log analysis."""
        log_files = self.find_log_files()
        all_events = []
        
        print(f"📊 Analyzing {len(log_files)} log files...")
        
        for log_file in log_files:
            events = self.parse_log_file(log_file)
            all_events.extend(events)
            print(f"  • {log_file.name}: {len(events)} events")
        
        if not all_events:
            return {"error": "No log events found"}
        
        # Perform analysis
        analysis = {
            'summary': self.analyze_summary(all_events),
            'performance': self.analyze_performance(all_events),
            'errors': self.analyze_errors(all_events),
            'timeline': self.analyze_timeline(all_events),
            'patterns': self.analyze_patterns(all_events)
        }
        
        return analysis
    
    def analyze_summary(self, events: List[Dict]) -> Dict:
        """Analyze overall summary statistics."""
        total_events = len(events)
        
        # Event type distribution
        event_types = Counter(event['event_type'] for event in events)
        
        # Log level distribution
        log_levels = Counter(event['level'] for event in events if event['level'])
        
        # Time range
        timestamps = [e['timestamp'] for e in events if e['timestamp']]
        time_range = None
        if timestamps:
            time_range = {
                'start': min(timestamps),
                'end': max(timestamps),
                'duration_hours': (max(timestamps) - min(timestamps)).total_seconds() / 3600
            }
        
        return {
            'total_events': total_events,
            'event_types': dict(event_types),
            'log_levels': dict(log_levels),
            'time_range': time_range
        }
    
    def analyze_performance(self, events: List[Dict]) -> Dict:
        """Analyze download performance metrics."""
        speed_events = [e for e in events if e['event_type'] == 'speed']
        progress_events = [e for e in events if e['event_type'] == 'turbo_progress']
        
        performance = {
            'speed_samples': len(speed_events),
            'progress_samples': len(progress_events)
        }
        
        if speed_events:
            speeds = [e['data']['files_per_sec'] for e in speed_events]
            performance.update({
                'avg_speed': sum(speeds) / len(speeds),
                'max_speed': max(speeds),
                'min_speed': min(speeds),
                'speed_trend': speeds  # For plotting
            })
        
        if progress_events:
            latest_progress = progress_events[-1]['data']
            performance.update({
                'current_progress': latest_progress['percentage'],
                'files_processed': latest_progress['current'],
                'total_files': latest_progress['total']
            })
        
        return performance
    
    def analyze_errors(self, events: List[Dict]) -> Dict:
        """Analyze error patterns and types."""
        error_events = [e for e in events if e['level'] == 'ERROR' or 'failed' in e.get('raw_line', '').lower()]
        
        error_analysis = {
            'total_errors': len(error_events),
            'error_timeline': []
        }
        
        if error_events:
            # Error type classification
            error_types = defaultdict(list)
            for event in error_events:
                if event['event_type'] == 'download_failed':
                    error_type = self.classify_error(event['data'].get('error_message', ''))
                    error_types[error_type].append(event)
                else:
                    error_types['Other'].append(event)
            
            error_analysis['error_types'] = {
                k: len(v) for k, v in error_types.items()
            }
            
            # Error timeline
            error_analysis['error_timeline'] = [
                {
                    'timestamp': e['timestamp'],
                    'type': e['event_type'],
                    'message': e['raw_line'][:100] + '...' if len(e['raw_line']) > 100 else e['raw_line']
                }
                for e in error_events[-20:]  # Last 20 errors
                if e['timestamp']
            ]
        
        return error_analysis
    
    def classify_error(self, error_msg: str) -> str:
        """Classify error types."""
        error_msg_lower = error_msg.lower()
        
        if "401" in error_msg or "unauthorized" in error_msg_lower:
            return "Authentication"
        elif "404" in error_msg or "not found" in error_msg_lower:
            return "File Not Found"
        elif "timeout" in error_msg_lower:
            return "Timeout"
        elif "connection" in error_msg_lower:
            return "Connection"
        elif "429" in error_msg:
            return "Rate Limit"
        elif "500" in error_msg or "503" in error_msg:
            return "Server Error"
        else:
            return "Other"
    
    def analyze_timeline(self, events: List[Dict]) -> List[Dict]:
        """Create timeline analysis."""
        timeline_events = [e for e in events if e['timestamp'] and e['event_type'] != 'unknown']
        timeline_events.sort(key=lambda x: x['timestamp'])
        
        timeline = []
        for event in timeline_events[-50:]:  # Last 50 significant events
            timeline.append({
                'timestamp': event['timestamp'].isoformat(),
                'event_type': event['event_type'],
                'level': event['level'],
                'summary': self.create_event_summary(event)
            })
        
        return timeline
    
    def create_event_summary(self, event: Dict) -> str:
        """Create a human-readable summary of an event."""
        event_type = event['event_type']
        data = event['data']
        
        if event_type == 'turbo_progress':
            return f"Progress: {data['percentage']:.1f}% ({data['current']:,}/{data['total']:,})"
        elif event_type == 'speed':
            return f"Speed: {data['files_per_sec']:.1f} files/sec"
        elif event_type == 'download_success':
            return f"Downloaded: {Path(data['file_path']).name}"
        elif event_type == 'download_failed':
            return f"Failed: {Path(data['file_path']).name} - {data['error_type']}"
        elif event_type == 'turbo_mode':
            return f"Started with {data['workers']} workers"
        elif event_type == 'resume':
            return f"Resumed from file {data['resume_from']:,}"
        else:
            return event['raw_line'][:100]
    
    def analyze_patterns(self, events: List[Dict]) -> Dict:
        """Analyze patterns in the logs."""
        patterns = {}
        
        # Download patterns by hour
        download_events = [e for e in events if e['event_type'] == 'download_success' and e['timestamp']]
        if download_events:
            hourly_downloads = defaultdict(int)
            for event in download_events:
                hour = event['timestamp'].strftime('%H:00')
                hourly_downloads[hour] += 1
            patterns['hourly_activity'] = dict(hourly_downloads)
        
        # Common error patterns
        error_events = [e for e in events if 'failed' in e.get('raw_line', '').lower()]
        if error_events:
            error_messages = [e['raw_line'] for e in error_events]
            # Simple pattern detection (could be enhanced)
            patterns['common_errors'] = Counter(error_messages).most_common(5)
        
        return patterns
    
    def create_performance_chart(self, analysis: Dict) -> go.Figure:
        """Create performance visualization."""
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=['Speed Over Time', 'Progress Timeline', 'Error Distribution', 'Hourly Activity'],
            specs=[[{"secondary_y": False}, {"secondary_y": False}],
                   [{"type": "pie"}, {"type": "bar"}]]
        )
        
        performance = analysis.get('performance', {})
        
        # Speed chart
        if 'speed_trend' in performance:
            speeds = performance['speed_trend']
            fig.add_trace(
                go.Scatter(
                    y=speeds,
                    mode='lines+markers',
                    name='Download Speed',
                    line=dict(color='blue')
                ),
                row=1, col=1
            )
        
        # Progress chart (simplified)
        if 'current_progress' in performance:
            progress = performance['current_progress']
            fig.add_trace(
                go.Indicator(
                    mode="gauge+number",
                    value=progress,
                    title={'text': "Progress %"},
                    gauge={'axis': {'range': [None, 100]},
                           'bar': {'color': "darkblue"},
                           'bgcolor': "white",
                           'borderwidth': 2,
                           'bordercolor': "gray"}
                ),
                row=1, col=2
            )
        
        # Error distribution
        errors = analysis.get('errors', {})
        if 'error_types' in errors and errors['error_types']:
            labels = list(errors['error_types'].keys())
            values = list(errors['error_types'].values())
            fig.add_trace(
                go.Pie(labels=labels, values=values, name="Errors"),
                row=2, col=1
            )
        
        # Hourly activity
        patterns = analysis.get('patterns', {})
        if 'hourly_activity' in patterns:
            hours = list(patterns['hourly_activity'].keys())
            counts = list(patterns['hourly_activity'].values())
            fig.add_trace(
                go.Bar(x=hours, y=counts, name="Downloads"),
                row=2, col=2
            )
        
        fig.update_layout(height=800, title_text="SharePoint Download Analysis")
        return fig
    
    def export_analysis(self, analysis: Dict, output_file: str = "log_analysis.json"):
        """Export analysis results to file."""
        # Convert datetime objects to strings for JSON serialization
        def json_serialize(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Object {obj} is not JSON serializable")
        
        with open(output_file, 'w') as f:
            json.dump(analysis, f, indent=2, default=json_serialize)
        
        print(f"📊 Analysis exported to {output_file}")

def main():
    """Main function for log analysis."""
    import argparse
    
    parser = argparse.ArgumentParser(description="SharePoint Download Log Analyzer")
    parser.add_argument("--logs", nargs="+", help="Log file paths or patterns")
    parser.add_argument("--export", help="Export results to file")
    parser.add_argument("--chart", action="store_true", help="Generate performance chart")
    
    args = parser.parse_args()
    
    # Create analyzer
    analyzer = LogAnalyzer(args.logs)
    
    # Perform analysis
    print("🔍 Starting log analysis...")
    analysis = analyzer.analyze_logs()
    
    if "error" in analysis:
        print(f"❌ {analysis['error']}")
        return
    
    # Display results
    print("\n📊 ANALYSIS RESULTS")
    print("=" * 50)
    
    summary = analysis['summary']
    print(f"📈 Total Events: {summary['total_events']:,}")
    
    if summary['time_range']:
        time_range = summary['time_range']
        print(f"⏱️  Time Range: {time_range['start']} to {time_range['end']}")
        print(f"⏱️  Duration: {time_range['duration_hours']:.1f} hours")
    
    performance = analysis['performance']
    if 'avg_speed' in performance:
        print(f"⚡ Average Speed: {performance['avg_speed']:.1f} files/sec")
        print(f"⚡ Max Speed: {performance['max_speed']:.1f} files/sec")
    
    if 'current_progress' in performance:
        print(f"📊 Progress: {performance['current_progress']:.1f}%")
        print(f"📁 Files Processed: {performance['files_processed']:,}/{performance['total_files']:,}")
    
    errors = analysis['errors']
    print(f"❌ Total Errors: {errors['total_errors']:,}")
    
    if 'error_types' in errors:
        print("📋 Error Types:")
        for error_type, count in errors['error_types'].items():
            print(f"  • {error_type}: {count}")
    
    # Export if requested
    if args.export:
        analyzer.export_analysis(analysis, args.export)
    
    # Generate chart if requested
    if args.chart:
        try:
            fig = analyzer.create_performance_chart(analysis)
            fig.show()
        except Exception as e:
            print(f"⚠️ Could not generate chart: {e}")

if __name__ == "__main__":
    main()
