#!/usr/bin/env python3
"""
Simple OneLake API Test Script
Tests the exact API endpoints and authentication
"""

import os
import requests
import json
from datetime import datetime

# Load environment variables
env_paths = ["config/.env", ".env"]
for env_path in env_paths:
    if os.path.exists(env_path):
        print(f"📄 Loading environment from: {env_path}")
        with open(env_path, 'r') as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value
        break

def test_onelake_apis():
    """Test different OneLake API approaches"""
    workspace_id = os.environ.get('FABRIC_WORKSPACE_ID')
    lakehouse_id = os.environ.get('FABRIC_LAKEHOUSE_ID') 
    access_token = os.environ.get('ACCESS_TOKEN')  # This is what's created by get_access_token.ps1
    
    print(f"🔧 Configuration:")
    print(f"Workspace ID: {workspace_id}")
    print(f"Lakehouse ID: {lakehouse_id}")
    print(f"Access Token: {'✅ Set' if access_token else '❌ Not set'}")
    
    if not all([workspace_id, lakehouse_id, access_token]):
        print("❌ Missing required configuration")
        return
    
    # Test file content
    test_content = f"Test file created at {datetime.now()}"
    test_filename = "diagnostic_test.txt"
    
    # Test different API approaches
    tests = [
        {
            "name": "OneLake Data Lake Gen2 API (without .Lakehouse suffix)",
            "url": f"https://onelake.dfs.fabric.microsoft.com/{workspace_id}/{lakehouse_id}/Files/{test_filename}?resource=file",
            "method": "put_direct"
        },
        {
            "name": "OneLake Data Lake Gen2 API (with .Lakehouse suffix)",
            "url": f"https://onelake.dfs.fabric.microsoft.com/{workspace_id}/{lakehouse_id}.Lakehouse/Files/{test_filename}?resource=file",
            "method": "put_direct"
        },
        {
            "name": "OneLake Data Lake Gen2 API (Create-Append-Flush without suffix)",
            "url": f"https://onelake.dfs.fabric.microsoft.com/{workspace_id}/{lakehouse_id}/Files/{test_filename}",
            "method": "create_append_flush"
        },
        {
            "name": "OneLake Data Lake Gen2 API (Create-Append-Flush with suffix)",
            "url": f"https://onelake.dfs.fabric.microsoft.com/{workspace_id}/{lakehouse_id}.Lakehouse/Files/{test_filename}",
            "method": "create_append_flush"
        }
    ]
    
    for test in tests:
        print(f"\n🧪 Testing: {test['name']}")
        print(f"URL: {test['url']}")
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/octet-stream",
            "x-ms-version": "2020-06-12",  # Data Lake Gen2 API version
            "Content-Length": str(len(test_content.encode())),
            "x-ms-client-request-id": "test-request-123",
            "x-ms-date": "Thu, 08 Aug 2025 10:20:00 GMT"  # Current timestamp
        }
        
        try:
            if test['method'] == 'put_direct':
                # Simple PUT request for file creation (Content-Length must be zero)
                create_headers = headers.copy()
                create_headers['Content-Length'] = '0'  # Must be zero for file creation
                response = requests.put(test['url'], headers=create_headers, timeout=30)
                print(f"Result: {'✅' if response.status_code in [200, 201] else '❌'} HTTP {response.status_code}")
                if response.status_code not in [200, 201]:
                    print(f"Error: {response.text[:200]}")
                    
            elif test['method'] == 'create_append_flush':
                # Azure Data Lake Gen2 pattern
                # Step 1: Create file with proper query parameter and zero content
                create_url = f"{test['url']}?resource=file"
                create_headers = headers.copy()
                create_headers['Content-Length'] = '0'  # Must be zero for file creation
                create_response = requests.put(create_url, headers=create_headers, timeout=30)
                print(f"Create: {'✅' if create_response.status_code in [200, 201] else '❌'} HTTP {create_response.status_code}")
                
                if create_response.status_code in [200, 201]:
                    # Step 2: Append data
                    append_url = f"{test['url']}?action=append&position=0"
                    append_headers = headers.copy()  # Use original headers with content length
                    append_response = requests.patch(append_url, data=test_content.encode(), headers=append_headers, timeout=30)
                    print(f"Append: {'✅' if append_response.status_code in [200, 202] else '❌'} HTTP {append_response.status_code}")
                    
                    if append_response.status_code in [200, 202]:
                        # Step 3: Flush
                        flush_url = f"{test['url']}?action=flush&position={len(test_content.encode())}"
                        flush_headers = headers.copy()
                        flush_headers['Content-Length'] = '0'  # No content for flush
                        flush_response = requests.patch(flush_url, headers=flush_headers, timeout=30)
                        print(f"Flush: {'✅' if flush_response.status_code in [200, 201] else '❌'} HTTP {flush_response.status_code}")
                        
                        if flush_response.status_code not in [200, 201]:
                            print(f"Flush Error: {flush_response.text[:200]}")
                    else:
                        print(f"Append Error: {append_response.text[:200]}")
                else:
                    print(f"Create Error: {create_response.text[:200]}")
                    
        except Exception as e:
            print(f"❌ Exception: {e}")
    
    # Test authentication scopes
    print(f"\n🔐 Testing different authentication scopes:")
    
    auth_tests = [
        {
            "scope": "https://storage.azure.com/.default",
            "name": "Azure Storage scope"
        },
        {
            "scope": "https://api.fabric.microsoft.com/.default", 
            "name": "Fabric API scope"
        }
    ]
    
    tenant_id = os.environ.get('TENANT_ID')
    client_id = os.environ.get('CLIENT_ID')
    client_secret = os.environ.get('CLIENT_SECRET')
    
    if all([tenant_id, client_id, client_secret]):
        for auth_test in auth_tests:
            try:
                token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
                token_data = {
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "scope": auth_test['scope']
                }
                
                response = requests.post(token_url, data=token_data, timeout=30)
                if response.status_code == 200:
                    print(f"✅ {auth_test['name']}: Token obtained")
                    
                    # Quick test with this token
                    new_token = response.json()['access_token']
                    test_headers = {
                        "Authorization": f"Bearer {new_token}",
                        "Content-Type": "application/octet-stream"
                    }
                    
                    test_url = f"https://onelake.dfs.fabric.microsoft.com/{workspace_id}/{lakehouse_id}.Lakehouse/Files/scope_test_{auth_test['name'].replace(' ', '_')}.txt"
                    test_response = requests.put(test_url, headers=test_headers, timeout=30)
                    print(f"   API Test: {'✅' if test_response.status_code in [200, 201] else '❌'} HTTP {test_response.status_code}")
                    
                else:
                    print(f"❌ {auth_test['name']}: HTTP {response.status_code}")
                    
            except Exception as e:
                print(f"❌ {auth_test['name']}: {e}")
    else:
        print("❌ Missing OAuth credentials for scope testing")

if __name__ == "__main__":
    print("🔬 OneLake API Diagnostic Test")
    print("=" * 40)
    test_onelake_apis()
