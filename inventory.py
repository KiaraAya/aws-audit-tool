import boto3
from botocore.exceptions import ClientError
from typing import Dict, Any, List


def _client(service: str, region: str):
    return boto3.client(service, region_name=region)


def _safe_call(fn, **kwargs):
    try:
        return fn(**kwargs)
    except ClientError as e:
        # No reventar todo por un servicio sin permisos, solo registrar el error.
        return {"__error__": str(e)}


def collect_region_inventory(region: str) -> Dict[str, Any]:
    ec2 = _client("ec2", region)
    elbv2 = _client("elbv2", region)

    data: Dict[str, Any] = {"region": region}

    # VPCs / Subnets / RT / IGW / NAT / SG / ENIs / Instances
    data["vpcs"] = _safe_call(ec2.describe_vpcs).get("Vpcs", [])
    data["subnets"] = _safe_call(ec2.describe_subnets).get("Subnets", [])
    data["route_tables"] = _safe_call(ec2.describe_route_tables).get("RouteTables", [])
    data["internet_gateways"] = _safe_call(ec2.describe_internet_gateways).get("InternetGateways", [])
    data["nat_gateways"] = _safe_call(ec2.describe_nat_gateways).get("NatGateways", [])
    data["security_groups"] = _safe_call(ec2.describe_security_groups).get("SecurityGroups", [])
    data["network_interfaces"] = _safe_call(ec2.describe_network_interfaces).get("NetworkInterfaces", [])

    # EC2 instances (paginado)
    instances: List[Dict[str, Any]] = []
    paginator = ec2.get_paginator("describe_instances")
    try:
        for page in paginator.paginate():
            for r in page.get("Reservations", []):
                instances.extend(r.get("Instances", []))
        data["instances"] = instances
    except ClientError as e:
        data["instances"] = []
        data["instances__error__"] = str(e)

    # Load Balancers / Target Groups (ALB/NLB)
    data["load_balancers"] = _safe_call(elbv2.describe_load_balancers).get("LoadBalancers", [])
    data["target_groups"] = _safe_call(elbv2.describe_target_groups).get("TargetGroups", [])

    return data


def collect_inventory(regions: List[str]) -> Dict[str, Any]:
    return {
        "regions": regions,
        "items": [collect_region_inventory(r) for r in regions],
    }
