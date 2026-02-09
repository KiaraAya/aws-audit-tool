# s3_io.py
"""
S3 IO utilities.

Supports uploading single files or entire directories (tree upload)
to an S3 bucket using boto3.
"""

from __future__ import annotations

import os
from typing import Optional
import logging

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def _s3_client(region: Optional[str] = None):
    return boto3.client("s3", region_name=region) if region else boto3.client("s3")


def upload_file(bucket: str, key: str, path: str, region: Optional[str] = None) -> None:
    """Upload a local file to S3."""
    s3 = _s3_client(region)
    try:
        s3.upload_file(path, bucket, key)
    except ClientError as e:
        raise RuntimeError(f"S3 upload failed bucket={bucket} key={key} path={path}: {e}") from e


def download_file(bucket: str, key: str, path: str, region: Optional[str] = None) -> None:
    """Download an S3 object to a local file."""
    s3 = _s3_client(region)
    try:
        s3.download_file(bucket, key, path)
    except ClientError as e:
        raise RuntimeError(f"S3 download failed bucket={bucket} key={key} path={path}: {e}") from e


def upload_tree(bucket: str, prefix: str, root_dir: str, region: Optional[str] = None) -> None:
    """
    Upload all files under root_dir to S3 under prefix.

    Keeps subfolder structure.
    """
    for dirpath, _, filenames in os.walk(root_dir):
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root_dir).replace("\\", "/")
            key = f"{prefix}/{rel}"
            logger.info("Uploading %s -> s3://%s/%s", rel, bucket, key)
            upload_file(bucket, key, full, region=region)
