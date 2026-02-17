# ---------------------------------------------------------
# config.py
# Central configuration for aws-audit-tool
# ---------------------------------------------------------

from __future__ import annotations

# Imports -----------------------------------------------

from dataclasses import dataclass
import os
from typing import List

# Internal Helpers --------------------------------------

# Utility function to split comma-separated values from environment variables
def _split_csv(value: str) -> List[str]:
    value = (value or "").strip()
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]

# Settings Definition -----------------------------------

# The Settings dataclass encapsulates all configuration options for the aws-audit-tool
@dataclass
class Settings:

    # AWS Account Configuration 
    account_name: str = os.getenv("AWS_AUDIT_ACCOUNT_NAME", "CRIT")
    account_id: str = os.getenv("AWS_AUDIT_ACCOUNT_ID", "")
    regions: List[str] | None = None

    # Output Configuration 
    output_dir: str = os.getenv("AWS_AUDIT_OUTPUT_DIR", "outputs")

    # S3 Upload Configuration 
    s3_bucket: str = os.getenv("AWS_AUDIT_S3_BUCKET", "")
    s3_prefix: str = os.getenv("AWS_AUDIT_S3_PREFIX", "aws-audit-tool")

    # CloudMapper Configuration 
    cloudmapper_dir: str = os.getenv(
        "CLOUDMAPPER_DIR",
        os.path.expanduser("~/cloudmapper")
    )
    
    run_cloudmapper: bool = os.getenv(
        "AWS_AUDIT_RUN_CLOUDMAPPER", "1"
    ) == "1"

    cloudmapper_port: int = int(
        os.getenv("CLOUDMAPPER_PORT", "8000")
    )

    cloudmapper_bind: str = os.getenv(
        "CLOUDMAPPER_BIND", "127.0.0.1"
    )

    cloudmapper_export_html: bool = os.getenv(
        "CLOUDMAPPER_EXPORT_HTML", "1"
    ) == "1"

    # Post Initialization 
    def __post_init__(self) -> None:
        regions_env = os.getenv("AWS_AUDIT_REGIONS", "")
        self.regions = _split_csv(regions_env) or ["us-east-1","us-east-2","us-west-1","us-west-2"]
