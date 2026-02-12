"""
CloudMapper runner.

Runs:
- collect
- prepare
- package full web UI as ZIP (offline site)
- optional webserver
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import socket
import shutil
from pathlib import Path
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------

def _run(cmd: list[str], cwd: str) -> str:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(
            "CloudMapper command failed\n"
            f"CMD: {' '.join(cmd)}\n"
            f"STDOUT:\n{p.stdout}\n"
            f"STDERR:\n{p.stderr}\n"
        )
    return p.stdout


def _is_port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) != 0


def _find_free_port(host: str, start_port: int, tries: int = 20) -> int:
    port = start_port
    for _ in range(tries):
        if _is_port_free(host, port):
            return port
        port += 1
    raise RuntimeError(f"No free port found starting at {start_port}")


# ----------------------------------------------------------------------
# Main CloudMapper execution
# ----------------------------------------------------------------------

def run_cloudmapper(
    cloudmapper_dir: str,
    account_name: str,
    regions: List[str],
    prepare_flags: Optional[List[str]] = None,
) -> None:
    """
    Runs:
    - collect
    - prepare
    """

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

    logger.info("CloudMapper collect: %s (%s)", account_name, region_arg)
    _run(
        [
            sys.executable,
            "cloudmapper.py",
            "collect",
            "--account",
            account_name,
            "--regions",
            region_arg,
        ],
        cwd=cloudmapper_dir,
    )

    logger.info("CloudMapper prepare: %s", account_name)
    _run(
        [
            sys.executable,
            "cloudmapper.py",
            "prepare",
            "--account",
            account_name,
            *prepare_flags,
        ],
        cwd=cloudmapper_dir,
    )


# ----------------------------------------------------------------------
# ZIP packaging (offline HTML site)
# ----------------------------------------------------------------------

def package_cloudmapper_site_zip(
    cloudmapper_dir: str,
    account_name: str,
    out_dir: str,
) -> str:
    """
    Packages CloudMapper web UI + account data into a ZIP.
    This produces an offline site you can open locally.
    """

    cm_dir = Path(cloudmapper_dir)
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    web_src = cm_dir / "web"
    data_src = cm_dir / "account-data" / account_name

    if not web_src.exists():
        raise FileNotFoundError(f"CloudMapper web/ not found at {web_src}")

    if not data_src.exists():
        raise FileNotFoundError(
            f"CloudMapper account data not found at {data_src}"
        )

    # Build temporary site folder
    site_root = out_path / f"cloudmapper_site_{account_name}"

    if site_root.exists():
        shutil.rmtree(site_root)

    site_root.mkdir()

    # Copy web UI
    shutil.copytree(web_src, site_root / "web")

    # Copy ONLY this account data
    shutil.copytree(
        data_src,
        site_root / "account-data" / account_name,
        dirs_exist_ok=True,
    )

    # Create ZIP
    zip_base = out_path / f"cloudmapper_{account_name}"
    zip_file = shutil.make_archive(str(zip_base), "zip", root_dir=str(site_root))

    logger.info("CloudMapper site ZIP created: %s", zip_file)
    return zip_file


# ----------------------------------------------------------------------
# Optional webserver
# ----------------------------------------------------------------------

def start_cloudmapper_webserver(
    cloudmapper_dir: str,
    port: int = 8000,
    public: bool = False,
    ipv6: bool = False,
) -> subprocess.Popen:
    """
    Starts CloudMapper webserver (non-blocking).
    Compatible with versions that support:
    --port
    --public
    --ipv6
    """

    port = _find_free_port("127.0.0.1", port)

    cmd = [
        sys.executable,
        "cloudmapper.py",
        "webserver",
        "--port",
        str(port),
    ]

    if public:
        cmd.append("--public")

    if ipv6:
        cmd.append("--ipv6")

    logger.info("Starting CloudMapper webserver on port %s", port)

    p = subprocess.Popen(
        cmd,
        cwd=cloudmapper_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    time.sleep(1.0)
    return p
