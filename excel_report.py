# excel_report.py
"""
Excel reporting for aws-audit-tool.

Builds a multi-sheet Excel file with:
- Resource sheets (VPCs, Subnets, EC2, ...)
- Added services (EBS, RDS, ASG, DynamoDB, S3, IAM)
- Findings sheets (Security, Tags, Unused, RDS Risk, Network Overview, IAM Audit)
- Clean table formatting (filters, freeze header, auto-width)
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

REQUIRED_TAGS = ["Name", "Environment", "Owner", "CostCenter"]
RISK_PORTS = {22: "SSH", 3389: "RDP", 3306: "MySQL", 5432: "PostgreSQL"}
EXCEL_TABLE_STYLE = "TableStyleMedium18"


def sanitize_for_excel(obj: Any) -> Any:
    """Recursively remove timezone info from tz-aware datetimes for Excel compatibility."""
    if isinstance(obj, datetime) and obj.tzinfo is not None:
        return obj.replace(tzinfo=None)
    if isinstance(obj, dict):
        return {k: sanitize_for_excel(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_for_excel(x) for x in obj]
    return obj


def _tags_dict(tags_list) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for t in tags_list or []:
        k = t.get("Key")
        v = t.get("Value")
        if k:
            out[k] = v or ""
    return out


def _is_world_open(ip_ranges) -> bool:
    for r in ip_ranges or []:
        if r.get("CidrIp") == "0.0.0.0/0":
            return True
    return False


def _safe_table_name(name: str) -> str:
    n = re.sub(r"[^A-Za-z0-9_]", "_", name or "Sheet")
    if not re.match(r"^[A-Za-z_]", n):
        n = "_" + n
    return n[:250]


def format_sheet_as_table(ws, table_style: str = EXCEL_TABLE_STYLE) -> None:
    max_row = ws.max_row
    max_col = ws.max_column

    if max_row >= 1:
        ws.freeze_panes = "A2"

    if max_row < 2 or max_col < 1:
        return

    last_col_letter = get_column_letter(max_col)
    table_ref = f"A1:{last_col_letter}{max_row}"
    table_name = _safe_table_name(f"{ws.title}_Table")

    existing = {t.displayName for t in ws._tables}
    if table_name in existing:
        table_name = f"{table_name}_1"

    table = Table(displayName=table_name, ref=table_ref)
    table.tableStyleInfo = TableStyleInfo(
        name=table_style,
        showFirstColumn=False,
        showLastColumn=False,
        showRowStripes=True,
        showColumnStripes=False,
    )
    ws.add_table(table)

    for col in ws.columns:
        max_len = 0
        col_letter = col[0].column_letter
        for cell in col:
            v = cell.value
            if v is None:
                continue
            s = str(v)
            if len(s) > max_len:
                max_len = len(s)
        ws.column_dimensions[col_letter].width = min(max_len + 2, 45)


def apply_workbook_formatting(xlsx_path: str) -> None:
    wb = load_workbook(xlsx_path)
    for ws in wb.worksheets:
        format_sheet_as_table(ws, table_style=EXCEL_TABLE_STYLE)
    wb.save(xlsx_path)


def build_excel(inventory: Dict[str, Any], out_xlsx_path: str) -> None:
    """
    Build the Excel report.

    Expected structure:
    {
      "regions": [...],
      "global": {"s3_buckets": [...], "iam_users": [...], "account_aliases": [...]},
      "run_info": {...},
      "items": [ {"region": "...", ...}, ... ]
    }
    """
    items = inventory.get("items", []) or []
    global_block = inventory.get("global", {}) or {}
    run_info = inventory.get("run_info", {}) or {}

    s3_buckets_all = global_block.get("s3_buckets", []) or []
    iam_users_all = global_block.get("iam_users", []) or []
    account_aliases = global_block.get("account_aliases", []) or []

    vpcs_all, subnets_all, rts_all, sgs_all, ec2_all, lbs_all = [], [], [], [], [], []
    ebs_vols_all, rds_instances_all, rds_clusters_all, asgs_all, dynamodb_all = [], [], [], [], []

    tag_compliance, security_findings, unused_resources, rds_risk, network_overview = [], [], [], [], []

    route_assoc: dict[tuple[str, str], list[str]] = {}
    rt_has_igw: dict[tuple[str, str], bool] = {}

    for region_block in items:
        region = region_block.get("region")

        for v in region_block.get("vpcs", []):
            vpcs_all.append({
                "Region": region,
                "VpcId": v.get("VpcId"),
                "CidrBlock": v.get("CidrBlock"),
                "IsDefault": v.get("IsDefault"),
                "State": v.get("State"),
            })

        for s in region_block.get("subnets", []):
            subnets_all.append({
                "Region": region,
                "SubnetId": s.get("SubnetId"),
                "VpcId": s.get("VpcId"),
                "CidrBlock": s.get("CidrBlock"),
                "AvailabilityZone": s.get("AvailabilityZone"),
                "State": s.get("State"),
            })

        for rt in region_block.get("route_tables", []):
            rt_id = rt.get("RouteTableId")
            rts_all.append({
                "Region": region,
                "RouteTableId": rt_id,
                "VpcId": rt.get("VpcId"),
                "Associations": len(rt.get("Associations", []) or []),
                "Routes": len(rt.get("Routes", []) or []),
            })

            has_igw = False
            for r in rt.get("Routes", []) or []:
                if r.get("GatewayId", "").startswith("igw-") and r.get("DestinationCidrBlock") == "0.0.0.0/0":
                    has_igw = True
                    break
            rt_has_igw[(region, rt_id)] = has_igw

            for a in rt.get("Associations", []) or []:
                subnet_id = a.get("SubnetId")
                if subnet_id:
                    route_assoc.setdefault((region, subnet_id), []).append(rt_id)

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

            for perm in sg.get("IpPermissions", []) or []:
                from_p = perm.get("FromPort")
                to_p = perm.get("ToPort")
                if from_p is None or to_p is None:
                    continue
                if _is_world_open(perm.get("IpRanges", []) or []):
                    for p in range(int(from_p), int(to_p) + 1):
                        if p in RISK_PORTS:
                            security_findings.append({
                                "Region": region,
                                "Finding": "SecurityGroup open to world",
                                "Severity": "HIGH",
                                "GroupId": sg.get("GroupId"),
                                "GroupName": sg.get("GroupName"),
                                "Port": p,
                                "Service": RISK_PORTS[p],
                                "Cidr": "0.0.0.0/0",
                            })

        for ins in region_block.get("instances", []):
            tags = _tags_dict(ins.get("Tags", []) or [])
            name = tags.get("Name", "")

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

            missing = [t for t in REQUIRED_TAGS if not tags.get(t)]
            if missing:
                tag_compliance.append({
                    "Region": region,
                    "ResourceType": "EC2",
                    "ResourceId": ins.get("InstanceId"),
                    "Name": name,
                    "MissingTags": ", ".join(missing),
                })

            if ((ins.get("State") or {}).get("Name") == "stopped") and (ins.get("InstanceType") or "").startswith(("m", "c", "r")):
                unused_resources.append({
                    "Region": region,
                    "Type": "EC2 (Stopped large family)",
                    "ResourceId": ins.get("InstanceId"),
                    "Details": f"InstanceType={ins.get('InstanceType')}",
                })

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

        for v in region_block.get("ebs_volumes", []):
            atts = v.get("Attachments", []) or []
            instance_id = atts[0].get("InstanceId") if atts else ""
            device = atts[0].get("Device") if atts else ""
            tags = _tags_dict(v.get("Tags", []) or [])

            ebs_vols_all.append({
                "Region": region,
                "VolumeId": v.get("VolumeId"),
                "Type": v.get("VolumeType"),
                "SizeGiB": v.get("Size"),
                "State": v.get("State"),
                "Encrypted": v.get("Encrypted"),
                "Iops": v.get("Iops"),
                "Throughput": v.get("Throughput"),
                "AvailabilityZone": v.get("AvailabilityZone"),
                "AttachedInstanceId": instance_id,
                "Device": device,
            })

            if v.get("State") == "available" and not atts:
                unused_resources.append({
                    "Region": region,
                    "Type": "EBS (Unattached)",
                    "ResourceId": v.get("VolumeId"),
                    "Details": f"SizeGiB={v.get('Size')} Type={v.get('VolumeType')}",
                })

            missing = [t for t in REQUIRED_TAGS if not tags.get(t)]
            if missing:
                tag_compliance.append({
                    "Region": region,
                    "ResourceType": "EBS",
                    "ResourceId": v.get("VolumeId"),
                    "Name": tags.get("Name", ""),
                    "MissingTags": ", ".join(missing),
                })

        for db in region_block.get("rds_db_instances", []):
            rds_instances_all.append({
                "Region": region,
                "DBInstanceIdentifier": db.get("DBInstanceIdentifier"),
                "Engine": db.get("Engine"),
                "EngineVersion": db.get("EngineVersion"),
                "DBInstanceClass": db.get("DBInstanceClass"),
                "Status": db.get("DBInstanceStatus"),
                "MultiAZ": db.get("MultiAZ"),
                "StorageEncrypted": db.get("StorageEncrypted"),
                "PubliclyAccessible": db.get("PubliclyAccessible"),
                "BackupRetentionPeriod": db.get("BackupRetentionPeriod"),
                "AllocatedStorage": db.get("AllocatedStorage"),
                "Endpoint": (db.get("Endpoint") or {}).get("Address"),
            })

            if db.get("PubliclyAccessible") is True:
                rds_risk.append({"Region": region, "DB": db.get("DBInstanceIdentifier"), "Risk": "PubliclyAccessible = true", "Severity": "HIGH"})
            if db.get("StorageEncrypted") is False:
                rds_risk.append({"Region": region, "DB": db.get("DBInstanceIdentifier"), "Risk": "StorageEncrypted = false", "Severity": "MEDIUM"})
            if (db.get("BackupRetentionPeriod") or 0) == 0:
                rds_risk.append({"Region": region, "DB": db.get("DBInstanceIdentifier"), "Risk": "BackupRetentionPeriod = 0", "Severity": "MEDIUM"})

        for c in region_block.get("rds_db_clusters", []):
            rds_clusters_all.append({
                "Region": region,
                "DBClusterIdentifier": c.get("DBClusterIdentifier"),
                "Engine": c.get("Engine"),
                "EngineVersion": c.get("EngineVersion"),
                "Status": c.get("Status"),
                "MultiAZ": c.get("MultiAZ"),
                "Endpoint": c.get("Endpoint"),
                "ReaderEndpoint": c.get("ReaderEndpoint"),
            })

        for a in region_block.get("autoscaling_groups", []):
            tags = _tags_dict(a.get("Tags", []) or [])

            asgs_all.append({
                "Region": region,
                "AutoScalingGroupName": a.get("AutoScalingGroupName"),
                "MinSize": a.get("MinSize"),
                "MaxSize": a.get("MaxSize"),
                "DesiredCapacity": a.get("DesiredCapacity"),
                "VpcZoneIdentifier": a.get("VPCZoneIdentifier"),
                "LaunchTemplate": (a.get("LaunchTemplate") or {}).get("LaunchTemplateName"),
                "Instances": len(a.get("Instances", []) or []),
            })

            if (a.get("DesiredCapacity") or 0) == 0:
                unused_resources.append({
                    "Region": region,
                    "Type": "ASG (DesiredCapacity=0)",
                    "ResourceId": a.get("AutoScalingGroupName"),
                    "Details": f"Min={a.get('MinSize')} Max={a.get('MaxSize')}",
                })

            missing = [t for t in REQUIRED_TAGS if not tags.get(t)]
            if missing:
                tag_compliance.append({
                    "Region": region,
                    "ResourceType": "ASG",
                    "ResourceId": a.get("AutoScalingGroupName"),
                    "Name": tags.get("Name", ""),
                    "MissingTags": ", ".join(missing),
                })

        for t in region_block.get("dynamodb_tables", []):
            dynamodb_all.append({
                "Region": region,
                "TableName": t.get("TableName"),
                "Status": t.get("TableStatus"),
                "BillingMode": (t.get("BillingModeSummary") or {}).get("BillingMode"),
                "ItemCount": t.get("ItemCount"),
                "SizeBytes": t.get("TableSizeBytes"),
                "Arn": t.get("TableArn"),
            })

    for s in subnets_all:
        region = s["Region"]
        subnet_id = s["SubnetId"]
        rts = route_assoc.get((region, subnet_id), []) or []
        is_public = any(rt_has_igw.get((region, rt_id)) is True for rt_id in rts)

        network_overview.append({
            "Region": region,
            "VpcId": s.get("VpcId"),
            "SubnetId": subnet_id,
            "AZ": s.get("AvailabilityZone"),
            "CidrBlock": s.get("CidrBlock"),
            "SubnetType": "Public" if is_public else "Private/Unknown",
            "AssociatedRouteTables": ", ".join(rts) if rts else "",
        })

    iam_audit = [{
        "UserName": u.get("UserName"),
        "CreateDate": u.get("CreateDate"),
        "PasswordLastUsed": u.get("PasswordLastUsed"),
        "Arn": u.get("Arn"),
    } for u in iam_users_all]

    findings_summary = [{
        "Security_Findings": len(security_findings),
        "Tag_Compliance_Issues": len(tag_compliance),
        "Unused_Resources": len(unused_resources),
        "RDS_Risk_Items": len(rds_risk),
    }]

    run_info_rows = [{
        "timestamp_utc": run_info.get("timestamp_utc", ""),
        "regions": ", ".join(run_info.get("regions", []) or []),
        "account_name": run_info.get("account_name", ""),
        "account_id_env": run_info.get("account_id_env", ""),
        "sts_account": (run_info.get("sts_identity", {}) or {}).get("Account", ""),
        "sts_arn": (run_info.get("sts_identity", {}) or {}).get("Arn", ""),
        "account_aliases": ", ".join(account_aliases) if account_aliases else "",
    }]

    summary = [{
        "VPCs": len(vpcs_all),
        "Subnets": len(subnets_all),
        "RouteTables": len(rts_all),
        "SecurityGroups": len(sgs_all),
        "EC2Instances": len(ec2_all),
        "LoadBalancers": len(lbs_all),
        "EBSVolumes": len(ebs_vols_all),
        "RDSInstances": len(rds_instances_all),
        "RDSClusters": len(rds_clusters_all),
        "AutoScalingGroups": len(asgs_all),
        "DynamoDBTables": len(dynamodb_all),
        "S3Buckets": len(s3_buckets_all),
        "IAMUsers": len(iam_users_all),
    }]

    def df(records: Any) -> pd.DataFrame:
        return pd.DataFrame(sanitize_for_excel(records))

    with pd.ExcelWriter(out_xlsx_path, engine="openpyxl") as writer:
        df(vpcs_all).to_excel(writer, index=False, sheet_name="VPCs")
        df(subnets_all).to_excel(writer, index=False, sheet_name="Subnets")
        df(rts_all).to_excel(writer, index=False, sheet_name="RouteTables")
        df(sgs_all).to_excel(writer, index=False, sheet_name="SecurityGroups")
        df(ec2_all).to_excel(writer, index=False, sheet_name="EC2")
        df(lbs_all).to_excel(writer, index=False, sheet_name="LoadBalancers")

        df(ebs_vols_all).to_excel(writer, index=False, sheet_name="EBS_Volumes")
        df(rds_instances_all).to_excel(writer, index=False, sheet_name="RDS_Instances")
        df(rds_clusters_all).to_excel(writer, index=False, sheet_name="RDS_Clusters")
        df(asgs_all).to_excel(writer, index=False, sheet_name="AutoScaling")
        df(dynamodb_all).to_excel(writer, index=False, sheet_name="DynamoDB")

        df(s3_buckets_all).to_excel(writer, index=False, sheet_name="S3_Buckets")
        df(iam_users_all).to_excel(writer, index=False, sheet_name="IAM_Users")

        df(run_info_rows).to_excel(writer, index=False, sheet_name="Run_Info")
        df(findings_summary).to_excel(writer, index=False, sheet_name="Findings_Summary")
        df(tag_compliance).to_excel(writer, index=False, sheet_name="Tag_Compliance")
        df(security_findings).to_excel(writer, index=False, sheet_name="Security_Findings")
        df(unused_resources).to_excel(writer, index=False, sheet_name="Unused_Resources")
        df(rds_risk).to_excel(writer, index=False, sheet_name="RDS_Risk")
        df(network_overview).to_excel(writer, index=False, sheet_name="Network_Overview")
        df(iam_audit).to_excel(writer, index=False, sheet_name="IAM_Audit")

        df(summary).to_excel(writer, index=False, sheet_name="Summary")

    apply_workbook_formatting(out_xlsx_path)
