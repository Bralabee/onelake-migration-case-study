#!/usr/bin/env python3
"""
OneLake SharePoint Invoice Migration Orchestrator
=================================================

Purpose:
  Single entrypoint to (1) download a controlled subset of SharePoint files
  and (2) upload them to OneLake using the optimized migrator, with a final
  consolidated summary. Designed for repeatable smoke tests and scaled runs.

Features:
  * Unified CLI (download + upload + summary)
  * Separate limits for download and upload phases
  * Optional skipping of either phase
  * Mode selection for downloader (--download-mode)
  * Progress reset passthrough to migrator
  * Resumable chunk uploads toggle
  * Pre-create OneLake directories toggle
  * Dry-run (metadata only) for uploader
  * Structured JSON run report (optional)

Prerequisites:
  - Existing environment variables in .env (TENANT_ID, CLIENT_ID, etc.)
  - Existing scripts:
      src/sharepoint/dll_pdf_fabric_turbo.py
      src/fabric/onelake_migrator_turbo_fixed.py

Example:
  python orchestrate_onelake_migration.py \
      --download-limit 100 --upload-limit 100 \
      --download-mode normal --enable-resume-chunks --verbose

Author: GitHub Copilot
Date: 2025-09-10
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
DOWNLOADER = ROOT / "src/sharepoint/dll_pdf_fabric_turbo.py"
MIGRATOR = ROOT / "src/fabric/onelake_migrator_turbo_fixed.py"
DEFAULT_DL_PATH = os.environ.get("LOCAL_DOWNLOAD_PATH", "./data/downloads")

MODES = {"conservative", "normal", "fast", "turbo"}


def run_cmd(cmd:list[str], cwd:Path, verbose:bool):
    start = time.time()
    if verbose:
        print(f"\n[CMD] {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=not verbose, text=True)
    elapsed = time.time() - start
    success = proc.returncode == 0
    stdout = proc.stdout if not verbose else "<streamed>"
    stderr = proc.stderr if not verbose else "<streamed>"
    if not success:
        print(f"❌ Command failed ({cmd[0]}): exit={proc.returncode}")
        if not verbose:
            print("--- STDOUT ---")
            print(stdout)
            print("--- STDERR ---")
            print(stderr)
    return {"command": cmd, "elapsed_sec": elapsed, "exit_code": proc.returncode, "stdout": stdout, "stderr": stderr, "success": success}


def orchestrate(args):
    run_report = {
        "start_time": datetime.utcnow().isoformat() + "Z",
        "download": None,
        "upload": None,
        "summary": {}
    }

    if args.validate_config:
        # Run downloader and migrator validation sequentially (best-effort)
        dl_cmd = [sys.executable, str(DOWNLOADER), "--validate-config"]
        if args.profile:
            dl_cmd += ["--profile", args.profile]
        dl_res = run_cmd(dl_cmd, ROOT, args.verbose)
        mig_cmd = [sys.executable, str(MIGRATOR), "--validate-config"]
        if args.profile:
            mig_cmd += ["--profile", args.profile]
        mig_res = run_cmd(mig_cmd, ROOT, args.verbose)
        ok = dl_res["success"] and mig_res["success"]
        print(f"Validation downloader={'ok' if dl_res['success'] else 'fail'} migrator={'ok' if mig_res['success'] else 'fail'}")
        sys.exit(0 if ok else 2)

    # Phase 1: Download
    if not args.skip_download:
        if not DOWNLOADER.exists():
            print(f"❌ Downloader script not found at {DOWNLOADER}")
            sys.exit(1)
        mode_flag = f"--{args.download_mode}" if args.download_mode in MODES else "--normal"
        dl_limit_args = ["--limit", str(args.download_limit)] if args.download_limit else []
        dl_cmd = [sys.executable, str(DOWNLOADER), mode_flag, *dl_limit_args]
        if args.download_new_only:
            dl_cmd.append("--download-new-only")
        if args.profile:
            dl_cmd += ["--profile", args.profile]
        print(f"📥 Download phase: mode={args.download_mode} limit={args.download_limit or '∞'}")
        dl_result = run_cmd(dl_cmd, ROOT, args.verbose)
        run_report["download"] = dl_result
        if not dl_result["success"]:
            if not args.force_continue:
                print("⛔ Stopping due to download failure (use --force-continue to ignore).")
                finalize(run_report, args)
                sys.exit(dl_result['exit_code'])
            else:
                print("⚠️ Continuing despite download failure (--force-continue set)")
    else:
        print("⏭️ Skipping download phase per user request")

    # Phase 2: Upload
    if not args.skip_upload:
        if not MIGRATOR.exists():
            print(f"❌ Migrator script not found at {MIGRATOR}")
            sys.exit(1)
        upload_limit_args = ["--limit", str(args.upload_limit)] if args.upload_limit else []
        migrator_cmd = [
            sys.executable,
            str(MIGRATOR),
            "--source", args.source,
            "--workers", str(args.workers),
            "--resume"
        ]
        if args.reset_progress:
            migrator_cmd.append("--reset-progress")
        if args.enable_resume_chunks:
            migrator_cmd.append("--enable-resume-chunks")
        if args.precreate_dirs:
            migrator_cmd.append("--precreate-dirs")
        if args.dry_run_metadata:
            migrator_cmd.append("--dry-run-metadata")
        if args.verbose:
            migrator_cmd.append("--verbose")
        migrator_cmd += upload_limit_args
        if args.profile:
            migrator_cmd += ["--profile", args.profile]
        print(f"🚀 Upload phase: limit={args.upload_limit or '∞'} resume_chunks={args.enable_resume_chunks} precreate={args.precreate_dirs}")
        up_result = run_cmd(migrator_cmd, ROOT, args.verbose)
        run_report["upload"] = up_result
        if not up_result["success"] and not args.force_continue:
            print("⛔ Stopping due to upload failure")
            finalize(run_report, args)
            sys.exit(up_result['exit_code'])
    else:
        print("⏭️ Skipping upload phase per user request")

    # Phase 3: Consolidated summary (best-effort parsing of migration progress file)
    # Determine progress file path (profile-aware namespaced state)
    if args.profile:
        progress_file = ROOT / ".state" / args.profile / "migrator" / "migration_progress_optimized.json"
        download_summary_file = ROOT / ".state" / args.profile / "downloader" / "last_run_summary.json"
        if not download_summary_file.exists():  # fallback
            download_summary_file = Path(args.source) / "last_run_summary.json"
    else:
        progress_file = ROOT / "migration_progress_optimized.json"
        download_summary_file = Path(args.source) / "last_run_summary.json"
    if progress_file.exists():
        try:
            data = json.loads(progress_file.read_text())
            stats = data.get("stats", {})
            run_report["summary"]["migration_stats"] = stats
            run_report["summary"]["completed_files"] = len(data.get("completed_files", []))
            if args.skip_upload:
                run_report["summary"]["previous_upload_stats"] = True
        except Exception as e:
            run_report["summary"]["migration_stats_error"] = str(e)
    else:
        run_report["summary"]["note"] = "No migration progress file found"

    # Downloader summary (if available)
    if download_summary_file.exists():
        try:
            dl_summary = json.loads(download_summary_file.read_text())
            run_report["summary"]["download_summary"] = dl_summary
        except Exception as e:
            run_report["summary"]["download_summary_error"] = str(e)

    finalize(run_report, args)


def finalize(report:dict, args):
    report["end_time"] = datetime.utcnow().isoformat() + "Z"
    if args.report_json:
        path = Path(args.report_json)
        path.write_text(json.dumps(report, indent=2))
        print(f"📝 Run report saved to {path}")
    # Human summary
    print("\n================ SUMMARY ================")
    if report.get("download"):
        dl = report["download"]
        print(f"Download: success={dl['success']} time={dl['elapsed_sec']:.2f}s exit={dl['exit_code']}")
    dl_sum = report.get("summary", {}).get("download_summary")
    if dl_sum:
        ignored = dl_sum.get('ignored_existing',0)
        ignored_part = f" | ignored: {ignored}" if ignored else ""
        print(f"Downloaded new: {dl_sum.get('success_new',0)} | skipped: {dl_sum.get('skipped_existing',0)}{ignored_part} | listed: {dl_sum.get('total_listed',0)} (limit={dl_sum.get('limit_requested')})")
    if report.get("upload"):
        up = report["upload"]
        print(f"Upload:   success={up['success']} time={up['elapsed_sec']:.2f}s exit={up['exit_code']}")
    else:
        # user skipped upload phase
        pass
    mig = report.get("summary", {}).get("migration_stats")
    if mig:
        label = "(previous run stats)" if report.get("upload") is None else ""
        print(f"Migrated: {mig.get('successful_uploads',0)}/{mig.get('total_files',0)} (new this run: {mig.get('successful_this_run',0)}) {label} | avg_speed={mig.get('avg_upload_speed',0):.2f} files/sec")
    cf = report.get("summary", {}).get("completed_files")
    if cf is not None:
        print(f"Completed files recorded: {cf}")
    print("========================================\n")


def parse_args():
    p = argparse.ArgumentParser(description="End-to-end orchestrator for SharePoint -> OneLake migration")
    p.add_argument("--download-limit", type=int, help="Limit number of files listed/downloaded")
    p.add_argument("--download-new-only", action="store_true", help="Downloader: ignore already-downloaded files (not counted as skips)")
    p.add_argument("--upload-limit", type=int, help="Limit number of files uploaded")
    p.add_argument("--download-mode", default="normal", choices=list(MODES), help="Downloader parallelism mode")
    p.add_argument("--profile", help="Profile name: loads config/profiles/<profile>.env before default .env")
    p.add_argument("--skip-download", action="store_true", help="Skip downloader phase")
    p.add_argument("--skip-upload", action="store_true", help="Skip uploader phase")
    p.add_argument("--source", default=DEFAULT_DL_PATH, help="Source directory for migrator (download destination)")
    p.add_argument("--workers", type=int, default=25, help="Uploader workers")
    p.add_argument("--reset-progress", action="store_true", help="Reset migration progress before upload")
    p.add_argument("--enable-resume-chunks", action="store_true", help="Enable resumable chunk uploads")
    p.add_argument("--precreate-dirs", action="store_true", help="Pre-create OneLake directory tree")
    p.add_argument("--dry-run-metadata", action="store_true", help="Uploader dry run (no uploads)")
    p.add_argument("--report-json", help="Write consolidated JSON run report to this path")
    p.add_argument("--force-continue", action="store_true", help="Continue even if a phase fails")
    p.add_argument("--verbose", action="store_true", help="Stream underlying script output and enable verbose modes")
    p.add_argument("--validate-config", action="store_true", help="Validate downloader & migrator configuration then exit")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    orchestrate(args)
