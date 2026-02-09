# runner.py
"""
Execution orchestrator for aws-audit-tool.

Flow:
1) Validate identity (STS)
2) Collect inventory (global + per region)
3) Write inventory.json + sts_identity.json
4) Generate Excel report
5) Optional: CloudMapper
6) Optional: Upload all outputs to S3
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
from cloudmapper_job import run_cloudmapper
from s3_io import upload_tree

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
    from cloudmapper_job import run_cloudmapper, start_cloudmapper_webserver, export_cloudmapper_html

    ensure_dirs(settings.output_dir)

    identity = get_identity()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    run_dir = os.path.join(settings.output_dir, ts)
    ensure_dirs(run_dir)

    logger.info("Run started: %s", ts)
    _write_json(os.path.join(run_dir, "sts_identity.json"), identity)

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

    findings_path = os.path.join(run_dir, "findings_summary.json")
    _write_json(findings_path, {
        "run_info": inv.get("run_info", {}),
        "global_counts": {
            "s3_buckets": len(inv.get("global", {}).get("s3_buckets", []) or []),
            "iam_users": len(inv.get("global", {}).get("iam_users", []) or []),
        },
    })

    # 4) CloudMapper (optional)
    web_proc = None
    if settings.run_cloudmapper:
        try:
            run_cloudmapper(
                cloudmapper_dir=settings.cloudmapper_dir,
                account_name=settings.account_name,
                regions=settings.regions,
            )

            # Export HTML snapshot (optional)
            if getattr(settings, "cloudmapper_export_html", True):
                export_cloudmapper_html(
                    cloudmapper_dir=settings.cloudmapper_dir,
                    account_name=settings.account_name,
                    out_dir=run_dir,  # lo guardamos junto al Excel/JSON
                )

            # Start webserver (optional)
            web_proc = start_cloudmapper_webserver(
                cloudmapper_dir=settings.cloudmapper_dir,
                account_name=settings.account_name,
                bind=settings.cloudmapper_bind,
                port=settings.cloudmapper_port,
            )

        except Exception as e:
            logger.warning("CloudMapper failed (non-blocking): %s", e)


    if settings.s3_bucket:
        prefix = f"{settings.s3_prefix}/{ts}"
        upload_tree(settings.s3_bucket, prefix, run_dir)

    # Upload to S3 
    if settings.s3_bucket:
        prefix = f"{settings.s3_prefix}/{ts}"
        upload_tree(settings.s3_bucket, prefix, run_dir)

    logger.info("Run completed: outputs=%s", run_dir)
    
    if web_proc:
        logger.info("CloudMapper webserver running (PID=%s). Stop it manually if needed.", web_proc.pid)

    return run_dir

