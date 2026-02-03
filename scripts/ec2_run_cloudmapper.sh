#!/usr/bin/env bash
set -euo pipefail

ACCOUNT_NAME="${1:-CRIT}"
S3_BUCKET="${2:?missing bucket}"
S3_PREFIX="${3:-cloudmapper}"

cd ~/cloudmapper
source venv/bin/activate

# Limpia data previa
rm -f web/data.json web/style.json || true

# Collect + Prepare (con flags que ya usaste para hacerlo legible)
python cloudmapper.py collect --account "$ACCOUNT_NAME"
python cloudmapper.py prepare --account "$ACCOUNT_NAME" \
  --no-internal-edges \
  --no-inter-rds-edges \
  --collapse-asgs \
  --no-azs \
  --no-node-data

# Empaquetar web output
TS="$(date +%Y%m%d_%H%M%S)"
OUT="/tmp/cloudmapper_${ACCOUNT_NAME}_${TS}.tar.gz"
tar -czf "$OUT" web/

# Subir a S3
aws s3 cp "$OUT" "s3://${S3_BUCKET}/${S3_PREFIX}/${ACCOUNT_NAME}/${TS}/cloudmapper_web.tar.gz"

echo "OK uploaded: s3://${S3_BUCKET}/${S3_PREFIX}/${ACCOUNT_NAME}/${TS}/cloudmapper_web.tar.gz"
