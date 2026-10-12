#!/usr/bin/env sh
# Inicia o sistema na rede local (Linux/Mac). Uso: ./iniciar.sh
cd "$(dirname "$0")"
PY=python3; command -v $PY >/dev/null || PY=python
# o .venv não funciona se a pasta foi copiada de outro computador: recria se estiver quebrado
if [ -d backend/.venv ] && ! backend/.venv/bin/python -c "import fastapi" >/dev/null 2>&1; then rm -rf backend/.venv; fi
[ -d backend/.venv ] || $PY -m venv backend/.venv
. backend/.venv/bin/activate
pip install -q -r backend/requirements.txt
python backend/porta_livre.py || exit 1
if [ ! -f frontend/dist/index.html ]; then
  (cd frontend && npm install && npm run build) || { echo "Instale o Node.js para compilar o frontend"; exit 1; }
fi
IP=$(python backend/ip_local.py)
echo ""
echo "=========================================================="
echo " Sistema de Avaliações no ar!"
echo " Neste computador:        http://localhost:8000"
echo " Alunos (mesma rede/Wi-Fi): http://$IP:8000"
echo " QR code para os alunos (ou abra http://localhost:8000/qrcode para projetar):"
python backend/qr_terminal.py "http://$IP:8000/aluno"
echo " Outros endereços deste computador:"; python backend/ip_local.py todos
echo " Para encerrar: Ctrl+C"
echo "=========================================================="
cd backend && exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
