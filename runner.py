# ---------------------------------------------------------
# runner.py
# Execution orchestrator for aws-audit-tool
# ---------------------------------------------------------

from __future__ import annotations

# Imports -----------------------------------------------

import json
import os
from datetime import datetime, timezone
import logging

import boto3

from config import Settings
from inventory import collect_inventory
from excel_report import build_excel
from s3_io import upload_tree, upload_file

logger = logging.getLogger(__name__)

# Internal Helpers --------------------------------------

# Helper to ensure a directory exists
def ensure_dirs(path: str) -> None:
    os.makedirs(path, exist_ok=True)

# Helper to get AWS STS caller identity
def get_identity() -> dict:
    sts = boto3.client("sts")
    return sts.get_caller_identity()

# Helper to write JSON with indentation and handle non-serializable objects
def _write_json(path: str, obj: object) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, default=str)

# Orchestration -----------------------------------------

# Main function to run the entire audit process
def run_all(settings: Settings) -> str:
    from cloudmapper_job import (
        run_cloudmapper,
        package_cloudmapper_site_zip,
        start_cloudmapper_webserver,
    )

    ensure_dirs(settings.output_dir)

    # Get AWS identity and timestamp for this run
    identity = get_identity()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    run_dir = os.path.join(settings.output_dir, ts)
    ensure_dirs(run_dir)

    logger.info("Run started: %s", ts)

    _write_json(os.path.join(run_dir, "sts_identity.json"), identity)

    # Collect inventory and save it
    inv = collect_inventory(settings.regions)
    inv["run_info"] = {
        "timestamp_utc": ts,
        "regions": settings.regions,
        "account_name": settings.account_name,
        "account_id_env": settings.account_id,
        "sts_identity": identity,
    }
    _write_json(os.path.join(run_dir, "inventory.json"), inv)

    excel_path = os.path.join(run_dir, "audit_report.xlsx")
    build_excel(inv, excel_path)

    # Save a summary of findings for quick reference
    findings_path = os.path.join(run_dir, "findings_summary.json")
    _write_json(
        findings_path,
        {
            "run_info": inv.get("run_info", {}),
            "global_counts": {
                "s3_buckets": len(inv.get("global", {}).get("s3_buckets", []) or []),
                "iam_users": len(inv.get("global", {}).get("iam_users", []) or []),
            },
        },
    )

    web_proc = None
    cloudmapper_zip = None

    # Optionally run CloudMapper and package its output
    if settings.run_cloudmapper:
        # Try to run CloudMapper, but do not block ZIP packaging if outputs exist
        try:
            run_cloudmapper(
                cloudmapper_dir=settings.cloudmapper_dir,
                account_name=settings.account_name,
                regions=settings.regions,
            )
        except Exception as e:
            logger.warning("CloudMapper collect/prepare failed (continuing to package if possible): %s", e)

        # Always try packaging if required folders exist
        try:
            cloudmapper_zip = package_cloudmapper_site_zip(
                cloudmapper_dir=settings.cloudmapper_dir,
                account_name=settings.account_name,
                out_dir=run_dir,
            )
        except Exception as e:
            logger.warning("CloudMapper ZIP packaging failed: %s", e)

        # Optional webserver
        if os.getenv("CLOUDMAPPER_WEBSERVER", "0") == "1":
            try:
                web_proc = start_cloudmapper_webserver(
                    cloudmapper_dir=settings.cloudmapper_dir,
                    port=getattr(settings, "cloudmapper_port", 8000),
                    public=False,
                    ipv6=False,
                )
            except Exception as e:
                logger.warning("CloudMapper webserver failed: %s", e)

    # Upload results to S3 if configured
    if settings.s3_bucket:
        prefix = f"{settings.s3_prefix}/{ts}"

        upload_tree(settings.s3_bucket, prefix, run_dir)

        if cloudmapper_zip and os.path.exists(cloudmapper_zip):
            key = f"{prefix}/{os.path.basename(cloudmapper_zip)}"
            upload_file(settings.s3_bucket, key, cloudmapper_zip)

    logger.info("Run completed: outputs=%s", run_dir)

    # If the webserver is running, log its status
    if web_proc:
        logger.info(
            "CloudMapper webserver running (PID=%s). Use SSH tunnel to view it.",
            web_proc.pid,
        )

    return run_dir
