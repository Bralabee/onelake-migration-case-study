#!/usr/bin/env python3
"""
🔍 Microsoft Fabric OneLake Connection Diagnostics
================================================

Test tool to verify Fabric authentication and API access.
Helps troubleshoot migration issues.

Author:Sanmi Ibitoye
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

class FabricDiagnostics:
    """Diagnostic tool for Fabric OneLake connectivity."""
    
    def __init__(self):
        """Initialize diagnostics."""
        self.tenant_id = os.environ.get("TENANT_ID")
        self.client_id = os.environ.get("CLIENT_ID") 
        self.client_secret = os.environ.get("CLIENT_SECRET")
        self.workspace_id = os.environ.get("FABRIC_WORKSPACE_ID")
        self.lakehouse_id = os.environ.get("FABRIC_LAKEHOUSE_ID")
        self.onelake_base_path = os.environ.get("ONELAKE_BASE_PATH", "/Files/SharePoint_Invoices")
        
    def test_authentication(self) -> str:
        """Test Azure AD authentication."""
        logger.info("🔐 Testing Azure AD authentication...")
        
        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        token_data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://api.fabric.microsoft.com/.default"
        }
        
        try:
            response = requests.post(token_url, data=token_data)
            response.raise_for_status()
            token_info = response.json()
            
            logger.info("✅ Authentication successful!")
            logger.info(f"🔑 Token expires in: {token_info.get('expires_in', 'unknown')} seconds")
            
            return token_info["access_token"]
            
        except Exception as e:
            logger.error(f"❌ Authentication failed: {e}")
            return None
    
    def test_workspace_access(self, token: str) -> bool:
        """Test workspace access."""
        logger.info("🏢 Testing workspace access...")
        
        api_base = "https://api.fabric.microsoft.com/v1"
        workspace_url = f"{api_base}/workspaces/{self.workspace_id}"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.get(workspace_url, headers=headers)
            
            if response.status_code == 200:
                workspace_info = response.json()
                logger.info("✅ Workspace access successful!")
                logger.info(f"📊 Workspace: {workspace_info.get('displayName', 'Unknown')}")
                return True
            else:
                logger.error(f"❌ Workspace access failed: HTTP {response.status_code}")
                logger.error(f"Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Workspace access error: {e}")
            return False
    
    def test_lakehouse_access(self, token: str) -> bool:
        """Test lakehouse access."""
        logger.info("🏠 Testing lakehouse access...")
        
        api_base = "https://api.fabric.microsoft.com/v1"
        lakehouse_url = f"{api_base}/workspaces/{self.workspace_id}/items/{self.lakehouse_id}"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.get(lakehouse_url, headers=headers)
            
            if response.status_code == 200:
                lakehouse_info = response.json()
                logger.info("✅ Lakehouse access successful!")
                logger.info(f"🏠 Lakehouse: {lakehouse_info.get('displayName', 'Unknown')}")
                logger.info(f"📝 Type: {lakehouse_info.get('type', 'Unknown')}")
                return True
            else:
                logger.error(f"❌ Lakehouse access failed: HTTP {response.status_code}")
                logger.error(f"Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Lakehouse access error: {e}")
            return False
    
    def test_file_upload(self, token: str) -> bool:
        """Test small file upload to OneLake."""
        logger.info("📄 Testing file upload...")
        
        # Create test file content
        test_content = f"Test file created: {datetime.now().isoformat()}"
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
                logger.info("✅ File upload successful!")
                logger.info(f"📁 Created: {test_path}")
                return True
            else:
                logger.error(f"❌ File upload failed: HTTP {response.status_code}")
                logger.error(f"Response: {response.text}")
                logger.error(f"Upload URL: {upload_url}")
                return False
                
        except Exception as e:
            logger.error(f"❌ File upload error: {e}")
            return False
    
    def list_files_in_path(self, token: str) -> bool:
        """List files in the OneLake path."""
        logger.info("📂 Testing file listing...")
        
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
                logger.info("✅ File listing successful!")
                
                if isinstance(files_info, list):
                    logger.info(f"📁 Found {len(files_info)} items in {self.onelake_base_path}")
                    for item in files_info[:5]:  # Show first 5 items
                        logger.info(f"  - {item.get('name', 'Unknown')} ({item.get('type', 'Unknown')})")
                else:
                    logger.info(f"📁 Response: {files_info}")
                
                return True
            else:
                logger.error(f"❌ File listing failed: HTTP {response.status_code}")
                logger.error(f"Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ File listing error: {e}")
            return False
    
    def run_full_diagnostics(self):
        """Run complete diagnostic suite."""
        logger.info("🔍 FABRIC ONELAKE DIAGNOSTICS")
        logger.info("=" * 50)
        
        # Check configuration
        logger.info("⚙️  Configuration check:")
        logger.info(f"  Tenant ID: {self.tenant_id[:8]}...")
        logger.info(f"  Client ID: {self.client_id[:8]}...")
        logger.info(f"  Workspace ID: {self.workspace_id}")
        logger.info(f"  Lakehouse ID: {self.lakehouse_id}")
        logger.info(f"  Base Path: {self.onelake_base_path}")
        
        # Test authentication
        token = self.test_authentication()
        if not token:
            logger.error("❌ Cannot proceed without authentication")
            return False
        
        # Test workspace access
        if not self.test_workspace_access(token):
            logger.error("❌ Cannot access workspace")
            return False
        
        # Test lakehouse access
        if not self.test_lakehouse_access(token):
            logger.error("❌ Cannot access lakehouse")
            return False
        
        # Test file operations
        upload_success = self.test_file_upload(token)
        list_success = self.list_files_in_path(token)
        
        if upload_success and list_success:
            logger.info("🎉 ALL DIAGNOSTICS PASSED!")
            logger.info("✅ Your Fabric OneLake connection is working correctly")
            return True
        else:
            logger.error("❌ Some diagnostics failed - check permissions and configuration")
            return False

def main():
    """Run diagnostics."""
    diagnostics = FabricDiagnostics()
    success = diagnostics.run_full_diagnostics()
    
    if success:
        print("\n🎯 DIAGNOSIS: Connection is working!")
        print("💡 If migration shows 0 successes, check:")
        print("   1. File paths in source directory")
        print("   2. Network connectivity during upload")
        print("   3. File size limits (if any)")
    else:
        print("\n❌ DIAGNOSIS: Connection issues found!")
        print("💡 Fix the issues above before running migration")

if __name__ == "__main__":
    main()
