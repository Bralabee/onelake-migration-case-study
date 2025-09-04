#!/usr/bin/env python3
"""
🔍 Microsoft Fabric Workspace Discovery Tool
============================================

Helps you find your Fabric workspace and lakehouse IDs
needed for the OneLake migration.

This script uses the Microsoft Fabric REST API to list
your workspaces and lakehouses.

Author:Sanmi Ibitoye
Date: August 7, 2025
"""

import requests
import json
import os
from datetime import datetime

def load_env_file(env_file=".env"):
    """Load environment variables from .env file."""
    # Check multiple possible locations for .env file
    possible_paths = [
        env_file,  # Current directory
        f"config/{env_file}",  # Config directory (after reorganization)
        f"../../config/{env_file}",  # From src/fabric/ to config/
        f"../config/{env_file}"  # Alternative path
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            print(f"📄 Loading environment from: {path}")
            with open(path, 'r') as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        os.environ[key] = value.strip('"\'')
            return
    
    print(f"⚠️  No .env file found in any of these locations: {possible_paths}")

def get_fabric_token(tenant_id: str, client_id: str, client_secret: str) -> str:
    """Get access token for Microsoft Fabric API."""
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    
    # Try multiple scopes that might work with Fabric
    scopes = [
        "https://api.fabric.microsoft.com/.default",
        "https://analysis.windows.net/powerbi/api/.default",
        "https://graph.microsoft.com/.default"
    ]
    
    for scope in scopes:
        token_data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope
        }
        
        try:
            print(f"🔑 Trying authentication with scope: {scope}")
            response = requests.post(token_url, data=token_data)
            response.raise_for_status()
            token = response.json()["access_token"]
            print(f"✅ Successfully authenticated with scope: {scope}")
            return token
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed with scope {scope}: {e}")
            continue
    
    print("❌ Failed to authenticate with any scope")
    return None

def list_workspaces(token: str):
    """List available Fabric workspaces using multiple API endpoints."""
    headers = {"Authorization": f"Bearer {token}"}
    
    # Try different API endpoints for workspace discovery
    endpoints = [
        "https://api.fabric.microsoft.com/v1/workspaces",
        "https://api.powerbi.com/v1.0/myorg/groups",
        "https://api.powerbi.com/v1.0/myorg/admin/groups?$expand=users,reports,dashboards,datasets",
        "https://graph.microsoft.com/v1.0/groups?$filter=groupTypes/any(c:c eq 'Unified')"
    ]
    
    for endpoint in endpoints:
        try:
            print(f"🔍 Trying endpoint: {endpoint}")
            response = requests.get(endpoint, headers=headers)
            response.raise_for_status()
            
            workspaces_data = response.json()
            # Handle different response formats
            if "value" in workspaces_data:
                workspaces = workspaces_data["value"]
            else:
                workspaces = workspaces_data if isinstance(workspaces_data, list) else []
            
            print(f"✅ Found {len(workspaces)} workspaces with endpoint: {endpoint}")
            
            if workspaces:
                print("🏢 Available Workspaces:")
                print("=" * 50)
                
                for workspace in workspaces:
                    # Handle different field names across APIs
                    name = workspace.get('displayName') or workspace.get('name') or 'Unknown'
                    id_field = workspace.get('id') or workspace.get('objectId') or 'Unknown'
                    workspace_type = workspace.get('type') or workspace.get('groupType') or 'Unknown'
                    description = workspace.get('description') or 'No description'
                    
                    print(f"📁 Name: {name}")
                    print(f"   ID: {id_field}")
                    print(f"   Type: {workspace_type}")
                    print(f"   Description: {description}")
                    print()
                
                return workspaces
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed with endpoint {endpoint}: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"   Response: {e.response.status_code} - {e.response.text[:200]}")
            continue
    
    print("❌ No workspaces found with any endpoint")
    print("💡 This might mean:")
    print("1. No Fabric license or workspace access")
    print("2. App registration needs additional permissions")
    print("3. Try using Power BI workspaces instead")
    return []

def list_lakehouses(token: str, workspace_id: str, workspace_name: str):
    """List lakehouses in a specific workspace using multiple API approaches."""
    headers = {"Authorization": f"Bearer {token}"}
    
    # Try different API endpoints for lakehouse discovery
    endpoints = [
        f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/items?type=Lakehouse",
        f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets",
        f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/items",
        f"https://api.powerbi.com/v1.0/myorg/admin/groups/{workspace_id}/datasets"
    ]
    
    for endpoint in endpoints:
        try:
            print(f"🔍 Trying lakehouse endpoint: {endpoint}")
            response = requests.get(endpoint, headers=headers)
            response.raise_for_status()
            
            items_data = response.json()
            items = items_data.get("value", []) if isinstance(items_data, dict) else items_data
            
            # Filter for lakehouses or datasets that might be lakehouses
            lakehouses = []
            for item in items:
                item_type = item.get('type', '').lower()
                if 'lakehouse' in item_type or 'dataset' in item_type:
                    lakehouses.append(item)
            
            print(f"✅ Found {len(lakehouses)} potential lakehouses/datasets")
            
            if lakehouses:
                print(f"🏗️ Lakehouses/Datasets in '{workspace_name}':")
                print("=" * 50)
                
                for lakehouse in lakehouses:
                    name = lakehouse.get('displayName') or lakehouse.get('name') or 'Unknown'
                    id_field = lakehouse.get('id') or 'Unknown'
                    item_type = lakehouse.get('type') or 'Unknown'
                    description = lakehouse.get('description') or 'No description'
                    
                    print(f"🏗️ Name: {name}")
                    print(f"   ID: {id_field}")
                    print(f"   Type: {item_type}")
                    print(f"   Description: {description}")
                    print(f"   URL: https://app.fabric.microsoft.com/groups/{workspace_id}/items/{id_field}")
                    print()
                
                return lakehouses
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed with endpoint {endpoint}: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"   Response: {e.response.status_code} - {e.response.text[:200]}")
            continue
    
    print("❌ No lakehouses found with any endpoint")
    print("💡 You may need to:")
    print("1. Create a lakehouse in the Fabric portal")
    print("2. Use Power BI Premium workspace")
    print(f"3. Visit: https://app.fabric.microsoft.com/groups/{workspace_id}")
    return []

def generate_env_config(workspace_id: str, lakehouse_id: str, workspace_name: str, lakehouse_name: str):
    """Generate .env configuration snippet."""
    config = f"""
# Microsoft Fabric OneLake Configuration (Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
# Workspace: {workspace_name}
# Lakehouse: {lakehouse_name}
FABRIC_WORKSPACE_ID={workspace_id}
FABRIC_LAKEHOUSE_ID={lakehouse_id}
ONELAKE_BASE_PATH=/Files/SharePoint_Invoices
DELTA_TABLE_NAME=sharepoint_invoices
"""
    
    # Save to file
    with open("fabric_config.env", "w") as f:
        f.write(config)
    
    print("✅ Configuration saved to: fabric_config.env")
    print("Copy these lines to your .env file:")
    print(config)

def main():
    """Main function to discover Fabric resources."""
    print("🔍 Microsoft Fabric Workspace Discovery")
    print("=" * 50)
    
    # Load environment
    load_env_file()
    
    tenant_id = os.environ.get("TENANT_ID")
    client_id = os.environ.get("CLIENT_ID")
    client_secret = os.environ.get("CLIENT_SECRET")
    
    if not all([tenant_id, client_id, client_secret]):
        print("❌ Missing required environment variables:")
        print("Please ensure your .env file contains:")
        print("- TENANT_ID")
        print("- CLIENT_ID")
        print("- CLIENT_SECRET")
        return
    
    print(f"🔐 Using App Registration: {client_id}")
    print(f"🏢 Tenant: {tenant_id}")
    print()
    
    # Get token
    print("🔑 Getting Fabric access token...")
    token = get_fabric_token(tenant_id, client_id, client_secret)
    
    if not token:
        print("❌ Failed to authenticate with Fabric API")
        print("Check your app registration permissions:")
        print("1. Go to Azure Portal → App Registrations")
        print("2. Add API permission: Power BI Service → App.ReadWrite.All")
        print("3. Grant admin consent")
        return
    
    print("✅ Successfully authenticated with Fabric API")
    print()
    
    # List workspaces
    workspaces = list_workspaces(token)
    
    if not workspaces:
        return
    
    # Interactive workspace selection
    if len(workspaces) == 1:
        selected_workspace = workspaces[0]
        print(f"📁 Using the only available workspace: {selected_workspace['displayName']}")
    else:
        print("Please select a workspace:")
        for i, workspace in enumerate(workspaces):
            print(f"{i + 1}. {workspace['displayName']}")
        
        try:
            choice = int(input("Enter workspace number: ")) - 1
            selected_workspace = workspaces[choice]
        except (ValueError, IndexError):
            print("❌ Invalid selection")
            return
    
    workspace_id = selected_workspace['id']
    workspace_name = selected_workspace['displayName']
    
    print(f"📁 Selected workspace: {workspace_name} ({workspace_id})")
    print()
    
    # List lakehouses in selected workspace
    lakehouses = list_lakehouses(token, workspace_id, workspace_name)
    
    if not lakehouses:
        print("💡 Create a lakehouse first:")
        print(f"1. Go to: https://app.fabric.microsoft.com/groups/{workspace_id}")
        print("2. Click '+ New' → Lakehouse")
        print("3. Give it a name like 'SharePoint_Data'")
        print("4. Run this script again")
        return
    
    # Interactive lakehouse selection
    if len(lakehouses) == 1:
        selected_lakehouse = lakehouses[0]
        print(f"🏗️ Using the only available lakehouse: {selected_lakehouse['displayName']}")
    else:
        print("Please select a lakehouse:")
        for i, lakehouse in enumerate(lakehouses):
            print(f"{i + 1}. {lakehouse['displayName']}")
        
        try:
            choice = int(input("Enter lakehouse number: ")) - 1
            selected_lakehouse = lakehouses[choice]
        except (ValueError, IndexError):
            print("❌ Invalid selection")
            return
    
    lakehouse_id = selected_lakehouse['id']
    lakehouse_name = selected_lakehouse['displayName']
    
    print(f"🏗️ Selected lakehouse: {lakehouse_name} ({lakehouse_id})")
    print()
    
    # Generate configuration
    generate_env_config(workspace_id, lakehouse_id, workspace_name, lakehouse_name)
    
    print("\n🚀 Next Steps:")
    print("1. Copy the configuration above to your .env file")
    print("2. Test the connection: make fabric-analyze")
    print("3. Start migration: make fabric-migrate")

if __name__ == "__main__":
    main()
