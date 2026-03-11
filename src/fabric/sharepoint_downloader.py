#!/usr/bin/env python3
"""Download first N files from a SharePoint document library folder using Microsoft Graph.

Environment variables required:
  TENANT_ID, CLIENT_ID, CLIENT_SECRET
  SP_HOSTNAME (e.g. highspeedtwo.sharepoint.com)
  SP_SITE_PATH (e.g. teams/ACA-TaskForceAdvancedAnalytics)
  SP_LIBRARY_NAME (e.g. Documents)
  SP_START_FOLDER (e.g. SCS/Invoices)
  LOCAL_DOWNLOAD_PATH (fallback to ./data/downloads if not set)

Usage:
  python sharepoint_downloader.py --limit 10 --verbose
"""
import os, sys, json, argparse, logging, time, urllib.parse
import requests
from dotenv import load_dotenv
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

GRAPH_ROOT = "https://graph.microsoft.com/v1.0"

# Auto-load .env similar to migrator
ENV_PATHS = [
    ".env",
    "config/.env",
    "../config/.env",
    "../../config/.env"
]
for p in ENV_PATHS:
    if os.path.exists(p):
        try:
            load_dotenv(p)
            logger.info(f"Loaded environment from {p}")
            break
        except Exception as e:
            logger.warning(f"Failed loading {p}: {e}")
else:
    load_dotenv()
    logger.warning("Fell back to default dotenv loading; vars may be missing")

def get_token(tenant_id, client_id, client_secret):
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    data = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret,
        'scope': 'https://graph.microsoft.com/.default'
    }
    r = requests.post(url, data=data)
    r.raise_for_status()
    return r.json()['access_token']

def get_site_id(token, hostname, site_path):
    # site_path like teams/ACA-TaskForceAdvancedAnalytics
    url = f"{GRAPH_ROOT}/sites/{hostname}:/{site_path}"  # trailing colon+path pattern per Graph API
    r = requests.get(url, headers={'Authorization': f'Bearer {token}'})
    r.raise_for_status()
    return r.json()['id']

def get_drive_id(token, site_id, library_name):
    url = f"{GRAPH_ROOT}/sites/{site_id}/drives"
    r = requests.get(url, headers={'Authorization': f'Bearer {token}'})
    r.raise_for_status()
    for d in r.json().get('value', []):
        if d.get('name') == library_name:
            return d['id']
    raise RuntimeError(f"Drive '{library_name}' not found")


def list_children(token, drive_id, folder_path):
    # Encode path safely
    encoded_path = urllib.parse.quote(folder_path.strip('/'))
    url = f"{GRAPH_ROOT}/drives/{drive_id}/root:/{encoded_path}:/children"
    r = requests.get(url, headers={'Authorization': f'Bearer {token}'})
    r.raise_for_status()
    return r.json().get('value', [])


def download_file(token, drive_id, item_id, target_path: Path):
    url = f"{GRAPH_ROOT}/drives/{drive_id}/items/{item_id}/content"
    r = requests.get(url, headers={'Authorization': f'Bearer {token}'}, stream=True)
    r.raise_for_status()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=65536):
            if chunk:
                f.write(chunk)


def main():
    ap = argparse.ArgumentParser(description='Download first N files from SharePoint folder')
    ap.add_argument('--limit', type=int, default=10)
    ap.add_argument('--verbose', action='store_true')
    ap.add_argument('--skip-existing', action='store_true')
    args = ap.parse_args()

    required_env = ['TENANT_ID','CLIENT_ID','CLIENT_SECRET','SP_HOSTNAME','SP_SITE_PATH','SP_LIBRARY_NAME','SP_START_FOLDER']
    missing = [k for k in required_env if not os.environ.get(k)]
    if missing:
        logger.error(f"Missing env vars: {missing}")
        sys.exit(1)

    tenant_id = os.environ['TENANT_ID']
    client_id = os.environ['CLIENT_ID']
    client_secret = os.environ['CLIENT_SECRET']
    hostname = os.environ['SP_HOSTNAME']
    site_path = os.environ['SP_SITE_PATH']
    library = os.environ['SP_LIBRARY_NAME']
    start_folder = os.environ['SP_START_FOLDER']
    download_root = Path(os.environ.get('LOCAL_DOWNLOAD_PATH', './data/downloads'))
    download_root.mkdir(parents=True, exist_ok=True)

    token = get_token(tenant_id, client_id, client_secret)
    if args.verbose: logger.info('Acquired Graph token')
    site_id = get_site_id(token, hostname, site_path)
    if args.verbose: logger.info(f'Site ID: {site_id}')
    drive_id = get_drive_id(token, site_id, library)
    if args.verbose: logger.info(f'Drive ID: {drive_id}')

    queue = [start_folder]
    downloaded = 0
    visited_folders = set()

    while queue and downloaded < args.limit:
        current = queue.pop(0)
        if current in visited_folders:
            continue
        visited_folders.add(current)
        try:
            children = list_children(token, drive_id, current)
        except Exception as e:
            logger.warning(f"List failed {current}: {e}")
            continue
        for item in children:
            if downloaded >= args.limit:
                break
            if 'folder' in item:
                queue.append(f"{current.rstrip('/')}/{item['name']}")
            elif 'file' in item:
                rel_path = f"{current.rstrip('/')}/{item['name']}".replace(start_folder.rstrip('/')+'/', '')
                target = download_root / rel_path
                if args.skip_existing and target.exists():
                    if args.verbose:
                        logger.info(f"Skip existing {rel_path}")
                    continue
                try:
                    download_file(token, drive_id, item['id'], target)
                    downloaded += 1
                    logger.info(f"Downloaded {downloaded}/{args.limit}: {rel_path}")
                except Exception as e:
                    logger.error(f"Download failed {rel_path}: {e}")
        time.sleep(0.1)  # mild pacing

    logger.info(f"Completed: {downloaded} files downloaded to {download_root}")

if __name__ == '__main__':
    main()
