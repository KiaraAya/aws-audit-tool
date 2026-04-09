# ---------------------------------------------------------
# aws_actions.py
# Remote EC2 execution using:
# 1) IAM Identity Center + EC2 Instance Connect
# 2) SSH Key Pair (temporary fallback)
# ---------------------------------------------------------

import io
import os
import stat
import time
import glob
import posixpath
import paramiko
import boto3

from config import (
    AUTH_MODE,
    KEYPAIR_DIR,
    AWS_PROFILE,
    AWS_REGION,
    EC2_INSTANCE_ID,
    EC2_IP,
    EC2_USER,
    EC2_AZ,
    REMOTE_PROJECT_DIR,
    REMOTE_VENV_ACTIVATE,
    AWS_AUDIT_S3_BUCKET,
    AWS_AUDIT_S3_PREFIX,
)


# Validates the AWS SSO session by attempting to retrieve the caller identity
def validate_sso_session():
    try:
        session = _get_boto3_session()
        sts = session.client("sts")
        identity = sts.get_caller_identity()
        return True, identity["Arn"]
    except Exception as e:
        return False, str(e)


# Builds the remote command to run the audit tool on the EC2 instance
def _build_remote_command(regions, run_cloudmapper=True):
    region_string = ",".join(regions)
    cloudmapper_flag = "1" if run_cloudmapper else "0"

    return f"""
    bash -lc '
    cd {REMOTE_PROJECT_DIR}
    source {REMOTE_VENV_ACTIVATE}
    export AWS_AUDIT_REGIONS="{region_string}"
    export AWS_AUDIT_RUN_CLOUDMAPPER="{cloudmapper_flag}"
    export AWS_AUDIT_S3_BUCKET="{AWS_AUDIT_S3_BUCKET}"
    export AWS_AUDIT_S3_PREFIX="{AWS_AUDIT_S3_PREFIX}"
    python main.py
    '
    """


# Creates a boto3 session using the SSO profile configured on the local machine
def _get_boto3_session():
    return boto3.Session(
        profile_name=AWS_PROFILE,
        region_name=AWS_REGION,
    )


# Generates a temporary SSH key pair in memory
def _generate_temporary_ssh_keypair():
    key = paramiko.RSAKey.generate(2048)

    private_buffer = io.StringIO()
    key.write_private_key(private_buffer)
    private_key_str = private_buffer.getvalue()

    public_key_str = f"{key.get_name()} {key.get_base64()}"

    return private_key_str, public_key_str


# Sends the temporary public key to the EC2 instance using EC2 Instance Connect
def _send_ssh_public_key(public_key: str):
    session = _get_boto3_session()
    eic = session.client("ec2-instance-connect")

    return eic.send_ssh_public_key(
        InstanceId=EC2_INSTANCE_ID,
        InstanceOSUser=EC2_USER,
        SSHPublicKey=public_key,
        AvailabilityZone=EC2_AZ,
    )


# Finds the only .pem file inside KEYPAIR_DIR
def _find_single_pem_file():
    pem_files = glob.glob(os.path.join(KEYPAIR_DIR, "*.pem"))

    if not pem_files:
        raise FileNotFoundError(
            f"No .pem file was found in {KEYPAIR_DIR}"
        )

    if len(pem_files) > 1:
        raise RuntimeError(
            f"Multiple .pem files were found in {KEYPAIR_DIR}. "
            "Please leave only one .pem file in that folder."
        )

    return pem_files[0]


# Shared SSH connection helper
def _connect_ssh_with_private_key(private_key_obj):
    last_error = None

    for _ in range(3):
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            ssh.connect(
                hostname=EC2_IP,
                username=EC2_USER,
                pkey=private_key_obj,
                timeout=20,
                look_for_keys=False,
                allow_agent=False,
            )

            return ssh

        except Exception as e:
            last_error = e
            time.sleep(1)

    raise last_error


# Opens an SSH connection using the temporary private key generated in memory
def _connect_ssh_with_temporary_key(private_key_str: str):
    private_key_obj = paramiko.RSAKey.from_private_key(io.StringIO(private_key_str))
    return _connect_ssh_with_private_key(private_key_obj)


# Opens an SSH connection using the .pem key found in KEYPAIR_DIR
def _connect_ssh_with_keypair():
    pem_path = _find_single_pem_file()
    private_key_obj = paramiko.RSAKey.from_private_key_file(pem_path)
    return _connect_ssh_with_private_key(private_key_obj)


# Opens an SSH connection using the currently configured auth mode
def _connect_for_current_mode():
    if AUTH_MODE == "keypair":
        return _connect_ssh_with_keypair()

    if AUTH_MODE == "sso":
        is_valid, auth_message = validate_sso_session()
        if not is_valid:
            raise RuntimeError(f"SSO session is not active: {auth_message}")

        private_key_str, public_key_str = _generate_temporary_ssh_keypair()
        response = _send_ssh_public_key(public_key_str)

        if not response.get("Success"):
            raise RuntimeError(f"Failed to send SSH public key: {response}")

        return _connect_ssh_with_temporary_key(private_key_str)

    raise RuntimeError(f"Unsupported AUTH_MODE: {AUTH_MODE}")


# Runs the audit script remotely on the EC2 instance
def run_audit(regions, run_cloudmapper=True):
    ssh = None

    try:
        if not regions:
            return False, "Please select at least one region."

        command = _build_remote_command(regions, run_cloudmapper)
        ssh = _connect_for_current_mode()

        stdin, stdout, stderr = ssh.exec_command(command)

        output = stdout.read().decode(errors="replace")
        errors = stderr.read().decode(errors="replace")
        exit_status = stdout.channel.recv_exit_status()

        if exit_status != 0:
            return False, errors or output or f"Remote command failed with exit status {exit_status}"

        return True, output or "Audit executed successfully."

    except Exception as e:
        return False, str(e)

    finally:
        if ssh:
            ssh.close()


# Downloads the latest report folder directly from the EC2 outputs directory
def download_reports(selected_folder):
    ssh = None
    sftp = None

    try:
        if not selected_folder or selected_folder == "No folder selected":
            return False, "Please select a local folder first."

        ssh = _connect_for_current_mode()
        sftp = ssh.open_sftp()

        remote_outputs_dir = posixpath.join(REMOTE_PROJECT_DIR, "outputs")

        # Find latest timestamped output folder in EC2
        stdin, stdout, stderr = ssh.exec_command(
            f'ls -1dt "{remote_outputs_dir}"/* 2>/dev/null | head -n 1'
        )
        latest_remote_dir = stdout.read().decode().strip()
        error_text = stderr.read().decode().strip()

        if not latest_remote_dir:
            return False, error_text or "No output folders were found on the EC2 instance."

        local_target_dir = os.path.join(
            selected_folder,
            os.path.basename(latest_remote_dir)
        )
        os.makedirs(local_target_dir, exist_ok=True)

        downloaded_files = []

        for entry in sftp.listdir_attr(latest_remote_dir):
            remote_path = posixpath.join(latest_remote_dir, entry.filename)

            if stat.S_ISDIR(entry.st_mode):
                continue

            local_path = os.path.join(local_target_dir, entry.filename)
            sftp.get(remote_path, local_path)
            downloaded_files.append(entry.filename)

        if not downloaded_files:
            return False, "The latest output folder exists, but no files were found to download."

        return True, (
            f"Reports downloaded successfully from EC2.\n"
            f"Remote folder: {latest_remote_dir}\n"
            f"Local folder: {local_target_dir}\n"
            f"Files: {', '.join(downloaded_files)}"
        )

    except Exception as e:
        return False, str(e)

    finally:
        if sftp:
            sftp.close()
        if ssh:
            ssh.close()