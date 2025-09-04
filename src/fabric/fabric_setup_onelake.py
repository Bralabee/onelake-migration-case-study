#!/usr/bin/env python3
"""
🔧 Microsoft Fabric OneLake Setup Tool
====================================

Creates directory structure and prepares OneLake for migration.
Fixes the 404 EntityNotFound errors.

Author: GitHub Copilot  
Date: August 8, 2025
"""

import os
import requests
import json
from datetime import datetime
from dotenv import load_dotenv
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
# Check multiple possible locations for .env file
env_paths = [
    ".env",  # Current directory
    "config/.env",  # Config directory (after reorganization)
    "../../config/.env",  # From src/fabric/ to config/
    "../config/.env"  # Alternative path
]

for env_path in env_paths:
    if os.path.exists(env_path):
        load_dotenv(env_path)
        logger.info(f"📄 Loaded environment from: {env_path}")
        break
else:
    load_dotenv()  # Fallback to default behavior
    logger.warning("⚠️  Using default .env loading - may not find config files")

class OneLakeSetup:
    """Setup tool for OneLake directory structure."""
    
    def __init__(self):
        """Initialize setup."""
        self.tenant_id = os.environ.get("TENANT_ID")
        self.client_id = os.environ.get("CLIENT_ID") 
        self.client_secret = os.environ.get("CLIENT_SECRET")
        self.workspace_id = os.environ.get("FABRIC_WORKSPACE_ID")
        self.lakehouse_id = os.environ.get("FABRIC_LAKEHOUSE_ID")
        self.onelake_base_path = os.environ.get("ONELAKE_BASE_PATH", "/Files/SharePoint_Invoices")
        
    def get_fabric_token(self) -> str:
        """Get access token for Microsoft Fabric."""
        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        token_data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://api.fabric.microsoft.com/.default"
        }
        
        response = requests.post(token_url, data=token_data)
        response.raise_for_status()
        return response.json()["access_token"]
    
    def create_directory_structure(self, token: str) -> bool:
        """Create the directory structure in OneLake."""
        logger.info("📁 Creating directory structure in OneLake...")
        
        # Create a placeholder file to establish the directory structure
        placeholder_content = f"""# SharePoint Invoices Migration
Created: {datetime.now().isoformat()}
This directory contains migrated files from SharePoint.

Migration Progress:
- Total files to migrate: 376,888
- Migration started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        placeholder_filename = "README_migration.md"
        placeholder_path = f"{self.onelake_base_path}/{placeholder_filename}"
        
        api_base = "https://api.fabric.microsoft.com/v1"
        upload_url = f"{api_base}/workspaces/{self.workspace_id}/items/{self.lakehouse_id}/files{placeholder_path}"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/octet-stream"
        }
        
        try:
            response = requests.put(upload_url, headers=headers, data=placeholder_content.encode())
            
            if response.status_code in [200, 201]:
                logger.info("✅ Directory structure created successfully!")
                logger.info(f"📁 Created: {placeholder_path}")
                return True
            else:
                logger.error(f"❌ Directory creation failed: HTTP {response.status_code}")
                logger.error(f"Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Directory creation error: {e}")
            return False
    
    def test_small_file_upload(self, token: str) -> bool:
        """Test uploading a small file to verify setup."""
        logger.info("🧪 Testing small file upload...")
        
        test_content = f"Test upload successful: {datetime.now().isoformat()}"
        test_filename = f"test_upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        test_path = f"{self.onelake_base_path}/{test_filename}"
        
        api_base = "https://api.fabric.microsoft.com/v1"
        upload_url = f"{api_base}/workspaces/{self.workspace_id}/items/{self.lakehouse_id}/files{test_path}"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/octet-stream"
        }
        
        try:
            response = requests.put(upload_url, headers=headers, data=test_content.encode())
            
            if response.status_code in [200, 201]:
                logger.info("✅ Test file upload successful!")
                logger.info(f"📄 Created: {test_path}")
                return True
            else:
                logger.error(f"❌ Test upload failed: HTTP {response.status_code}")
                logger.error(f"Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Test upload error: {e}")
            return False
    
    def list_directory_contents(self, token: str) -> bool:
        """List contents of the created directory."""
        logger.info("📂 Listing directory contents...")
        
        api_base = "https://api.fabric.microsoft.com/v1"
        list_url = f"{api_base}/workspaces/{self.workspace_id}/items/{self.lakehouse_id}/files{self.onelake_base_path}"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.get(list_url, headers=headers)
            
            if response.status_code == 200:
                files_info = response.json()
                logger.info("✅ Directory listing successful!")
                
                if isinstance(files_info, list):
                    logger.info(f"📁 Found {len(files_info)} items in {self.onelake_base_path}")
                    for item in files_info:
                        item_name = item.get('name', 'Unknown')
                        item_type = item.get('type', 'Unknown')
                        logger.info(f"  - {item_name} ({item_type})")
                else:
                    logger.info(f"📁 Directory structure: {files_info}")
                
                return True
            else:
                logger.error(f"❌ Directory listing failed: HTTP {response.status_code}")
                logger.error(f"Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Directory listing error: {e}")
            return False
    
    def setup_onelake(self):
        """Complete OneLake setup process."""
        logger.info("🚀 ONELAKE SETUP STARTING")
        logger.info("=" * 50)
        
        # Get authentication token
        logger.info("🔐 Getting authentication token...")
        try:
            token = self.get_fabric_token()
            logger.info("✅ Authentication successful!")
        except Exception as e:
            logger.error(f"❌ Authentication failed: {e}")
            return False
        
        # Create directory structure
        if not self.create_directory_structure(token):
            logger.error("❌ Failed to create directory structure")
            return False
        
        # Test file upload
        if not self.test_small_file_upload(token):
            logger.error("❌ Failed to upload test file")
            return False
        
        # List directory contents
        if not self.list_directory_contents(token):
            logger.warning("⚠️ Could not list directory contents (but setup may still be successful)")
        
        logger.info("🎉 ONELAKE SETUP COMPLETE!")
        logger.info("✅ Directory structure created and verified")
        logger.info(f"📁 Ready for migration to: {self.onelake_base_path}")
        
        return True

def main():
    """Run OneLake setup."""
    setup = OneLakeSetup()
    success = setup.setup_onelake()
    
    if success:
        print("\n🎯 SETUP SUCCESSFUL!")
        print("✅ OneLake is ready for migration")
        print("💡 Now run: make fabric-migrate-turbo")
    else:
        print("\n❌ SETUP FAILED!")
        print("💡 Check the errors above and retry")

if __name__ == "__main__":
    main()
