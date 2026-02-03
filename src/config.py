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
    # AWS
    account_name: str = os.getenv("AWS_AUDIT_ACCOUNT_NAME", "CRIT")
    account_id: str = os.getenv("AWS_AUDIT_ACCOUNT_ID", "")
    regions: List[str] = None

    # S3 outputs (optional)
    s3_bucket: str = os.getenv("AWS_AUDIT_S3_BUCKET", "")
    s3_prefix: str = os.getenv("AWS_AUDIT_S3_PREFIX", "aws-audit-tool")

    # Local paths
    output_dir: str = os.getenv("AWS_AUDIT_OUTPUT_DIR", "outputs")

    # CloudMapper (path al repo clonado en EC2)
    cloudmapper_dir: str = os.getenv("CLOUDMAPPER_DIR", os.path.expanduser("~/cloudmapper"))
    cloudmapper_port: int = int(os.getenv("CLOUDMAPPER_PORT", "8000"))

    def __post_init__(self):
        regions_env = os.getenv("AWS_AUDIT_REGIONS", "")
        self.regions = _split_csv(regions_env) or ["us-east-1"]  # default seguro
