#!/usr/bin/env python3
"""
Analyze all available data sources to understand what information we have
"""

import json
import os
from pathlib import Path
from collections import Counter

def analyze_progress_file():
    """Analyze the structure and content of the progress file"""
    progress_file = Path("C:/commercial_pdfs/downloaded_files/download_progress_turbo.json")
    
    print("=== PROGRESS FILE ANALYSIS ===")
    
    if not progress_file.exists():
        print("❌ Progress file not found")
        return {}
    
    with open(progress_file, 'r') as f:
        data = json.load(f)
    
    success_files = data.get('results', {}).get('success', [])
    failed_files = data.get('results', {}).get('failed', [])
    
    print(f"📁 Total success entries: {len(success_files):,}")
    print(f"❌ Total failed entries: {len(failed_files):,}")
    
    # Analyze data fields available
    if success_files:
        sample = success_files[0]
        print(f"\n📋 Available fields in success entries:")
        for key, value in sample.items():
            print(f"  {key}: {type(value).__name__} = {value}")
    
    # Check size data quality
    files_with_nonzero_size = [f for f in success_files if f.get('size', 0) > 0]
    files_with_zero_size = [f for f in success_files if f.get('size', 0) == 0]
    
    print(f"\n📊 Size data quality:")
    print(f"  Files with size > 0: {len(files_with_nonzero_size):,}")
    print(f"  Files with size = 0: {len(files_with_zero_size):,}")
    
    if files_with_nonzero_size:
        sizes = [f.get('size', 0) for f in files_with_nonzero_size]
        print(f"  Total size from JSON: {sum(sizes) / (1024**3):.2f} GB")
        print(f"  Average file size: {sum(sizes) / len(sizes) / (1024**2):.2f} MB")
    
    # Check timestamps
    files_with_timestamp = [f for f in success_files if f.get('timestamp')]
    print(f"  Files with timestamps: {len(files_with_timestamp):,}")
    
    # Check local paths / file paths
    unique_paths = set()
    local_paths = []
    
    for f in success_files[:1000]:  # Sample first 1000
        path = f.get('path', '')
        if path:
            unique_paths.add(path)
            # Try to construct local path
            local_path = f"C:/commercial_pdfs/downloaded_files/{path}"
            if os.path.exists(local_path):
                local_paths.append(local_path)
    
    print(f"  Unique file paths (sample): {len(unique_paths):,}")
    print(f"  Files found on disk (sample): {len(local_paths):,}")
    
    return {
        'success_files': success_files,
        'failed_files': failed_files,
        'files_with_nonzero_size': files_with_nonzero_size,
        'files_with_zero_size': files_with_zero_size
    }

def analyze_file_system():
    """Analyze what's actually on the file system"""
    download_dir = Path("C:/commercial_pdfs/downloaded_files")
    
    print("\n=== FILE SYSTEM ANALYSIS ===")
    
    if not download_dir.exists():
        print("❌ Download directory not found")
        return {}
    
    # Find all PDF and other files
    all_files = []
    total_size = 0
    
    print("🔍 Scanning file system...")
    
    for root, dirs, files in os.walk(download_dir):
        for file in files:
            if file.endswith(('.pdf', '.PDF', '.xls', '.xlsx', '.msg', '.jpg', '.png')):
                file_path = Path(root) / file
                try:
                    size = file_path.stat().st_size
                    relative_path = file_path.relative_to(download_dir)
                    all_files.append({
                        'path': str(relative_path).replace('\\', '/'),
                        'size': size,
                        'full_path': str(file_path)
                    })
                    total_size += size
                except:
                    pass
    
    print(f"📁 Files found on disk: {len(all_files):,}")
    print(f"📊 Total size on disk: {total_size / (1024**3):.2f} GB")
    
    if all_files:
        avg_size = total_size / len(all_files)
        print(f"📊 Average file size: {avg_size / (1024**2):.2f} MB")
        
        # File type breakdown
        extensions = Counter()
        for f in all_files:
            ext = Path(f['path']).suffix.lower()
            extensions[ext] += 1
        
        print(f"📋 File types found:")
        for ext, count in extensions.most_common(10):
            print(f"  {ext}: {count:,} files")
    
    return {
        'all_files': all_files,
        'total_size': total_size,
        'file_count': len(all_files)
    }

def cross_reference_data(progress_data, filesystem_data):
    """Cross-reference progress file data with file system data"""
    print("\n=== CROSS-REFERENCE ANALYSIS ===")
    
    # Create lookup dictionaries
    progress_paths = {f.get('path', ''): f for f in progress_data.get('success_files', [])}
    filesystem_paths = {f['path']: f for f in filesystem_data.get('all_files', [])}
    
    # Find matches
    matched_files = []
    missing_from_progress = []
    missing_from_filesystem = []
    
    for path in filesystem_paths:
        if path in progress_paths:
            fs_file = filesystem_paths[path]
            progress_file = progress_paths[path]
            matched_files.append({
                'path': path,
                'fs_size': fs_file['size'],
                'progress_size': progress_file.get('size', 0),
                'timestamp': progress_file.get('timestamp', ''),
                'status': progress_file.get('status', '')
            })
        else:
            missing_from_progress.append(path)
    
    for path in progress_paths:
        if path not in filesystem_paths:
            missing_from_filesystem.append(path)
    
    print(f"✅ Files in both progress and filesystem: {len(matched_files):,}")
    print(f"❓ Files on disk but not in progress: {len(missing_from_progress):,}")
    print(f"❓ Files in progress but not on disk: {len(missing_from_filesystem):,}")
    
    # Analyze size discrepancies
    size_matches = 0
    size_mismatches = 0
    total_corrected_size = 0
    
    for f in matched_files:
        if f['fs_size'] == f['progress_size']:
            size_matches += 1
        else:
            size_mismatches += 1
        total_corrected_size += f['fs_size']
    
    print(f"📊 Size data accuracy:")
    print(f"  Files with matching sizes: {size_matches:,}")
    print(f"  Files with size mismatches: {size_mismatches:,}")
    print(f"  Corrected total size: {total_corrected_size / (1024**3):.2f} GB")
    
    return {
        'matched_files': matched_files,
        'missing_from_progress': missing_from_progress,
        'missing_from_filesystem': missing_from_filesystem,
        'total_corrected_size': total_corrected_size
    }

def main():
    """Main analysis function"""
    print("🔍 Analyzing all data sources for SharePoint downloads...\n")
    
    # Analyze progress file
    progress_data = analyze_progress_file()
    
    # Analyze file system
    filesystem_data = analyze_file_system()
    
    # Cross-reference
    cross_ref_data = cross_reference_data(progress_data, filesystem_data)
    
    print("\n=== RECOMMENDATIONS ===")
    print("1. ✅ Use file system data for accurate size calculations")
    print("2. ✅ Use progress file for status, timestamps, and tracking")
    print("3. ✅ Cross-reference both sources for complete picture")
    print("4. ✅ Handle files that exist on disk but not in progress")
    print("5. ✅ Use actual file sizes instead of JSON size field")

if __name__ == "__main__":
    main()
