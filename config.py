# Importations ------------------------------------------------------------
from dataclasses import dataclass
import os
from typing import List

# Helper to split comma-separated values ----------------------------------
def _split_csv(value: str) -> List[str]:
    """
    Splits a CSV string into a clean list of values.

    :param value: Comma-separated string (e.g. "us-east-1,us-west-2")
    :return: List of trimmed strings
    """
    value = (value or "").strip()
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]

# # Centralized application configuration -------------------------------
@dataclass
class Settings:
    """
    Central configuration object for aws-audit-tool.

    Values are loaded primarily from environment variables
    to support execution in EC2 using IAM Roles, CI/CD,
    or local development environments.
    """
    
    # AWS account configuration ---------------------------------------
    account_name: str = os.getenv("AWS_AUDIT_ACCOUNT_NAME", "CRIT")       # Logical AWS account name
    account_id: str = os.getenv("AWS_AUDIT_ACCOUNT_ID", "")               # Optional AWS account ID (informational)
    regions: List[str] = None                                             # Will be populated in __post_init__

    # S3 output configuration (optional) - Used for Athena / long-term storage
    s3_bucket: str = os.getenv("AWS_AUDIT_S3_BUCKET", "")                 # Target S3 bucket for outputs
    s3_prefix: str = os.getenv("AWS_AUDIT_S3_PREFIX", "aws-audit-tool")   # Base prefix inside the bucket

    # Local output paths ---------------------------------------------
    output_dir: str = os.getenv("AWS_AUDIT_OUTPUT_DIR", "outputs")        # Local directory for generated artifacts

    # CloudMapper configuration --------------------------------------
    cloudmapper_dir: str = os.getenv("CLOUDMAPPER_DIR", os.path.expanduser("~/cloudmapper")) # Path to the cloned CloudMapper repository
    cloudmapper_port: int = int(os.getenv("CLOUDMAPPER_PORT", "8000"))                       # Port for CloudMapper webserver (if used)

    # Post-initialization logic --------------------------------------
    def __post_init__(self):
        """
        Initializes regions configuration.

        Priority:
        1) AWS_AUDIT_REGIONS environment variable
        2) Safe default: ["us-east-1"]
        """
        regions_env = os.getenv("AWS_AUDIT_REGIONS", "")
        self.regions = _split_csv(regions_env) or ["us-east-1"]  # default seguro
