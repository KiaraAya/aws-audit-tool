# ---------------------------------------------------------
# s3_io.py
# S3 IO utilities for aws-audit-tool
# ---------------------------------------------------------

from __future__ import annotations

# Imports -----------------------------------------------

import os
from typing import Optional
import logging

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Internal Helpers --------------------------------------

# Returns an S3 client, optionally in a specific region
def _s3_client(region: Optional[str] = None):
    return boto3.client("s3", region_name=region) if region else boto3.client("s3")

# S3 Operations -----------------------------------------

# Uploads a local file to S3 at the specified bucket and key
def upload_file(bucket: str, key: str, path: str, region: Optional[str] = None) -> None:
    s3 = _s3_client(region)
    try:
        s3.upload_file(path, bucket, key)
    except ClientError as e:
        raise RuntimeError(f"S3 upload failed bucket={bucket} key={key} path={path}: {e}") from e

# Downloads a file from S3 to the specified local path
def download_file(bucket: str, key: str, path: str, region: Optional[str] = None) -> None:
    s3 = _s3_client(region)
    try:
        s3.download_file(bucket, key, path)
    except ClientError as e:
        raise RuntimeError(f"S3 download failed bucket={bucket} key={key} path={path}: {e}") from e

# Uploads all files in a local directory tree to S3 under the specified bucket and prefix
def upload_tree(bucket: str, prefix: str, root_dir: str, region: Optional[str] = None) -> None:
    for dirpath, _, filenames in os.walk(root_dir):
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root_dir).replace("\\", "/")
            key = f"{prefix}/{rel}"
            logger.info("Uploading %s -> s3://%s/%s", rel, bucket, key)
            upload_file(bucket, key, full, region=region)
