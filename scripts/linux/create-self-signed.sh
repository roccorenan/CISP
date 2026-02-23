#!/usr/bin/env bash
set -e
# Uso:
#   create-self-signed.sh <CN> [IP] [OUTDIR]
# Exemplo:
#   create-self-signed.sh cisp.intranet 10.9.1.35 ./certs
CN="${1:-cisp.local}"
IP="${2:-}"
OUTDIR="${3:-./certs}"
mkdir -p "$OUTDIR"

# Gera configuração com Subject Alternative Name (SAN) para CN e IP (se informado)
cat > "$OUTDIR/openssl.cnf" <<EOF
[ req ]
default_bits       = 2048
distinguished_name = req_distinguished_name
req_extensions     = v3_req
prompt             = no

[ req_distinguished_name ]
CN = $CN

[ v3_req ]
subjectAltName = @alt_names

[ alt_names ]
DNS.1 = $CN
EOF

if [ -n "$IP" ]; then
  echo "IP.1 = $IP" >> "$OUTDIR/openssl.cnf"
fi

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout "$OUTDIR/cisp.key" -out "$OUTDIR/cisp.crt" \
  -config "$OUTDIR/openssl.cnf"

openssl dhparam -out "$OUTDIR/dhparam.pem" 2048
