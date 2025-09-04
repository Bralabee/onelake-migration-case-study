import requests
import os
from urllib.parse import quote

# -----------------------------------------------------------
# Prerequisites:
# 1. Install the requests library: pip install requests
# 2. Get your authentication details (Tenant ID, Client ID, Client Secret)
#    from a registered app in Microsoft Entra ID with permissions
#    to SharePoint.
# 3. Fill in the variables below.
# -----------------------------------------------------------

# --- User Configuration Section ---



# Your SharePoint site details
site_url = 'https://yourtenant.sharepoint.com/sites/YourTeamSite'

# The server-relative URL of the folder you want to download
# Example: '/sites/YourTeamSite/Shared Documents/Main Folder'
folder_path = '/sites/YourTeamSite/Shared Documents/Main Folder'

# The local path where you want to save the files
local_download_path = 'C:\\commercial_pdfs\\downloaded_files'

# --- End User Configuration Section ---

def get_access_token():
    """Authenticates with Microsoft Entra ID and returns an access token."""
    resource = 'https://graph.microsoft.com/.default'
    authority = f'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token'
    
    token_data = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret,
        'scope': resource,
    }

    try:
        print("Attempting to get access token...")
        token_response = requests.post(authority, data=token_data)
        token_response.raise_for_status()
        access_token = token_response.json().get('access_token')
        print("Access token retrieved successfully.")
        return access_token
    except requests.exceptions.RequestException as e:
        print(f"Error getting access token: {e}")
        return None

def download_folder_recursively(folder_server_relative_url, local_path, access_token):
    """
    Recursively downloads files and folders from a SharePoint folder
    to a local directory, preserving the folder structure.
    """
    # Create the local directory if it doesn't exist
    if not os.path.exists(local_path):
        print(f"Creating local directory: {local_path}")
        os.makedirs(local_path)

    # SharePoint REST API URL to get folder contents
    # The URL needs to be encoded
    encoded_url = quote(folder_server_relative_url, safe='')
    api_url = f"{site_url}/_api/web/GetFolderByServerRelativeUrl('{encoded_url}')?$expand=Folders,Files"
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json;odata=nometadata'
    }

    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        folder_contents = response.json()
        
        # Download all files in the current folder
        for file_info in folder_contents.get('Files', []):
            file_name = file_info.get('Name')
            file_server_relative_url = file_info.get('ServerRelativeUrl')
            
            # Use the "GetFileByServerRelativeUrl" endpoint to download the file content
            file_download_url = f"{site_url}/_api/web/GetFileByServerRelativeUrl('{quote(file_server_relative_url, safe='')}')/$value"
            
            local_file_path = os.path.join(local_path, file_name)
            
            print(f"  Downloading file: {file_name} to {local_file_path}")
            
            file_response = requests.get(file_download_url, headers={'Authorization': f'Bearer {access_token}'}, stream=True)
            file_response.raise_for_status()
            
            with open(local_file_path, 'wb') as f:
                # Iterate over the response content in chunks to handle large files efficiently
                for chunk in file_response.iter_content(chunk_size=8192):
                    f.write(chunk)
        
        # Recursively call the function for all subfolders
        for subfolder_info in folder_contents.get('Folders', []):
            subfolder_name = subfolder_info.get('Name')
            subfolder_server_relative_url = subfolder_info.get('ServerRelativeUrl')

            # Skip system folders that don't contain user data
            if subfolder_name not in ['Forms', '_rels', 'Private']:
                new_local_path = os.path.join(local_path, subfolder_name)
                download_folder_recursively(subfolder_server_relative_url, new_local_path, access_token)

    except requests.exceptions.RequestException as e:
        print(f"Error accessing SharePoint API for {folder_server_relative_url}: {e}")

if __name__ == "__main__":
    access_token = get_access_token()
    if access_token:
        print(f"Starting download from SharePoint path: {folder_path}")
        print(f"Destination local path: {local_download_path}")
        download_folder_recursively(folder_path, local_download_path, access_token)
        print("Download process completed.")

