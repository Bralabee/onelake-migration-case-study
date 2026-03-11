#!/usr/bin/env python3
import json
import sys
sys.path.append('.')
try:
    from src.monitoring.simple_dashboard import SimpleProgressMonitor
except ModuleNotFoundError:
    from simple_dashboard import SimpleProgressMonitor

# Test detailed insights
monitor = SimpleProgressMonitor("C:/commercial_pdfs/downloaded_files")
data = monitor.load_data()

if 'progress' in data:
    results = data['progress'].get('results', {})
    success_files = results.get('success', [])
    failed_files = results.get('failed', [])
    
    insights = monitor.generate_file_insights(success_files, failed_files)
    
    print("=== DETAILED INSIGHTS ANALYSIS ===")
    print(f"\n📁 File Types ({len(insights.get('file_types', {}))} types):")
    for ext, count in list(insights.get('file_types', {}).items())[:5]:
        print(f"  {ext}: {count:,} files")
    
    print(f"\n📂 Top Folders ({len(insights.get('top_folders', []))} folders):")
    for folder in insights.get('top_folders', [])[:5]:
        print(f"  {folder['name']}: {folder['count']:,} files")
    
    print(f"\n📊 Size Distribution:")
    size_dist = insights.get('size_distribution', {})
    for category, count in size_dist.items():
        print(f"  {category}: {count:,} files")
    
    print(f"\n⏰ Download Timeline:")
    timeline = insights.get('download_timeline', {})
    for period, count in timeline.items():
        print(f"  {period}: {count:,} files")
    
    print(f"\n❌ Failure Analysis:")
    failures = insights.get('failure_analysis', {})
    for error_type, count in failures.items():
        print(f"  {error_type}: {count} files")
    
    print(f"\n📈 Summary:")
    summary = insights.get('summary', {})
    for key, value in summary.items():
        print(f"  {key}: {value}")
    
    print(f"\n🔍 Sample Recent Downloads:")
    recent = insights.get('recent_downloads', [])[:3]
    for download in recent:
        print(f"  {download.get('path', 'Unknown')[:60]}... ({download.get('size_mb', 0)} MB)")
