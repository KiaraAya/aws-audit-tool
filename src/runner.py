import json
import os
from datetime import datetime, timezone

import boto3

from .config import Settings
from .inventory import collect_inventory
from .s3_io import upload_file
from .cloudmapper_job import run_cloudmapper
from .excel_report import build_excel


def ensure_dirs(path: str):
    os.makedirs(path, exist_ok=True)


def get_identity() -> dict:
    """
    Valida que boto3 esté usando el IAM Role de la instancia EC2.
    """
    sts = boto3.client("sts")
    return sts.get_caller_identity()


def run_all(settings: Settings) -> str:
    """
    Orquesta:
    1) Validación de identidad (IAM Role)
    2) Inventario AWS (JSON)
    3) Reporte Excel (.xlsx)
    4) CloudMapper (diagramas)
    5) Upload opcional a S3
    """
    ensure_dirs(settings.output_dir)

    # ─────────────────────────────────────────────
    # 1) Validar IAM Role
    # ─────────────────────────────────────────────
    identity = get_identity()

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = os.path.join(settings.output_dir, ts)
    ensure_dirs(run_dir)

    identity_path = os.path.join(run_dir, "sts_identity.json")
    with open(identity_path, "w", encoding="utf-8") as f:
        json.dump(identity, f, indent=2)

    # ─────────────────────────────────────────────
    # 2) Inventory AWS (JSON)
    # ─────────────────────────────────────────────
    inv = collect_inventory(settings.regions)

    inv_path = os.path.join(run_dir, "inventory.json")
    with open(inv_path, "w", encoding="utf-8") as f:
        json.dump(inv, f, indent=2, default=str)

    # ─────────────────────────────────────────────
    # 3) Excel report
    # ─────────────────────────────────────────────
    excel_path = os.path.join(run_dir, "audit_report.xlsx")
    build_excel(inv, excel_path)

    # ─────────────────────────────────────────────
    # 4) CloudMapper (diagramas)
    # ─────────────────────────────────────────────
    run_cloudmapper(
        cloudmapper_dir=settings.cloudmapper_dir,
        account_name=settings.account_name,
        regions=settings.regions,
    )

    # ─────────────────────────────────────────────
    # 5) Upload a S3 (opcional)
    # ─────────────────────────────────────────────
    if settings.s3_bucket:
        prefix = f"{settings.s3_prefix}/{ts}"

        upload_file(
            settings.s3_bucket,
            f"{prefix}/sts_identity.json",
            identity_path,
        )
        upload_file(
            settings.s3_bucket,
            f"{prefix}/inventory.json",
            inv_path,
        )
        upload_file(
            settings.s3_bucket,
            f"{prefix}/audit_report.xlsx",
            excel_path,
        )

    return run_dir
