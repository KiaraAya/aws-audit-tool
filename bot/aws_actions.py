import paramiko


EC2_IP = "3.236.249.127"
EC2_USER = "ec2-user"
KEY_PATH = r"C:\keys\cloudmapperkey.pem"


def run_audit(regions, run_cloudmapper=True):
    try:
        region_string = ",".join(regions)
        cloudmapper_flag = "1" if run_cloudmapper else "0"

        command = f"""
        bash -lc '
        cd /home/ec2-user/aws-audit-tool
        source .venv/bin/activate
        export AWS_AUDIT_REGIONS="{region_string}"
        export AWS_AUDIT_RUN_CLOUDMAPPER="{cloudmapper_flag}"
        python main.py
        '
        """

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        ssh.connect(
            hostname=EC2_IP,
            username=EC2_USER,
            key_filename=KEY_PATH,
        )

        stdin, stdout, stderr = ssh.exec_command(command)

        output = stdout.read().decode()
        errors = stderr.read().decode()

        ssh.close()

        if errors.strip():
            return False, errors

        return True, output or "Audit executed successfully."

    except Exception as e:
        return False, str(e)


def download_reports(selected_folder):
    return True, f"Download placeholder.\nSelected folder: {selected_folder}"
