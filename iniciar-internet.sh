#!/usr/bin/env sh
# Coloca o sistema na internet (link https://...trycloudflare.com) sem precisar liberar Firewall ou rede.
cd "$(dirname "$0")"
./iniciar.sh &
python3 backend/tunel.py
