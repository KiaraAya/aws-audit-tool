# Importations ------------------------------------------------------------
import boto3
from botocore.exceptions import ClientError
from typing import Dict, Any, List

# AWS client factory ------------------------------------------------------
def _client(service: str, region: str):
    """
    Creates a boto3 client for a given AWS service and region.

    :param service: AWS service name (e.g. ec2, elbv2)
    :param region: AWS region
    :return: boto3 client
    """
    return boto3.client(service, region_name=region)

# Safe wrapper for AWS API calls ------------------------------------------
def _safe_call(fn, **kwargs):
    """
    Executes an AWS SDK call safely.

    If the call fails due to missing permissions or service restrictions,
    the error is captured and returned instead of stopping the execution.

    :param fn: boto3 client method to execute
    :param kwargs: Parameters for the AWS API call
    :return: API response or error dictionary
    """
    try:
        return fn(**kwargs)
    except ClientError as e:
        # Do not fail the entire inventory due to a single permission issue
        return {"__error__": str(e)}

# Collect inventory for a single AWS region ------------------------------
def collect_region_inventory(region: str) -> Dict[str, Any]:
    """
    Collects AWS infrastructure inventory for a specific region.

    All operations are read-only (Describe/List APIs).

    :param region: AWS region to query
    :return: Dictionary containing regional inventory data
    """
    
    ec2 = _client("ec2", region)
    elbv2 = _client("elbv2", region)

    data: Dict[str, Any] = {"region": region}

    # Core networking and compute resources ------------------------------
    data["vpcs"] = _safe_call(ec2.describe_vpcs).get("Vpcs", [])
    data["subnets"] = _safe_call(ec2.describe_subnets).get("Subnets", [])
    data["route_tables"] = _safe_call(ec2.describe_route_tables).get("RouteTables", [])
    data["internet_gateways"] = _safe_call(ec2.describe_internet_gateways).get("InternetGateways", [])
    data["nat_gateways"] = _safe_call(ec2.describe_nat_gateways).get("NatGateways", [])
    data["security_groups"] = _safe_call(ec2.describe_security_groups).get("SecurityGroups", [])
    data["network_interfaces"] = _safe_call(ec2.describe_network_interfaces).get("NetworkInterfaces", [])

    # EC2 Instances (paginated) ------------------------------------------
    instances: List[Dict[str, Any]] = []
    paginator = ec2.get_paginator("describe_instances")
    try:
        for page in paginator.paginate():
            for r in page.get("Reservations", []):
                instances.extend(r.get("Instances", []))
        data["instances"] = instances
    except ClientError as e:
        # If EC2 instances cannot be retrieved, continue execution --------
        data["instances"] = []
        data["instances__error__"] = str(e)

    # Load Balancers and Target Groups ------------------------------------
    data["load_balancers"] = _safe_call(elbv2.describe_load_balancers).get("LoadBalancers", [])
    data["target_groups"] = _safe_call(elbv2.describe_target_groups).get("TargetGroups", [])

    return data

# # Collect inventory across multiple regions -----------------------------
def collect_inventory(regions: List[str]) -> Dict[str, Any]:
    """
    Collects AWS inventory across multiple regions.

    :param regions: List of AWS regions
    :return: Aggregated inventory structure
    """
    
    return {
        "regions": regions,
        "items": [collect_region_inventory(r) for r in regions],
    }
