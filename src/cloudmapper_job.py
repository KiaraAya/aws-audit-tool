import os
import subprocess
from typing import List


def _run(cmd: list[str], cwd: str):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(
            "CloudMapper command failed:\n"
            f"CMD: {' '.join(cmd)}\n"
            f"STDOUT:\n{p.stdout}\n"
            f"STDERR:\n{p.stderr}\n"
        )
    return p.stdout


def run_cloudmapper(
    cloudmapper_dir: str,
    account_name: str,
    regions: List[str],
    prepare_flags: List[str] | None = None,
) -> None:
    prepare_flags = prepare_flags or [
        "--no-internal-edges",
        "--no-inter-rds-edges",
        "--collapse-asgs",
        "--no-azs",
        "--no-node-data",
    ]

    cloudmapper_py = os.path.join(cloudmapper_dir, "cloudmapper.py")
    if not os.path.exists(cloudmapper_py):
        raise FileNotFoundError(f"cloudmapper.py not found at {cloudmapper_py}")

    region_arg = ",".join(regions)

    # collect
    _run(["python", "cloudmapper.py", "collect", "--account", account_name, "--regions", region_arg], cwd=cloudmapper_dir)

    # prepare
    _run(["python", "cloudmapper.py", "prepare", "--account", account_name, *prepare_flags], cwd=cloudmapper_dir)
