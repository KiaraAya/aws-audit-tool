"""
Execution orchestrator for aws-audit-tool.

Flow:
1) Validate identity (STS)
2) Collect inventory (global + per region)
3) Write inventory.json + sts_identity.json
4) Generate Excel report
5) Optional: CloudMapper (collect + prepare)
   - Package offline site ZIP (web + account-data/<account>)
   - Optionally start webserver
6) Optional: Upload outputs to S3
"""

from __future__ import annotations

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


def ensure_dirs(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def get_identity() -> dict:
    sts = boto3.client("sts")
    return sts.get_caller_identity()


def _write_json(path: str, obj: object) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, default=str)


def run_all(settings: Settings) -> str:
    # Import here so runner can still run even if cloudmapper deps are missing
    from cloudmapper_job import (
        run_cloudmapper,
        package_cloudmapper_site_zip,
        start_cloudmapper_webserver,
    )

    ensure_dirs(settings.output_dir)

    identity = get_identity()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    run_dir = os.path.join(settings.output_dir, ts)
    ensure_dirs(run_dir)

    logger.info("Run started: %s", ts)

    # 1) Persist STS identity
    _write_json(os.path.join(run_dir, "sts_identity.json"), identity)

    # 2) Inventory
    inv = collect_inventory(settings.regions)
    inv["run_info"] = {
        "timestamp_utc": ts,
        "regions": settings.regions,
        "account_name": settings.account_name,
        "account_id_env": settings.account_id,
        "sts_identity": identity,
    }
    _write_json(os.path.join(run_dir, "inventory.json"), inv)

    # 3) Excel
    excel_path = os.path.join(run_dir, "audit_report.xlsx")
    build_excel(inv, excel_path)

    # 4) Findings summary
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

    # 5) CloudMapper (optional)
    web_proc = None
    cloudmapper_zip = None

    if settings.run_cloudmapper:
        try:
            run_cloudmapper(
                cloudmapper_dir=settings.cloudmapper_dir,
                account_name=settings.account_name,
                regions=settings.regions,
            )

            # Package offline "HTML" as ZIP (recommended way)
            cloudmapper_zip = package_cloudmapper_site_zip(
                cloudmapper_dir=settings.cloudmapper_dir,
                account_name=settings.account_name,
                out_dir=run_dir,
            )

            # Start webserver (optional) - your version supports --port/--public/--ipv6 only
            # If you want it always on, set an env var in config later.
            # For now: only start if CLOUDMAPPER_WEBSERVER=1
            if os.getenv("CLOUDMAPPER_WEBSERVER", "0") == "1":
                web_proc = start_cloudmapper_webserver(
                    cloudmapper_dir=settings.cloudmapper_dir,
                    port=getattr(settings, "cloudmapper_port", 8000),
                    public=False,
                    ipv6=False,
                )

        except Exception as e:
            logger.warning("CloudMapper failed (non-blocking): %s", e)

    # 6) Upload outputs to S3 (optional)
    if settings.s3_bucket:
        prefix = f"{settings.s3_prefix}/{ts}"

        # Upload the full run_dir (Excel + JSON + zip if present)
        upload_tree(settings.s3_bucket, prefix, run_dir)

        # (Optional) Make sure zip is uploaded even if your upload_tree ignores it for any reason
        if cloudmapper_zip and os.path.exists(cloudmapper_zip):
            key = f"{prefix}/{os.path.basename(cloudmapper_zip)}"
            upload_file(settings.s3_bucket, key, cloudmapper_zip)

    logger.info("Run completed: outputs=%s", run_dir)

    if web_proc:
        logger.info(
            "CloudMapper webserver running (PID=%s). Use SSH tunnel to view it.",
            web_proc.pid,
        )

    return run_dir
