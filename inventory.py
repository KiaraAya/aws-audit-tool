# ---------------------------------------------------------
# inventory.py
# AWS inventory collection for aws-audit-tool
# ---------------------------------------------------------

from __future__ import annotations

# Imports -----------------------------------------------

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Callable
import logging

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Internal Helpers --------------------------------------

# Creates a boto3 client for the specified service and region
def _client(service: str, region: str):
    return boto3.client(service, region_name=region)

# Safely calls a function and captures ClientError exceptions, returning a standardized response
def safe_call(fn: Callable[..., Any], **kwargs) -> dict:
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

# Paginates through a boto3 client operation, collecting items from the specified result key, and captures ClientError exceptions
def _paginate(
    client,
    operation: str,
    result_key: str,
    **kwargs
) -> tuple[list[dict], Optional[dict]]:
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

# Global Inventory --------------------------------------

# Collects global inventory items that are not region-specific, such as IAM users and S3 buckets, and captures ClientError exceptions
def collect_global_inventory() -> Dict[str, Any]:
    s3 = boto3.client("s3")
    iam = boto3.client("iam")

    out: Dict[str, Any] = {}
    
    resp = safe_call(iam.list_account_aliases)
    out["account_aliases"] = resp["data"].get("AccountAliases", []) if resp["ok"] else []
    if not resp["ok"]:
        out["account_aliases_error"] = resp

    resp = safe_call(s3.list_buckets)
    out["s3_buckets"] = resp["data"].get("Buckets", []) if resp["ok"] else []
    if not resp["ok"]:
        out["s3_buckets_error"] = resp

    users, err = _paginate(iam, "list_users", "Users")
    out["iam_users"] = users
    if err:
        out["iam_users_error"] = err

    return out

# Regional Inventory ------------------------------------

# Collects inventory items for a specific region, such as VPCs, EC2 instances, and RDS clusters, and captures ClientError exceptions for each API call
def collect_region_inventory(region: str) -> Dict[str, Any]:
    ec2 = _client("ec2", region)
    elbv2 = _client("elbv2", region)
    rds = _client("rds", region)
    autoscaling = _client("autoscaling", region)
    dynamodb = _client("dynamodb", region)

    data: Dict[str, Any] = {"region": region}

    # Each API call is wrapped in safe_call to capture errors without stopping the entire collection process. 
    # Results are stored in the data dictionary, and any errors are recorded with an "_error" key for that resource type.
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

    instances, err = _paginate(ec2, "describe_instances", "Reservations")
    if err:
        data["instances"] = []
        data["instances_error"] = err
    else:
        flat: list[dict] = []
        for r in instances:
            flat.extend(r.get("Instances", []) or [])
        data["instances"] = flat

    vols, err = _paginate(ec2, "describe_volumes", "Volumes")
    data["ebs_volumes"] = vols
    if err:
        data["ebs_volumes_error"] = err

    resp = safe_call(elbv2.describe_load_balancers)
    data["load_balancers"] = resp["data"].get("LoadBalancers", []) if resp["ok"] else []
    if not resp["ok"]:
        data["load_balancers_error"] = resp

    resp = safe_call(elbv2.describe_target_groups)
    data["target_groups"] = resp["data"].get("TargetGroups", []) if resp["ok"] else []
    if not resp["ok"]:
        data["target_groups_error"] = resp

    resp = safe_call(rds.describe_db_instances)
    data["rds_db_instances"] = resp["data"].get("DBInstances", []) if resp["ok"] else []
    if not resp["ok"]:
        data["rds_db_instances_error"] = resp

    resp = safe_call(rds.describe_db_clusters)
    data["rds_db_clusters"] = resp["data"].get("DBClusters", []) if resp["ok"] else []
    if not resp["ok"]:
        data["rds_db_clusters_error"] = resp

    asgs, err = _paginate(autoscaling, "describe_auto_scaling_groups", "AutoScalingGroups")
    data["autoscaling_groups"] = asgs
    if err:
        data["autoscaling_groups_error"] = err

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

    # For each DynamoDB table, we attempt to describe it to get more details. 
    # Errors in describing individual tables are collected but do not stop the process of collecting other tables.
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

# Orchestration -----------------------------------------

# Collects inventory for the specified regions, including global inventory, and returns a structured dictionary with all collected data.
def collect_inventory(regions: List[str], max_workers: int = 8) -> Dict[str, Any]:
    global_inv = collect_global_inventory()

    # We use a ThreadPoolExecutor to collect regional inventory in parallel, which can speed up the process when there are many regions.
    items: list[dict] = []
    if not regions:
        return {"regions": [], "global": global_inv, "items": []}

    workers = min(max_workers, max(1, len(regions)))
    logger.info("Collecting regional inventory with %s workers for %s regions", workers, len(regions))

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(collect_region_inventory, r): r for r in regions}
        for fut in as_completed(futures):
            items.append(fut.result())

    items.sort(key=lambda x: x.get("region", ""))

    return {"regions": regions, "global": global_inv, "items": items}
