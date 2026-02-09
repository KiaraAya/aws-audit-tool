# config.py
"""
Application configuration for aws-audit-tool.

Settings are loaded from environment variables, with safe defaults
to support EC2 IAM Roles, CI/CD, or local runs.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import List


def _split_csv(value: str) -> List[str]:
    value = (value or "").strip()
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


@dataclass
class Settings:
    """Central configuration object."""

    # AWS account
    account_name: str = os.getenv("AWS_AUDIT_ACCOUNT_NAME", "CRIT")
    account_id: str = os.getenv("AWS_AUDIT_ACCOUNT_ID", "")
    regions: List[str] | None = None

    # Output
    output_dir: str = os.getenv("AWS_AUDIT_OUTPUT_DIR", "outputs")

    # Optional S3 upload
    s3_bucket: str = os.getenv("AWS_AUDIT_S3_BUCKET", "")
    s3_prefix: str = os.getenv("AWS_AUDIT_S3_PREFIX", "aws-audit-tool")

    # CloudMapper 
    cloudmapper_dir: str = os.getenv("CLOUDMAPPER_DIR", os.path.expanduser("~/cloudmapper"))
    run_cloudmapper: bool = os.getenv("AWS_AUDIT_RUN_CLOUDMAPPER", "0") == "1"
    cloudmapper_port: int = int(os.getenv("CLOUDMAPPER_PORT", "8000"))
    cloudmapper_bind: str = os.getenv("CLOUDMAPPER_BIND", "127.0.0.1")  # 0.0.0.0 si querés acceder remoto
    cloudmapper_export_html: bool = os.getenv("CLOUDMAPPER_EXPORT_HTML", "1") == "1"


    def __post_init__(self) -> None:
        regions_env = os.getenv("AWS_AUDIT_REGIONS", "")
        self.regions = _split_csv(regions_env) or ["us-east-1"]
