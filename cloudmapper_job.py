# cloudmapper_job.py
"""
CloudMapper runner.

Runs:
- collect
- prepare
Optionally:
- start webserver
- export an HTML snapshot
"""

from __future__ import annotations

import os
import subprocess
import time
import socket
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


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


def run_cloudmapper(
    cloudmapper_dir: str,
    account_name: str,
    regions: List[str],
    prepare_flags: Optional[List[str]] = None,
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

    logger.info("CloudMapper collect: %s (%s)", account_name, region_arg)
    _run(["python", "cloudmapper.py", "collect", "--account", account_name, "--regions", region_arg], cwd=cloudmapper_dir)

    logger.info("CloudMapper prepare: %s", account_name)
    _run(["python", "cloudmapper.py", "prepare", "--account", account_name, *prepare_flags], cwd=cloudmapper_dir)


def export_cloudmapper_html(
    cloudmapper_dir: str,
    account_name: str,
    out_dir: str,
) -> str:
    """
    Creates a self-contained HTML export (snapshot) for the account diagrams.

    CloudMapper has an `export` command in most installs. If your CloudMapper
    fork/version doesn't have it, tell me what `python cloudmapper.py -h` shows
    and I adapt it.
    """
    os.makedirs(out_dir, exist_ok=True)
    out_html = os.path.join(out_dir, f"cloudmapper_{account_name}.html")

    # Common command in CloudMapper versions:
    # python cloudmapper.py export --account <name> --output <file>
    logger.info("CloudMapper export html -> %s", out_html)
    _run(["python", "cloudmapper.py", "export", "--account", account_name, "--output", out_html], cwd=cloudmapper_dir)
    return out_html


def start_cloudmapper_webserver(
    cloudmapper_dir: str,
    account_name: str,
    bind: str = "127.0.0.1",
    port: int = 8000,
) -> subprocess.Popen:
    """
    Starts CloudMapper webserver as a subprocess (non-blocking).
    Returns the Popen handle so caller can keep it alive or terminate it.
    """
    port = _find_free_port(bind, port)

    logger.info("Starting CloudMapper webserver: http://%s:%s", bind, port)
    # webserver usually does NOT require --account; it serves files under web/
    # but leaving account_name here doesn't hurt if your version supports it.
    p = subprocess.Popen(
        ["python", "cloudmapper.py", "webserver", "--bind", bind, "--port", str(port)],
        cwd=cloudmapper_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Give it a moment to boot
    time.sleep(1.0)
    return p
