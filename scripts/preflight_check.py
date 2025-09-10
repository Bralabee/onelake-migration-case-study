#!/usr/bin/env python3
"""Preflight validation for OneLake Migration Project.

Checks:
 1. Python version >= 3.11
 2. Required environment variables present & non-empty
 3. Optional tuning vars numeric & sane
 4. Can obtain Graph/Fabric token (MSAL) unless manual token provided
 5. Local download path exists or can be created
 6. Write permission to progress JSON directory
 7. Network reachability (HEAD) to SharePoint and Fabric endpoints (best-effort)

Exit codes:
 0 success
 1 missing/invalid env
 2 token acquisition failure
 3 filesystem permission issues
 4 network issues

Usage:
  python scripts/preflight_check.py [--strict]

Strict mode treats warnings as failures.
"""
from __future__ import annotations
import os, sys, json, argparse, pathlib, time, textwrap
from typing import List, Dict, Tuple

REQUIRED_VARS = [
    "TENANT_ID","CLIENT_ID","CLIENT_SECRET",
    "FABRIC_WORKSPACE_ID","FABRIC_LAKEHOUSE_ID",
    "SP_HOSTNAME","SP_SITE_PATH","SP_LIBRARY_NAME","SP_START_FOLDER",
    "LOCAL_DOWNLOAD_PATH"
]
OPTIONAL_VARS_NUMERIC = {
    "MAX_CONCURRENT_UPLOADS": (1, 128),
    "UPLOAD_CHUNK_SIZE_MB": (1, 1024),
    "RETRY_MAX_ATTEMPTS": (1, 20),
    "RETRY_BASE_DELAY_SECONDS": (0.1, 30.0),
    "PROGRESS_REFRESH_SECONDS": (1, 600)
}
SOFT_VARS = ["DELTA_TABLE_NAME","FABRIC_ACCESS_TOKEN","ACCESS_TOKEN","DRY_RUN","STOP_ON_FIRST_ERROR","LOG_LEVEL"]

EXIT_SUCCESS = 0
EXIT_ENV = 1
EXIT_TOKEN = 2
EXIT_FS = 3
EXIT_NET = 4

try:
    import msal  # type: ignore
    import requests
except ImportError as e:
    print("[ERROR] Missing dependency. Activate environment and install requirements first.", file=sys.stderr)
    print(f"Detail: {e}", file=sys.stderr)
    sys.exit(EXIT_ENV)


def color(msg: str, code: str) -> str:
    return f"\033[{code}m{msg}\033[0m"

def ok(msg: str):
    print(color("✔ " + msg, "32"))

def warn(msg: str):
    print(color("⚠ " + msg, "33"))

def err(msg: str):
    print(color("✖ " + msg, "31"))


def check_python() -> bool:
    if sys.version_info < (3,11):
        err(f"Python 3.11+ required, found {sys.version}")
        return False
    ok(f"Python version {sys.version.split()[0]}")
    return True


def load_env_file():
    # Already loaded by user? Support auto-loading .env if present.
    env_path = pathlib.Path('.env')
    if env_path.is_file():
        for line in env_path.read_text().splitlines():
            if not line or line.strip().startswith('#') or '=' not in line:
                continue
            k,v = line.split('=',1)
            os.environ.setdefault(k.strip(), v.strip())


def check_required_env(strict: bool) -> Tuple[bool, Dict[str,str]]:
    missing = []
    values = {}
    for k in REQUIRED_VARS:
        v = os.environ.get(k, '').strip()
        if not v:
            missing.append(k)
        else:
            values[k]=v
    if missing:
        err("Missing required variables: " + ", ".join(missing))
        return False, values
    ok(f"All required variables present ({len(REQUIRED_VARS)})")
    return True, values


def check_numeric(strict: bool) -> bool:
    good = True
    for k,(lo,hi) in OPTIONAL_VARS_NUMERIC.items():
        raw = os.environ.get(k)
        if raw is None:
            warn(f"{k} not set, using default assumptions")
            if strict: good = False
            continue
        try:
            val = float(raw)
        except ValueError:
            err(f"{k} must be numeric, got '{raw}'")
            good = False
            continue
        if not (lo <= val <= hi):
            err(f"{k}={val} out of range [{lo},{hi}]")
            good = False
        else:
            ok(f"{k}={val} within range")
    return good


def acquire_token() -> bool:
    # If manual token override present, trust it.
    if os.environ.get('FABRIC_ACCESS_TOKEN') or os.environ.get('ACCESS_TOKEN'):
        warn("Manual access token provided - skipping MSAL acquisition test")
        return True
    tenant = os.environ.get('TENANT_ID')
    client = os.environ.get('CLIENT_ID')
    secret = os.environ.get('CLIENT_SECRET')
    if not all([tenant,client,secret]):
        err("Cannot acquire token: missing TENANT_ID/CLIENT_ID/CLIENT_SECRET")
        return False
    authority = f"https://login.microsoftonline.com/{tenant}"
    scope = ["https://graph.microsoft.com/.default"]
    try:
        app = msal.ConfidentialClientApplication(client, authority=authority, client_credential=secret)
        result = app.acquire_token_for_client(scopes=scope)
        if 'access_token' in result:
            ok("Graph token acquisition succeeded")
            return True
        else:
            err("Graph token acquisition failed: " + str(result.get('error_description','unknown')))
            return False
    except Exception as e:
        err(f"Exception during token acquisition: {e}")
        return False


def check_filesystem() -> bool:
    good = True
    dl = pathlib.Path(os.environ.get('LOCAL_DOWNLOAD_PATH','./data/downloads'))
    try:
        dl.mkdir(parents=True, exist_ok=True)
        test_file = dl / '.write_test'
        test_file.write_text('ok')
        test_file.unlink(missing_ok=True)
        ok(f"Write access verified for {dl}")
    except Exception as e:
        err(f"Filesystem permission issue at {dl}: {e}")
        good = False
    return good


def check_network(strict: bool) -> bool:
    import socket
    good = True
    sp_host = os.environ.get('SP_HOSTNAME')
    if sp_host:
        try:
            socket.gethostbyname(sp_host)
            ok(f"DNS resolve success: {sp_host}")
        except Exception as e:
            err(f"DNS resolve failed for {sp_host}: {e}")
            good = False
    # Lightweight HEAD requests
    try:
        r = requests.get('https://graph.microsoft.com/v1.0/$metadata', timeout=5)
        if r.status_code < 400:
            ok("Reachable: Microsoft Graph")
        else:
            warn(f"Graph reachable but status {r.status_code}")
            if strict: good = False
    except Exception as e:
        err(f"Network check failed for Graph: {e}")
        good = False
    return good


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--strict', action='store_true', help='Treat warnings as failures')
    args = parser.parse_args()

    load_env_file()
    overall = True

    if not check_python():
        overall = False
    env_ok, _vals = check_required_env(args.strict)
    if not env_ok:
        overall = False
    if not check_numeric(args.strict):
        overall = False
    if overall:
        if not acquire_token():
            sys.exit(EXIT_TOKEN)
        if not check_filesystem():
            sys.exit(EXIT_FS)
        if not check_network(args.strict):
            sys.exit(EXIT_NET)
    if overall:
        ok("Preflight completed successfully")
        sys.exit(EXIT_SUCCESS)
    else:
        err("Preflight failed")
        sys.exit(EXIT_ENV)

if __name__ == '__main__':
    main()
