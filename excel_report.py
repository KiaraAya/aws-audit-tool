# Importations ------------------------------------------------------------
import pandas as pd
from typing import Dict, Any, List

# Helper to extract selected columns from items ---------------------------
def _rows(items: List[Dict[str, Any]], cols: List[str]) -> List[Dict[str, Any]]:
    """
    Extracts a subset of keys from a list of dictionaries.

    :param items: List of dictionaries (AWS resources)
    :param cols: List of keys to extract
    :return: List of dictionaries with selected keys only
    """
    out = []
    for it in items or []:
        row = {}
        for c in cols:
            row[c] = it.get(c)
        out.append(row)
    return out

# Excel report builder -------------------------------------------------
def build_excel(inventory: Dict[str, Any], out_xlsx_path: str) -> None:
    """
    Builds an Excel report from the AWS inventory structure.

    The inventory dictionary is expected to be the output of
    collect_inventory() from inventory.py.

    :param inventory: Aggregated AWS inventory data
    :param out_xlsx_path: Final path where the Excel file will be written
    """
    
    # Inventory items grouped by region ---------------------------------
    items = inventory.get("items", [])

    # Global accumulators (all regions combined) ------------------------
    vpcs_all = []
    subnets_all = []
    rts_all = []
    sgs_all = []
    ec2_all = []
    lbs_all = []

    # Iterate through each region block --------------------------------
    for region_block in items:
        region = region_block.get("region")

        # VPCs ---------------------------------------------------------
        for v in region_block.get("vpcs", []):
            vpcs_all.append({
                "Region": region,
                "VpcId": v.get("VpcId"),
                "CidrBlock": v.get("CidrBlock"),
                "IsDefault": v.get("IsDefault"),
                "State": v.get("State"),
            })

        # Subnets ------------------------------------------------------
        for s in region_block.get("subnets", []):
            subnets_all.append({
                "Region": region,
                "SubnetId": s.get("SubnetId"),
                "VpcId": s.get("VpcId"),
                "CidrBlock": s.get("CidrBlock"),
                "AvailabilityZone": s.get("AvailabilityZone"),
                "State": s.get("State"),
            })

        # Route tables ------------------------------------------------
        for rt in region_block.get("route_tables", []):
            # Get the vpcId if it is provided
            rts_all.append({
                "Region": region,
                "RouteTableId": rt.get("RouteTableId"),
                "VpcId": rt.get("VpcId"),
                "Associations": len(rt.get("Associations", []) or []),
                "Routes": len(rt.get("Routes", []) or []),
            })

        # Security Groups----------------------------------------------
        for sg in region_block.get("security_groups", []):
            sgs_all.append({
                "Region": region,
                "GroupId": sg.get("GroupId"),
                "GroupName": sg.get("GroupName"),
                "VpcId": sg.get("VpcId"),
                "IngressRules": len(sg.get("IpPermissions", []) or []),
                "EgressRules": len(sg.get("IpPermissionsEgress", []) or []),
                "Description": sg.get("Description"),
            })

        # EC2 instances ------------------------------------------------
        for ins in region_block.get("instances", []):
            # Extract Name tag if present
            name = ""
            for t in ins.get("Tags", []) or []:
                if t.get("Key") == "Name":
                    name = t.get("Value") or ""
                    break

            ec2_all.append({
                "Region": region,
                "InstanceId": ins.get("InstanceId"),
                "Name": name,
                "InstanceType": ins.get("InstanceType"),
                "State": (ins.get("State") or {}).get("Name"),
                "VpcId": ins.get("VpcId"),
                "SubnetId": ins.get("SubnetId"),
                "PrivateIp": ins.get("PrivateIpAddress"),
                "PublicIp": ins.get("PublicIpAddress"),
            })

        # Load balancers ---------------------------------------------
        for lb in region_block.get("load_balancers", []):
            lbs_all.append({
                "Region": region,
                "LoadBalancerArn": lb.get("LoadBalancerArn"),
                "Name": lb.get("LoadBalancerName"),
                "Type": lb.get("Type"),
                "Scheme": lb.get("Scheme"),
                "VpcId": lb.get("VpcId"),
                "State": (lb.get("State") or {}).get("Code"),
                "DNSName": lb.get("DNSName"),
            })

    # Write Excel file -----------------------------------------------
    with pd.ExcelWriter(out_xlsx_path, engine="openpyxl") as writer:
        pd.DataFrame(vpcs_all).to_excel(writer, index=False, sheet_name="VPCs")
        pd.DataFrame(subnets_all).to_excel(writer, index=False, sheet_name="Subnets")
        pd.DataFrame(rts_all).to_excel(writer, index=False, sheet_name="RouteTables")
        pd.DataFrame(sgs_all).to_excel(writer, index=False, sheet_name="SecurityGroups")
        pd.DataFrame(ec2_all).to_excel(writer, index=False, sheet_name="EC2")
        pd.DataFrame(lbs_all).to_excel(writer, index=False, sheet_name="LoadBalancers")

        # Summary sheet ----------------------------------------------
        summary = [{
            "VPCs": len(vpcs_all),
            "Subnets": len(subnets_all),
            "RouteTables": len(rts_all),
            "SecurityGroups": len(sgs_all),
            "EC2Instances": len(ec2_all),
            "LoadBalancers": len(lbs_all),
        }]
        pd.DataFrame(summary).to_excel(writer, index=False, sheet_name="Summary")
