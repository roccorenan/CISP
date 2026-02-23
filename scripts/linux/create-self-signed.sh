#!/usr/bin/env bash
set -e
CN="${1:-cisp.local}"
OUTDIR="${2:-./certs}"
mkdir -p "$OUTDIR"
openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout "$OUTDIR/cisp.key" -out "$OUTDIR/cisp.crt" -subj "/CN=$CN"
openssl dhparam -out "$OUTDIR/dhparam.pem" 2048
