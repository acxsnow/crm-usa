#!/bin/sh
# Certificado autofirmado para abrir la app por HTTPS desde el celular en la
# red local (el GPS del navegador exige HTTPS). Solo para desarrollo.
#
#   sh frontend/scripts/dev-cert.sh            # detecta la IP de la red local
#   sh frontend/scripts/dev-cert.sh 192.168.1.20
#   DEV_HTTPS=1 docker compose up frontend      # luego abre https://<IP>:5173
set -e
cd "$(dirname "$0")/.."
IP="${1:-$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')}"
mkdir -p .certs
openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
  -keyout .certs/dev.key -out .certs/dev.crt -subj "/CN=crm-dev" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1${IP:+,IP:$IP}" >/dev/null 2>&1
echo "Certificado listo en frontend/.certs (IP: ${IP:-solo localhost})."
echo "Arranca con: DEV_HTTPS=1 docker compose up frontend  y abre https://${IP:-localhost}:5173"
