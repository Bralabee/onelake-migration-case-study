#!/usr/bin/env python3
"""
📊 Retry Progress Monitor
========================

Monitor the progress of failed file retry attempts.
This script watches the progress file and reports on retry status.

Author: GitHub Copilot
Date: August 8, 2025
"""

import json
import time
import os
from datetime import datetime
from pathlib import Path

def monitor_retry_progress():
    """Monitor the retry progress by watching the progress file."""
    # Try multiple progress file candidates
    base_path = Path("C:/commercial_pdfs/downloaded_files")
    candidates = [
        base_path / "download_progress_turbo.json",
        base_path / "download_progress_turbo_backup_20250808_022130.json",
        base_path / "download_progress_turbo_backup_20250808_015125.json", 
        base_path / "download_progress_turbo_backup_20250807_235850.json",
        base_path / "download_progress.json"
    ]
    
    progress_file = None
    for candidate in candidates:
        if candidate.exists():
            progress_file = candidate
            print(f"📁 Using progress file: {candidate.name}")
            break
    
    if not progress_file:
        print("❌ No progress file found!")
        print("Available files:")
        for f in base_path.glob("download_progress*"):
            print(f"  - {f.name}")
        return
    
    print("🔄 Monitoring retry progress...")
    print("Press Ctrl+C to stop monitoring\n")
    
    last_stats = None
    
    try:
        while True:
            # Load current stats
            with open(progress_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            success_count = len(data.get('results', {}).get('success', []))
            failed_count = len(data.get('results', {}).get('failed', []))
            total_files = data.get('total_count', success_count + failed_count)
            
            current_stats = {
                'success': success_count,
                'failed': failed_count,
                'total': total_files,
                'completion': (success_count / total_files * 100) if total_files > 0 else 0
            }
            
            # Show progress
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] 📊 Status: {success_count:,} success | {failed_count:,} failed | {current_stats['completion']:.1f}% complete")
            
            # Show changes if we have previous stats
            if last_stats:
                success_change = current_stats['success'] - last_stats['success']
                failed_change = current_stats['failed'] - last_stats['failed']
                
                if success_change > 0 or failed_change != 0:
                    print(f"           📈 Changes: +{success_change} success, {failed_change:+} failed")
            
            last_stats = current_stats
            
            # Check if retry is complete (no change for 30 seconds)
            time.sleep(10)
            
    except KeyboardInterrupt:
        print("\n🛑 Monitoring stopped by user")
    except Exception as e:
        print(f"❌ Error monitoring: {e}")

if __name__ == "__main__":
    monitor_retry_progress()
