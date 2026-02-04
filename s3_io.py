# Importations ------------------------------------------------------------
import boto3
from botocore.exceptions import ClientError

# S3 client factory -------------------------------------------------------
def _s3_client(region: str | None = None):
    """
    Creates a boto3 S3 client.

    When running on EC2 with an IAM Role attached, boto3 automatically
    retrieves credentials from the Instance Profile (no access keys needed).

    :param region: Optional AWS region for the S3 client
    :return: boto3 S3 client
    """
    
    if region:
        return boto3.client("s3", region_name=region)
    return boto3.client("s3")

# Upload local file to S3 ------------------------------------------------
def upload_file(bucket: str, key: str, path: str, region: str | None = None) -> None:
    """
    Uploads a local file to an S3 bucket.

    :param bucket: Target S3 bucket name
    :param key: S3 object key (path inside the bucket)
    :param path: Local file path to upload
    :param region: Optional AWS region
    :raises RuntimeError: If the upload fails
    """
    s3 = _s3_client(region)
    try:
        s3.upload_file(path, bucket, key)
    except ClientError as e:
        raise RuntimeError(f"S3 upload failed bucket={bucket} key={key} path={path}: {e}") from e

# Download file from S3 -------------------------------------------------
def download_file(bucket: str, key: str, path: str, region: str | None = None) -> None:
    """
    Downloads a file from an S3 bucket to a local path.

    :param bucket: Source S3 bucket name
    :param key: S3 object key (path inside the bucket)
    :param path: Local destination file path
    :param region: Optional AWS region
    :raises RuntimeError: If the download fails
    """
    
    s3 = _s3_client(region)
    try:
        s3.download_file(bucket, key, path)
    except ClientError as e:
        raise RuntimeError(f"S3 download failed bucket={bucket} key={key} path={path}: {e}") from e
