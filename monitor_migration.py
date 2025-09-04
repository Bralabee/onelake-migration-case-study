#!/usr/bin/env python3
"""
Migration Progress Monitor
Tracks the progress of the OneLake migration in real-time
"""

import json
import time
import os
from datetime import datetime, timedelta

def load_progress():
    """Load current migration progress"""
    try:
        with open('migration_progress_production.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return None

def format_number(num):
    """Format number with commas"""
    return f"{num:,}"

def calculate_eta(uploaded, total, start_time, current_time):
    """Calculate estimated time of arrival"""
    if uploaded == 0:
        return "Unknown"
    
    elapsed = current_time - start_time
    rate = uploaded / elapsed if elapsed > 0 else 0
    remaining = total - uploaded
    
    if rate == 0:
        return "Unknown"
    
    eta_seconds = remaining / rate
    eta = datetime.now() + timedelta(seconds=eta_seconds)
    return eta.strftime("%Y-%m-%d %H:%M:%S")

def monitor_migration():
    """Monitor migration progress"""
    print("🔍 OneLake Migration Monitor")
    print("=" * 50)
    
    start_time = time.time()
    last_uploaded = 0
    
    while True:
        try:
            data = load_progress()
            if not data:
                print("❌ Progress file not found")
                time.sleep(5)
                continue
            
            current_time = time.time()
            uploaded = data.get('uploaded_files', 0)
            total = data.get('total_files', 0)
            failed = data.get('failed_files', 0)
            skipped = data.get('skipped_files', 0)
            
            # Calculate progress
            progress_pct = (uploaded / total * 100) if total > 0 else 0
            completed_files = len(data.get('completed_files', {}))
            remaining = total - uploaded - skipped
            
            # Calculate rate
            if uploaded > last_uploaded:
                files_since_last = uploaded - last_uploaded
                rate = files_since_last / 5  # files per second (5 second intervals)
            else:
                rate = 0
            
            # Clear screen and show status
            os.system('cls' if os.name == 'nt' else 'clear')
            
            print("🚀 OneLake Migration - Live Status")
            print("=" * 60)
            print(f"📊 Total Files: {format_number(total)}")
            print(f"✅ Successfully Uploaded: {format_number(uploaded)}")
            print(f"⏭️  Skipped (Already Exists): {format_number(skipped)}")
            print(f"❌ Failed Uploads: {format_number(failed)}")
            print(f"📁 Completed Files: {format_number(completed_files)}")
            print(f"📄 Remaining Files: {format_number(remaining)}")
            print()
            print(f"📈 Progress: {progress_pct:.2f}%")
            print(f"⚡ Current Rate: {rate:.1f} files/second")
            print(f"🕐 ETA: {calculate_eta(uploaded, total, start_time, current_time)}")
            print()
            
            # Progress bar
            bar_length = 40
            filled_length = int(bar_length * progress_pct / 100)
            bar = '█' * filled_length + '░' * (bar_length - filled_length)
            print(f"[{bar}] {progress_pct:.1f}%")
            print()
            
            # Status message
            if remaining == 0:
                print("🎉 MIGRATION COMPLETED SUCCESSFULLY!")
                break
            elif rate > 0:
                print(f"🔄 Migration in progress... ({rate:.1f} files/sec)")
            else:
                print("⏸️ Migration paused or starting...")
            
            print(f"🕐 Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("\nPress Ctrl+C to exit monitor")
            
            last_uploaded = uploaded
            time.sleep(5)  # Update every 5 seconds
            
        except KeyboardInterrupt:
            print("\n👋 Monitor stopped by user")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    monitor_migration()
