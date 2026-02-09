# inventory.py
"""
AWS inventory collection.

Collects:
- Global inventory (S3 buckets, IAM users, account aliases)
- Regional inventory (VPC/EC2/etc + EBS, RDS, ASG, DynamoDB)

Errors are captured per-service and do not stop the full run.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Callable
import logging

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def _client(service: str, region: str):
    return boto3.client(service, region_name=region)


def safe_call(fn: Callable[..., Any], **kwargs) -> dict:
    """
    Run a boto3 call safely.

    Returns:
      {"ok": True, "data": <response>}
      {"ok": False, "error": "...", "code": "...", "message": "..."}
    """
    try:
        return {"ok": True, "data": fn(**kwargs)}
    except ClientError as e:
        err = getattr(e, "response", {}).get("Error", {}) or {}
        return {
            "ok": False,
            "error": str(e),
            "code": err.get("Code", ""),
            "message": err.get("Message", ""),
        }


def _paginate(client, operation: str, result_key: str, **kwargs) -> tuple[list[dict], Optional[dict]]:
    """
    Generic paginator helper.

    Returns:
      (items, error_obj)
    """
    items: list[dict] = []
    try:
        paginator = client.get_paginator(operation)
        for page in paginator.paginate(**kwargs):
            items.extend(page.get(result_key, []) or [])
        return items, None
    except ClientError as e:
        err = getattr(e, "response", {}).get("Error", {}) or {}
        return [], {
            "error": str(e),
            "code": err.get("Code", ""),
            "message": err.get("Message", ""),
        }


def collect_global_inventory() -> Dict[str, Any]:
    """Collect global (non-regional) resources."""
    s3 = boto3.client("s3")
    iam = boto3.client("iam")

    out: Dict[str, Any] = {}

    # Account aliases
    resp = safe_call(iam.list_account_aliases)
    out["account_aliases"] = resp["data"].get("AccountAliases", []) if resp["ok"] else []
    if not resp["ok"]:
        out["account_aliases_error"] = resp

    # S3 buckets (global)
    resp = safe_call(s3.list_buckets)
    out["s3_buckets"] = resp["data"].get("Buckets", []) if resp["ok"] else []
    if not resp["ok"]:
        out["s3_buckets_error"] = resp

    # IAM users (global, paginated)
    users, err = _paginate(iam, "list_users", "Users")
    out["iam_users"] = users
    if err:
        out["iam_users_error"] = err

    return out


def collect_region_inventory(region: str) -> Dict[str, Any]:
    """Collect regional inventory for a single AWS region."""
    ec2 = _client("ec2", region)
    elbv2 = _client("elbv2", region)
    rds = _client("rds", region)
    autoscaling = _client("autoscaling", region)
    dynamodb = _client("dynamodb", region)

    data: Dict[str, Any] = {"region": region}

    # Core
    for key, call in [
        ("vpcs", lambda: safe_call(ec2.describe_vpcs)),
        ("subnets", lambda: safe_call(ec2.describe_subnets)),
        ("route_tables", lambda: safe_call(ec2.describe_route_tables)),
        ("internet_gateways", lambda: safe_call(ec2.describe_internet_gateways)),
        ("nat_gateways", lambda: safe_call(ec2.describe_nat_gateways)),
        ("security_groups", lambda: safe_call(ec2.describe_security_groups)),
        ("network_interfaces", lambda: safe_call(ec2.describe_network_interfaces)),
    ]:
        resp = call()
        data[key] = resp["data"].get(key[0].upper() + key[1:], []) if resp["ok"] else []
        # above line won't match AWS keys always; handle individually below for correctness

    # Fix keys properly (AWS response keys)
    data["vpcs"] = safe_call(ec2.describe_vpcs)["data"].get("Vpcs", []) if safe_call(ec2.describe_vpcs)["ok"] else []
    # NOTE: avoid double calls by doing explicit calls once:
    # We'll do it correctly below with single calls:

    # --- Single-call blocks (no duplicates) ---
    resp = safe_call(ec2.describe_vpcs)
    data["vpcs"] = resp["data"].get("Vpcs", []) if resp["ok"] else []
    if not resp["ok"]:
        data["vpcs_error"] = resp

    resp = safe_call(ec2.describe_subnets)
    data["subnets"] = resp["data"].get("Subnets", []) if resp["ok"] else []
    if not resp["ok"]:
        data["subnets_error"] = resp

    resp = safe_call(ec2.describe_route_tables)
    data["route_tables"] = resp["data"].get("RouteTables", []) if resp["ok"] else []
    if not resp["ok"]:
        data["route_tables_error"] = resp

    resp = safe_call(ec2.describe_internet_gateways)
    data["internet_gateways"] = resp["data"].get("InternetGateways", []) if resp["ok"] else []
    if not resp["ok"]:
        data["internet_gateways_error"] = resp

    resp = safe_call(ec2.describe_nat_gateways)
    data["nat_gateways"] = resp["data"].get("NatGateways", []) if resp["ok"] else []
    if not resp["ok"]:
        data["nat_gateways_error"] = resp

    resp = safe_call(ec2.describe_security_groups)
    data["security_groups"] = resp["data"].get("SecurityGroups", []) if resp["ok"] else []
    if not resp["ok"]:
        data["security_groups_error"] = resp

    resp = safe_call(ec2.describe_network_interfaces)
    data["network_interfaces"] = resp["data"].get("NetworkInterfaces", []) if resp["ok"] else []
    if not resp["ok"]:
        data["network_interfaces_error"] = resp

    # Instances (paginated)
    instances, err = _paginate(ec2, "describe_instances", "Reservations")
    if err:
        data["instances"] = []
        data["instances_error"] = err
    else:
        flat: list[dict] = []
        for r in instances:
            flat.extend(r.get("Instances", []) or [])
        data["instances"] = flat

    # EBS volumes (paginated)
    vols, err = _paginate(ec2, "describe_volumes", "Volumes")
    data["ebs_volumes"] = vols
    if err:
        data["ebs_volumes_error"] = err

    # Load balancers / target groups
    resp = safe_call(elbv2.describe_load_balancers)
    data["load_balancers"] = resp["data"].get("LoadBalancers", []) if resp["ok"] else []
    if not resp["ok"]:
        data["load_balancers_error"] = resp

    resp = safe_call(elbv2.describe_target_groups)
    data["target_groups"] = resp["data"].get("TargetGroups", []) if resp["ok"] else []
    if not resp["ok"]:
        data["target_groups_error"] = resp

    # RDS
    resp = safe_call(rds.describe_db_instances)
    data["rds_db_instances"] = resp["data"].get("DBInstances", []) if resp["ok"] else []
    if not resp["ok"]:
        data["rds_db_instances_error"] = resp

    resp = safe_call(rds.describe_db_clusters)
    data["rds_db_clusters"] = resp["data"].get("DBClusters", []) if resp["ok"] else []
    if not resp["ok"]:
        data["rds_db_clusters_error"] = resp

    # AutoScaling (paginated)
    asgs, err = _paginate(autoscaling, "describe_auto_scaling_groups", "AutoScalingGroups")
    data["autoscaling_groups"] = asgs
    if err:
        data["autoscaling_groups_error"] = err

    # DynamoDB: list tables + describe each
    table_names: list[str] = []
    try:
        p = dynamodb.get_paginator("list_tables")
        for page in p.paginate():
            table_names.extend(page.get("TableNames", []) or [])
    except ClientError as e:
        err = getattr(e, "response", {}).get("Error", {}) or {}
        data["dynamodb_tables"] = []
        data["dynamodb_tables_error"] = {
            "error": str(e),
            "code": err.get("Code", ""),
            "message": err.get("Message", ""),
        }
        return data

    tables: list[dict] = []
    errors: list[dict] = []
    for name in table_names:
        resp = safe_call(dynamodb.describe_table, TableName=name)
        if resp["ok"]:
            tables.append(resp["data"].get("Table", {}) or {})
        else:
            errors.append({"TableName": name, **resp})

    data["dynamodb_tables"] = tables
    if errors:
        data["dynamodb_tables_describe_errors"] = errors

    return data


def collect_inventory(regions: List[str], max_workers: int = 8) -> Dict[str, Any]:
    """Collect inventory for all regions (parallel) + global inventory."""
    global_inv = collect_global_inventory()

    items: list[dict] = []
    if not regions:
        return {"regions": [], "global": global_inv, "items": []}

    workers = min(max_workers, max(1, len(regions)))
    logger.info("Collecting regional inventory with %s workers for %s regions", workers, len(regions))

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(collect_region_inventory, r): r for r in regions}
        for fut in as_completed(futures):
            items.append(fut.result())

    # Keep output stable-ish: sort by region
    items.sort(key=lambda x: x.get("region", ""))

    return {"regions": regions, "global": global_inv, "items": items}
