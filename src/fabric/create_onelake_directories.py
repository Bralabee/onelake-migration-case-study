"""
Directory Structure Creator for OneLake Migration
This script analyzes the local file structure and creates the necessary
directory hierarchy in OneLake before migration.
"""

import os
import json
import logging
from pathlib import Path
from typing import Set, List
import requests
from urllib.parse import quote
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class OneLakeDirectoryCreator:
    def __init__(self, workspace_id: str, lakehouse_id: str, access_token: str):
        self.workspace_id = workspace_id
        self.lakehouse_id = lakehouse_id
        self.access_token = access_token
        self.base_url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/items/{lakehouse_id}/files"
        
    def get_headers(self):
        """Get authorization headers for API requests"""
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
    
    def analyze_directory_structure(self, source_path: str, base_onelake_path: str = "Files/SharePoint_Invoices") -> Set[str]:
        """
        Analyze local directory structure and return all unique directory paths
        that need to be created in OneLake
        """
        logger.info(f"🔍 Analyzing directory structure in: {source_path}")
        
        directories = set()
        
        for root, dirs, files in os.walk(source_path):
            # Get relative path from source
            rel_path = os.path.relpath(root, source_path)
            
            # Skip the root directory itself
            if rel_path == ".":
                continue
                
            # Convert Windows paths to OneLake format
            onelake_path = rel_path.replace("\\", "/")
            full_onelake_path = f"{base_onelake_path}/{onelake_path}"
            
            # Add this directory and all parent directories
            path_parts = full_onelake_path.split("/")
            for i in range(2, len(path_parts) + 1):  # Start from 2 to skip "Files"
                partial_path = "/".join(path_parts[:i])
                directories.add(partial_path)
        
        logger.info(f"📊 Found {len(directories)} unique directories to create")
        return directories
    
    def create_directory(self, directory_path: str) -> bool:
        """
        Create a single directory in OneLake using the REST API
        """
        # URL encode the path properly
        encoded_path = quote(directory_path, safe='/')
        url = f"{self.base_url}/{encoded_path}"
        
        # Try to create directory using PUT method
        try:
            response = requests.put(
                url,
                headers=self.get_headers(),
                timeout=30
            )
            
            if response.status_code in [200, 201, 409]:  # 409 means already exists
                logger.info(f"✅ Directory created/exists: {directory_path}")
                return True
            else:
                logger.error(f"❌ Failed to create directory {directory_path}: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Exception creating directory {directory_path}: {str(e)}")
            return False
    
    def create_directory_batch(self, directories: List[str], batch_size: int = 10) -> dict:
        """
        Create directories in batches with rate limiting
        """
        logger.info(f"🏗️ Creating {len(directories)} directories in batches of {batch_size}")
        
        results = {"success": 0, "failed": 0, "failed_dirs": []}
        
        # Sort directories by depth (shallowest first)
        sorted_dirs = sorted(directories, key=lambda x: x.count('/'))
        
        for i in range(0, len(sorted_dirs), batch_size):
            batch = sorted_dirs[i:i + batch_size]
            
            logger.info(f"📦 Processing batch {i//batch_size + 1}/{(len(sorted_dirs) + batch_size - 1)//batch_size}")
            
            for directory in batch:
                if self.create_directory(directory):
                    results["success"] += 1
                else:
                    results["failed"] += 1
                    results["failed_dirs"].append(directory)
                
                # Small delay between requests to avoid rate limiting
                time.sleep(0.1)
            
            # Longer delay between batches
            if i + batch_size < len(sorted_dirs):
                logger.info("⏱️ Waiting 2 seconds before next batch...")
                time.sleep(2)
        
        return results
    
    def save_directory_list(self, directories: Set[str], filename: str = "onelake_directories.json"):
        """Save directory list to file for reference"""
        dir_list = sorted(list(directories))
        
        data = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_directories": len(dir_list),
            "directories": dir_list
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"💾 Directory list saved to: {filename}")

def load_env_variables():
    """Load environment variables from .env file"""
    env_vars = {}
    
    # Check multiple possible locations for .env file
    possible_paths = [
        ".env",  # Current directory
        "config/.env",  # Config directory (after reorganization)
        "../../config/.env",  # From src/fabric/ to config/
        "../config/.env"  # Alternative path
    ]
    
    for path in possible_paths:
        try:
            with open(path, 'r') as f:
                logger.info(f"📄 Loading environment from: {path}")
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key.strip()] = value.strip().strip('"\'')
                return env_vars
        except FileNotFoundError:
            continue
    
    logger.error(f"❌ .env file not found in any of these locations: {possible_paths}")
    return None

def main():
    """Main execution function"""
    logger.info("🏗️ OneLake Directory Structure Creator")
    logger.info("=====================================")
    
    # Load configuration
    env_vars = load_env_variables()
    if not env_vars:
        return
    
    # Configuration
    source_path = "C:/commercial_pdfs/downloaded_files"
    workspace_id = env_vars.get('FABRIC_WORKSPACE_ID', 'abc64232-25a2-499d-90ae-9fe5939ae437')
    lakehouse_id = env_vars.get('FABRIC_LAKEHOUSE_ID', 'a622b04f-1094-4f9b-86fd-5105f4778f76')
    access_token = env_vars.get('ACCESS_TOKEN')  # You'll need to get this
    
    if not access_token:
        logger.error("❌ ACCESS_TOKEN not found in .env file")
        logger.info("💡 You can get an access token from:")
        logger.info("   1. Azure Portal > App Registrations > Your App > Certificates & secrets")
        logger.info("   2. Or use Azure CLI: az account get-access-token --resource https://api.fabric.microsoft.com")
        return
    
    # Check if source exists
    if not os.path.exists(source_path):
        logger.error(f"❌ Source path does not exist: {source_path}")
        return
    
    # Initialize creator
    creator = OneLakeDirectoryCreator(workspace_id, lakehouse_id, access_token)
    
    # Analyze directory structure
    directories = creator.analyze_directory_structure(source_path)
    
    # Save directory list for reference
    creator.save_directory_list(directories)
    
    # Show preview
    logger.info("📋 Sample directories to create:")
    sample_dirs = sorted(list(directories))[:10]
    for dir_path in sample_dirs:
        logger.info(f"   {dir_path}")
    
    if len(directories) > 10:
        logger.info(f"   ... and {len(directories) - 10} more")
    
    # Confirm before proceeding
    confirm = input("\n🤔 Proceed with directory creation? (y/N): ")
    if confirm.lower() != 'y':
        logger.info("❌ Directory creation cancelled")
        return
    
    # Create directories
    results = creator.create_directory_batch(list(directories))
    
    # Show results
    logger.info("\n📊 Directory Creation Results:")
    logger.info(f"✅ Successfully created: {results['success']}")
    logger.info(f"❌ Failed to create: {results['failed']}")
    
    if results['failed_dirs']:
        logger.info("\n❌ Failed directories:")
        for failed_dir in results['failed_dirs'][:10]:  # Show first 10
            logger.info(f"   {failed_dir}")
        
        if len(results['failed_dirs']) > 10:
            logger.info(f"   ... and {len(results['failed_dirs']) - 10} more")
    
    if results['success'] > 0:
        logger.info("\n🎉 Directory structure creation completed!")
        logger.info("💡 You can now run the migration script:")
        logger.info("   make fabric-migrate-turbo")

if __name__ == "__main__":
    main()
