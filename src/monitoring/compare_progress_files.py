#!/usr/bin/env python3
import json
import os
from datetime import datetime

progress_files = [
    'C:/commercial_pdfs/downloaded_files/download_progress.json',
    'C:/commercial_pdfs/downloaded_files/download_progress_turbo.json',
    'C:/commercial_pdfs/downloaded_files/download_progress_turbo_backup_20250807_234632.json',
    'C:/commercial_pdfs/downloaded_files/download_progress_turbo_backup_20250807_235850.json'
]

print("=== PROGRESS FILES COMPARISON ===\n")

for file_path in progress_files:
    if os.path.exists(file_path):
        try:
            file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
            mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            filename = os.path.basename(file_path)
            print(f"📁 {filename}")
            print(f"   Size: {file_size:.1f} MB")
            print(f"   Modified: {mod_time}")
            print(f"   Last processed index: {data.get('last_processed_index', 'N/A')}")
            print(f"   Success count: {len(data.get('results', {}).get('success', []))}")
            print(f"   Failed count: {len(data.get('results', {}).get('failed', []))}")
            
            # Check how many are actually downloaded vs skipped
            success_list = data.get('results', {}).get('success', [])
            downloaded = sum(1 for item in success_list if not item.get('skipped', False))
            skipped = sum(1 for item in success_list if item.get('skipped', False))
            
            print(f"   Actually downloaded: {downloaded}")
            print(f"   Skipped (already existed): {skipped}")
            
            # Check for timestamp
            if 'timestamp' in data:
                print(f"   Last update: {data['timestamp']}")
            
            # Check for turbo mode indication
            if 'turbo_mode' in data:
                print(f"   Turbo mode: {data['turbo_mode']}")
                
            print(f"   Progress: {(data.get('last_processed_index', 0) / 376882) * 100:.1f}%")
            print()
            
        except Exception as e:
            print(f"❌ Error reading {file_path}: {e}\n")
    else:
        print(f"❌ File not found: {file_path}\n")

print("=== ANALYSIS ===")
print("It appears there are multiple progress tracking systems:")
print("1. 'download_progress.json' - Original/legacy tracking")
print("2. 'download_progress_turbo.json' - Turbo mode tracking") 
print("3. Backup files - Automated backups of turbo progress")
print("\nThe dashboard should use the most recent/active file.")
