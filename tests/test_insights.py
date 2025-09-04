#!/usr/bin/env python3
import json
import sys
sys.path.append('.')
from simple_dashboard import SimpleProgressMonitor

# Test the insights generation
monitor = SimpleProgressMonitor("C:/commercial_pdfs/downloaded_files")
data = monitor.load_data()

print("=== TESTING INSIGHTS PAGE GENERATION ===")
print(f"Progress file exists: {monitor.progress_file.exists()}")
print(f"Cache file exists: {monitor.cache_file.exists()}")
print(f"Total files: {data.get('cache', {}).get('total_files', 'N/A')}")
print(f"Progress data loaded: {'progress' in data}")

if 'progress' in data:
    results = data['progress'].get('results', {})
    success_files = results.get('success', [])
    failed_files = results.get('failed', [])
    print(f"Success files count: {len(success_files)}")
    print(f"Failed files count: {len(failed_files)}")
    
    # Test insights generation
    try:
        insights = monitor.generate_file_insights(success_files, failed_files)
        print(f"Insights generated successfully: {len(insights)} keys")
        print(f"File types found: {len(insights.get('file_types', {}))}")
        print(f"Top folders: {len(insights.get('top_folders', []))}")
        
        # Test a few items
        if success_files:
            print("\nSample success file:")
            print(json.dumps(success_files[0], indent=2)[:300] + "...")
            
    except Exception as e:
        print(f"Error generating insights: {e}")
        import traceback
        traceback.print_exc()

# Test HTML generation
try:
    html = monitor.generate_insights_html(data)
    print(f"HTML generated successfully: {len(html)} characters")
except Exception as e:
    print(f"Error generating HTML: {e}")
    import traceback
    traceback.print_exc()
