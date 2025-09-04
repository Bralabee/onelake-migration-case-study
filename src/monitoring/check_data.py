#!/usr/bin/env python3
import json

# Load progress data
with open('C:/commercial_pdfs/downloaded_files/download_progress.json', 'r') as f:
    progress = json.load(f)

# Load cache data header
with open('C:/commercial_pdfs/downloaded_files/file_list_cache.json', 'r') as f:
    cache_start = f.read(1000)  # Read first 1000 chars
    f.seek(0)
    # Try to get just the basic structure
    for line_num, line in enumerate(f):
        if line_num > 20:  # Stop after first few lines to avoid memory issues
            break
        if '"timestamp"' in line:
            print(f"Cache timestamp line: {line.strip()}")
        if '"site_id"' in line:
            print(f"Cache site_id line: {line.strip()}")

print("=== ACTUAL DATA STATISTICS ===")
print(f"Last processed index: {progress['last_processed_index']}")
print(f"Success count: {len(progress['results']['success'])}")
print(f"Failed count: {len(progress['results']['failed'])}")

# Check how many are actually downloaded vs skipped
downloaded = 0
skipped = 0
for item in progress['results']['success']:
    if item.get('skipped', False):
        skipped += 1
    else:
        downloaded += 1

print(f"Actually downloaded: {downloaded}")
print(f"Skipped (already existed): {skipped}")
print(f"Progress percentage: {(progress['last_processed_index'] / 376882) * 100:.1f}%")

# Check timestamp
if 'timestamp' in progress:
    print(f"Last update: {progress['timestamp']}")
else:
    print("No timestamp in progress file")
