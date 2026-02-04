# Importations ------------------------------------------------------------
import os
import subprocess
from typing import List

# Internal helper for executing CLI commands ------------------------------
def _run(cmd: list[str], cwd: str):
    """
    Executes a system command inside a specific working directory.
    Captures stdout and stderr for proper error handling.

    :param cmd: Command to execute (list of strings)
    :param cwd: Working directory where the command will be executed
    :raises RuntimeError: If the command execution fails
    :return: Command stdout output
    """
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    
    # If the command fails, raise a detailed error
    if p.returncode != 0:
        raise RuntimeError(
            "CloudMapper command failed:\n"
            f"CMD: {' '.join(cmd)}\n"
            f"STDOUT:\n{p.stdout}\n"
            f"STDERR:\n{p.stderr}\n"
        )
    return p.stdout

# Main CloudMapper execution logic -------------------------------------
def run_cloudmapper(
    cloudmapper_dir: str,
    account_name: str,
    regions: List[str],
    prepare_flags: List[str] | None = None,
) -> None:
    """
    Executes CloudMapper (collect + prepare) to automatically generate
    AWS network and infrastructure diagrams.

    :param cloudmapper_dir: Path to the cloned CloudMapper repository
    :param account_name: Logical AWS account name (e.g. CRIT)
    :param regions: List of AWS regions to query
    :param prepare_flags: Optional flags to reduce diagram visual noise
    """
    
    # Default flags for cleaner and readable diagrams ----------------
    prepare_flags = prepare_flags or [
        "--no-internal-edges",             # Remove unnecessary internal connections
        "--no-inter-rds-edges",            # Remove RDS-to-RDS edges
        "--collapse-asgs",                 # Collapse Auto Scaling Groups
        "--no-azs",                        # Hide Availability Zones
        "--no-node-data",                  # Hide node metadata
    ]

    # Validate CloudMapper installation path -------------------------
    cloudmapper_py = os.path.join(cloudmapper_dir, "cloudmapper.py")
    if not os.path.exists(cloudmapper_py):
        raise FileNotFoundError(f"cloudmapper.py not found at {cloudmapper_py}")

    # CloudMapper expects regions as a CSV string --------------------
    region_arg = ",".join(regions)

    # Step 1: Collects AWS data using read-only API calls ------------
    _run(["python", "cloudmapper.py", "collect", "--account", account_name, "--regions", region_arg], cwd=cloudmapper_dir)

    # Step 2: Prepare - Generates data.json and style.json for diagrams
    _run(["python", "cloudmapper.py", "prepare", "--account", account_name, *prepare_flags], cwd=cloudmapper_dir)
