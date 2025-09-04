#!/usr/bin/env python3
"""
OneLake Migration Diagnostic Analysis
Analyzes the disconnect between successful directory creation and failed file uploads
"""

import json
import os
import sys
from datetime import datetime
import requests
import glob
from pathlib import Path

def load_environment():
    """Load environment variables with multi-path checking"""
    env_paths = [
        "config/.env",
        ".env", 
        "../.env",
        "../../config/.env",
        "../config/.env"
    ]
    
    for env_path in env_paths:
        if os.path.exists(env_path):
            print(f"📄 Loading environment from: {env_path}")
            with open(env_path, 'r') as f:
                for line in f:
                    if '=' in line and not line.strip().startswith('#'):
                        key, value = line.strip().split('=', 1)
                        os.environ[key] = value
            return env_path
    
    print("⚠️ No .env file found in any expected location")
    return None

def main():
    print("🔬 OneLake Migration Diagnostic Analysis")
    print("=" * 50)
    print(f"Analysis started at: {datetime.now()}")
    print()
    
    # Load environment
    env_file_used = load_environment()
    
    # Load configuration files
    directories_file = "onelake_directories.json"
    progress_file = "migration_progress_optimized.json"
    
    onelake_dirs = {}
    migration_progress = {}
    
    # Load onelake_directories.json
    if os.path.exists(directories_file):
        with open(directories_file, 'r') as f:
            onelake_dirs = json.load(f)
        print(f"✅ Loaded {len(onelake_dirs)} OneLake directories from {directories_file}")
    else:
        print(f"❌ {directories_file} not found")
    
    # Load migration_progress_optimized.json
    if os.path.exists(progress_file):
        with open(progress_file, 'r') as f:
            migration_progress = json.load(f)
        print(f"✅ Loaded migration progress: {len(migration_progress)} entries")
    else:
        print(f"❌ {progress_file} not found")
    
    # Display configuration summary
    print(f"\n🔧 Configuration Summary:")
    print(f"Environment file: {env_file_used}")
    print(f"Workspace ID: {os.environ.get('FABRIC_WORKSPACE_ID', 'Not set')}")
    print(f"Lakehouse ID: {os.environ.get('FABRIC_LAKEHOUSE_ID', 'Not set')}")
    print(f"Access Token: {'Set' if os.environ.get('FABRIC_ACCESS_TOKEN') else 'Not set'}")
    print(f"OneLake directories loaded: {onelake_dirs.get('total_directories', len(onelake_dirs)) if isinstance(onelake_dirs, dict) else len(onelake_dirs)}")
    print(f"Migration attempts: {len(migration_progress)}")
    
    # Show sample directory structure
    if onelake_dirs:
        if 'directories' in onelake_dirs:
            directories = onelake_dirs['directories']
            print(f"\n📂 Sample directory structure:")
            for i, directory in enumerate(directories[:5]):
                print(f"  {i+1}. {directory}")
            if len(directories) > 5:
                print(f"  ... and {len(directories) - 5} more directories")
        else:
            print(f"\n📂 Sample directory paths:")
            for i, (key, path) in enumerate(list(onelake_dirs.items())[:5]):
                print(f"  {i+1}. {key}")
                print(f"     Path: {path}")
            if len(onelake_dirs) > 5:
                print(f"  ... and {len(onelake_dirs) - 5} more directories")
    
    # Analyze directory creation vs migration attempts
    if onelake_dirs and migration_progress:
        # Handle the actual file structure
        created_dirs = set()
        if 'directories' in onelake_dirs:
            created_dirs = set(onelake_dirs['directories'])
            actual_dir_count = len(created_dirs)
        else:
            created_dirs = set(onelake_dirs.keys())
            actual_dir_count = len(created_dirs)
        
        # Analyze migration progress structure
        completed_files = migration_progress.get('completed_files', [])
        failed_files = migration_progress.get('failed_files', [])
        
        print(f"\n📊 Migration Analysis:")
        print(f"Directories created: {actual_dir_count}")
        print(f"Completed file uploads: {len(completed_files)}")
        print(f"Failed file uploads: {len(failed_files)}")
        
        if len(completed_files) > 0:
            print("✅ Sample successful uploads:")
            for success in completed_files[:3]:
                print(f"  - {success}")
        else:
            print("❌ No successful file uploads found")
            
            # Analyze failure patterns from failed_files
            if failed_files:
                failure_reasons = {}
                for failed_file in failed_files:
                    if isinstance(failed_file, dict):
                        error = failed_file.get('error', 'Unknown error')
                        failure_reasons[error] = failure_reasons.get(error, 0) + 1
                
                print(f"\n🔴 Upload failure patterns:")
                for reason, count in sorted(failure_reasons.items(), key=lambda x: x[1], reverse=True):
                    print(f"  {count:3d}x: {reason}")
                    
                # Show sample failed files
                print(f"\n📄 Sample failed files:")
                for failed_file in failed_files[:5]:
                    if isinstance(failed_file, dict):
                        print(f"  - {failed_file.get('file', 'Unknown file')}: {failed_file.get('error', 'Unknown error')}")
    
    # Show the actual directory structure created
    if onelake_dirs and 'directories' in onelake_dirs:
        print(f"\n📂 Created Directory Structure (sample):")
        directories = onelake_dirs['directories']
        for i, directory in enumerate(directories[:10]):
            print(f"  {i+1:2d}. {directory}")
        if len(directories) > 10:
            print(f"  ... and {len(directories) - 10} more directories")
    
    # API Path Analysis
    workspace_id = os.environ.get('FABRIC_WORKSPACE_ID')
    lakehouse_id = os.environ.get('FABRIC_LAKEHOUSE_ID')
    
    if workspace_id and lakehouse_id:
        print(f"\n🔗 API Path Analysis:")
        
        # Path formats used in different contexts
        paths = {
            'Fabric Notebook (mssparkutils)': f"abfss://COE_F_EUC_P2@onelake.dfs.fabric.microsoft.com/{workspace_id}/{lakehouse_id}.Lakehouse/Files/",
            'OneLake REST API': f"https://onelake.dfs.fabric.microsoft.com/{workspace_id}/{lakehouse_id}.Lakehouse/Files/",
            'Fabric REST API': f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/items/{lakehouse_id}/",
        }
        
        for method, path in paths.items():
            print(f"\n{method}:")
            print(f"  {path}")
        
        # Show sample directory paths from onelake_directories.json
        if onelake_dirs and 'directories' in onelake_dirs:
            print(f"\n📂 Path Conversion Example:")
            sample_dir = onelake_dirs['directories'][0]
            
            # Construct the abfss path that would have been used for directory creation
            abfss_path = f"abfss://COE_F_EUC_P2@onelake.dfs.fabric.microsoft.com/{workspace_id}/{lakehouse_id}.Lakehouse/{sample_dir}/"
            
            print(f"Directory: {sample_dir}")
            print(f"  Created (abfss):  {abfss_path}")
            
            # Show what the migration API should use
            https_path = abfss_path.replace("abfss://COE_F_EUC_P2@", "https://")
            print(f"  For REST API:     {https_path}")
    
    # Authentication Test
    access_token = os.environ.get('FABRIC_ACCESS_TOKEN')
    if access_token and workspace_id:
        print(f"\n🔐 Testing Authentication:")
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}"
            response = requests.get(url, headers=headers, timeout=30)
            print(f"Workspace API: {'✅' if response.status_code == 200 else '❌'} {response.status_code}")
            
            if response.status_code != 200:
                print(f"  Error: {response.text[:200]}")
                
        except Exception as e:
            print(f"Authentication test failed: ❌ {e}")
    else:
        print(f"\n🔐 Authentication: ❌ Missing access token or workspace ID")
    
    # Generate Recommendations
    print(f"\n🎯 ROOT CAUSE ANALYSIS:")
    
    if len(onelake_dirs) > 0 and len(migration_progress) == 0:
        print("1. ❌ ISSUE: Migration script not running or not saving progress")
        print("   → Check if migration script is finding the directories")
        print("   → Verify migration script has write permissions")
    
    if len(onelake_dirs) > 0 and len(migration_progress) > 0:
        print("2. ❌ ISSUE: Path format mismatch between creation and upload")
        print("   → Directories created with abfss:// paths (Fabric notebook)")
        print("   → Migration script likely using https:// paths (REST API)")
        print("   → Need path conversion logic")
    
    if not access_token:
        print("3. ❌ ISSUE: Missing or expired access token")
        print("   → Run 'make fabric-get-token' to refresh token")
        print("   → Add FABRIC_ACCESS_TOKEN to config/.env")
    
    print(f"\n💡 RECOMMENDED SOLUTIONS:")
    print("1. 🔧 PATH CONVERSION FIX:")
    print("   → Update migration script to convert abfss:// to https:// paths")
    print("   → Example: abfss://COE_F_EUC_P2@onelake.dfs.fabric.microsoft.com")
    print("   →      to: https://onelake.dfs.fabric.microsoft.com")
    
    print("\n2. 🔐 AUTHENTICATION FIX:")
    print("   → Refresh access token: make fabric-get-token")
    print("   → Verify token has OneLake write permissions")
    
    print("\n3. 📁 MIGRATION APPROACH:")
    print("   → Test single file upload first")
    print("   → Use Azure Data Lake Gen2 API (create → append → flush)")
    print("   → Consider AzCopy for high-performance uploads")
    
    print(f"\n⏰ Analysis completed at: {datetime.now()}")
    print("\n📋 NEXT STEPS:")
    print("1. Fix path conversion in migration script")
    print("2. Refresh access token")
    print("3. Test single file upload")
    print("4. Run full migration with proper error handling")

if __name__ == "__main__":
    main()
