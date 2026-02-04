# Importations ------------------------------------------------------------
import json
import os
from datetime import datetime, timezone
import boto3
from config import Settings
from inventory import collect_inventory
from s3_io import upload_file
from cloudmapper_job import run_cloudmapper
from excel_report import build_excel

# Ensure directory exists ------------------------------------------------
def ensure_dirs(path: str):
    """
    Creates a directory if it does not already exist.

    :param path: Directory path to create
    """
    os.makedirs(path, exist_ok=True)

# Validate AWS identity ------------------------------------------------
def get_identity() -> dict:
    """
    Validates that boto3 is using the IAM Role attached
    to the EC2 instance (no access keys required).

    :return: AWS STS caller identity
    """
    sts = boto3.client("sts")
    return sts.get_caller_identity()

# Main execution orchestrator ------------------------------------------
def run_all(settings: Settings) -> str:
    """
    Orchestrates the complete audit workflow:

    1) Validate AWS identity (IAM Role)
    2) Collect AWS inventory (JSON)
    3) Generate Excel report
    4) Run CloudMapper (infrastructure diagrams)
    5) Upload outputs to S3 (optional)

    :param settings: Application configuration object
    :return: Path to the execution output directory
    """
    
    # Ensure base output directory exists -----------------------------
    ensure_dirs(settings.output_dir)

    # 1) Validate IAM Role identity -----------------------------------
    identity = get_identity()

    # Create a timestamped execution directory ------------------------
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = os.path.join(settings.output_dir, ts)
    ensure_dirs(run_dir)

    # Persist STS identity for audit traceability ---------------------
    identity_path = os.path.join(run_dir, "sts_identity.json")
    with open(identity_path, "w", encoding="utf-8") as f:
        json.dump(identity, f, indent=2)

    # 2) Collect AWS inventory (JSON) ---------------------------------
    inv = collect_inventory(settings.regions)

    inv_path = os.path.join(run_dir, "inventory.json")
    with open(inv_path, "w", encoding="utf-8") as f:
        json.dump(inv, f, indent=2, default=str)

    # 3) Generate Excel report ----------------------------------------
    excel_path = os.path.join(run_dir, "audit_report.xlsx")
    build_excel(inv, excel_path)

    # 4) CloudMapper (diagram generation) -----------------------------
    '''run_cloudmapper(
        cloudmapper_dir=settings.cloudmapper_dir,
        account_name=settings.account_name,
        regions=settings.regions,
    )'''

    # 5) Upload a S3 (opcional) ---------------------------------------
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
