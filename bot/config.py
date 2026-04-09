# ---------------------------------------------------------
# config.py
# Bot configuration for connection to EC2
# ---------------------------------------------------------

AWS_PROFILE = "aws-audit-sso"
AWS_REGION = "us-east-1"

EC2_INSTANCE_ID = "i-00d6d25daf954f723"
EC2_IP = "3.236.249.127"
EC2_USER = "ec2-user"
EC2_AZ = "us-east-1a"

REMOTE_PROJECT_DIR = "/home/ec2-user/aws-audit-tool"
REMOTE_VENV_ACTIVATE = "/home/ec2-user/aws-audit-tool/.venv/bin/activate"

# Active mode for EC2 connection
AUTH_MODE = "keypair"

# Folder that contains exactly one .pem file
KEYPAIR_DIR = r"C:\keys"

# S3 settings used by the remote execution
AWS_AUDIT_S3_BUCKET = "aws-audit-tool-crit"
AWS_AUDIT_S3_PREFIX = "aws-audit-tool"