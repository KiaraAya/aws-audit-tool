import boto3
from botocore.exceptions import ClientError


def _s3_client(region: str | None = None):
    # En EC2 con Role: boto3 agarra credenciales del Instance Profile automáticamente.
    if region:
        return boto3.client("s3", region_name=region)
    return boto3.client("s3")


def upload_file(bucket: str, key: str, path: str, region: str | None = None) -> None:
    s3 = _s3_client(region)
    try:
        s3.upload_file(path, bucket, key)
    except ClientError as e:
        raise RuntimeError(f"S3 upload failed bucket={bucket} key={key} path={path}: {e}") from e


def download_file(bucket: str, key: str, path: str, region: str | None = None) -> None:
    s3 = _s3_client(region)
    try:
        s3.download_file(bucket, key, path)
    except ClientError as e:
        raise RuntimeError(f"S3 download failed bucket={bucket} key={key} path={path}: {e}") from e
