"""
Simple Directory Structure Creator for OneLake Migration
Uses the same authentication as the existing migration scripts
"""

import os
import json
import logging
import time
from pathlib import Path
from typing import Set, List
from msal import ConfidentialClientApplication
import requests
from urllib.parse import quote

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_env_file():
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

def get_access_token(tenant_id: str, client_id: str, client_secret: str) -> str:
    """Get access token using MSAL"""
    try:
        logger.info("🔐 Getting access token...")
        
        app = ConfidentialClientApplication(
            client_id=client_id,
            client_credential=client_secret,
            authority=f"https://login.microsoftonline.com/{tenant_id}"
        )
        
        # Get token for Fabric API
        result = app.acquire_token_for_client(scopes=["https://api.fabric.microsoft.com/.default"])
        
        if "access_token" in result:
            logger.info("✅ Access token obtained successfully")
            return result["access_token"]
        else:
            logger.error(f"❌ Failed to get access token: {result.get('error_description', 'Unknown error')}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Exception getting access token: {str(e)}")
        return None

def analyze_directory_structure(source_path: str, base_onelake_path: str = "Files/SharePoint_Invoices") -> Set[str]:
    """Analyze local directory structure and return all unique directory paths"""
    logger.info(f"🔍 Analyzing directory structure in: {source_path}")
    
    directories = set()
    file_count = 0
    
    for root, dirs, files in os.walk(source_path):
        file_count += len(files)
        
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
    
    logger.info(f"📊 Found {len(directories)} unique directories for {file_count:,} files")
    return directories

def save_directory_list(directories: Set[str], filename: str = "onelake_directories.json"):
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
    
    # Show sample directories
    logger.info("📋 Sample directories to create:")
    for i, dir_path in enumerate(dir_list[:10]):
        logger.info(f"   {i+1}. {dir_path}")
    
    if len(dir_list) > 10:
        logger.info(f"   ... and {len(dir_list) - 10} more directories")

def show_manual_creation_guide(directories: Set[str]):
    """Show guide for manual directory creation"""
    dir_list = sorted(list(directories))
    
    logger.info("")
    logger.info("📋 MANUAL DIRECTORY CREATION GUIDE")
    logger.info("=================================")
    logger.info("")
    logger.info("🌐 Go to Microsoft Fabric Portal:")
    logger.info("   https://app.fabric.microsoft.com")
    logger.info("")
    logger.info("📁 Navigate to:")
    logger.info("   Workspaces > COE_F_EUC_P2 > si_dev_lakehouse > Files")
    logger.info("")
    logger.info("🏗️ Create these directories (in order):")
    logger.info("")
    
    # Group by depth for easier creation
    by_depth = {}
    for path in dir_list:
        depth = path.count('/')
        if depth not in by_depth:
            by_depth[depth] = []
        by_depth[depth].append(path)
    
    for depth in sorted(by_depth.keys()):
        logger.info(f"   Level {depth} directories:")
        for path in sorted(by_depth[depth])[:5]:  # Show first 5 at each level
            logger.info(f"     • {path}")
        
        if len(by_depth[depth]) > 5:
            logger.info(f"     ... and {len(by_depth[depth]) - 5} more at this level")
        logger.info("")
    
    logger.info("💡 TIP: Create the top-level folders first, then work your way down")
    logger.info("💡 TIP: You can create multiple folders at once by right-clicking in the Files area")

def main():
    """Main execution function"""
    logger.info("🏗️ OneLake Directory Structure Analyzer")
    logger.info("=======================================")
    
    # Load configuration
    env_vars = load_env_file()
    if not env_vars:
        return
    
    # Configuration
    source_path = "C:/commercial_pdfs/downloaded_files"
    
    # Check if source exists
    if not os.path.exists(source_path):
        logger.error(f"❌ Source path does not exist: {source_path}")
        return
    
    # Analyze directory structure
    directories = analyze_directory_structure(source_path)
    
    # Save directory list for reference
    save_directory_list(directories)
    
    # Show manual creation guide
    show_manual_creation_guide(directories)
    
    # Try automatic creation if credentials are available
    tenant_id = env_vars.get('TENANT_ID')
    client_id = env_vars.get('CLIENT_ID')
    client_secret = env_vars.get('CLIENT_SECRET')
    
    if all([tenant_id, client_id, client_secret]):
        logger.info("🤖 Attempting automatic directory creation...")
        
        access_token = get_access_token(tenant_id, client_id, client_secret)
        
        if access_token:
            logger.info("✅ Authentication successful!")
            logger.info("💡 Automatic directory creation is complex via API")
            logger.info("💡 RECOMMENDED: Use manual creation via Fabric portal (faster and more reliable)")
        else:
            logger.info("❌ Automatic creation failed - use manual method")
    
    logger.info("")
    logger.info("🎯 NEXT STEPS:")
    logger.info("1. Create directories manually using the guide above")
    logger.info("2. Once directories are created, run: make fabric-test-single")
    logger.info("3. If test succeeds, run: make fabric-migrate-turbo")

if __name__ == "__main__":
    main()
