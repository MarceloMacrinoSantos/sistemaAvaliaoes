#!/usr/bin/env bash
# =====================================================================
#  Instala o Sistema de Avaliações numa VM Ubuntu (Oracle Cloud Always Free)
#  Uso (dentro da VM, na pasta do projeto):   sudo bash deploy/oracle/instalar.sh [dominio]
#    - sem domínio: usa um endereço gratuito do tipo 129-146-1-2.sslip.io, com HTTPS automático
#    - com domínio: aponte o DNS (registro A) para o IP da VM antes e passe o nome, ex.: provas.minhaescola.com.br
#  Pode ser rodado de novo sem problema (também serve para atualizar o sistema).
# =====================================================================
set -euo pipefail

[ "$(id -u)" -eq 0 ] || { echo "Rode com sudo:  sudo bash $0 $*"; exit 1; }
ORIGEM="$(cd "$(dirname "$0")/../.." && pwd)"      # pasta do projeto (onde está backend/ e frontend/)
APP=/opt/avaliacoes                               # código
DADOS=/var/lib/avaliacoes                         # banco de dados (fica fora do código: atualizar não apaga nada)
BACKUP=/var/backups/avaliacoes
USUARIO=avaliacoes

echo "==> 1/7 Pacotes do sistema"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip sqlite3 curl iptables-persistent >/dev/null
if ! command -v caddy >/dev/null; then
  apt-get install -y -qq caddy >/dev/null 2>&1 || {
    apt-get install -y -qq debian-keyring debian-archive-keyring apt-transport-https gnupg >/dev/null
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor --yes -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
    apt-get update -qq && apt-get install -y -qq caddy >/dev/null
  }
fi

echo "==> 2/7 Usuário e pastas"
id "$USUARIO" >/dev/null 2>&1 || useradd --system --home "$APP" --shell /usr/sbin/nologin "$USUARIO"
mkdir -p "$APP" "$DADOS" "$BACKUP"

echo "==> 3/7 Copiando o sistema para $APP"
if [ -f "$DADOS/avaliacoes.db" ]; then   # atualização: backup antes de trocar o código
  sqlite3 "$DADOS/avaliacoes.db" ".backup '$BACKUP/antes-da-atualizacao-$(date +%F-%H%M).db'"
fi
rm -rf "$APP/backend" "$APP/frontend"
cp -r "$ORIGEM/backend" "$ORIGEM/frontend" "$APP/"
rm -rf "$APP/backend/.venv" "$APP/backend/avaliacoes.db"* "$APP/frontend/node_modules"
# banco que você trouxe do seu computador (copie para ~/avaliacoes.db antes de rodar)
for candidato in /home/*/avaliacoes.db "$ORIGEM/backend/avaliacoes.db"; do
  if [ -f "$candidato" ] && [ ! -f "$DADOS/avaliacoes.db" ]; then
    echo "    Importando banco existente: $candidato"
    sqlite3 "$candidato" ".backup '$DADOS/avaliacoes.db'"
  fi
done

echo "==> 4/7 Ambiente Python (pode levar alguns minutos na primeira vez)"
python3 -m venv "$APP/venv"
"$APP/venv/bin/pip" install -q --upgrade pip
"$APP/venv/bin/pip" install -q -r "$APP/backend/requirements.txt"

echo "==> 5/7 Configuração e serviço"
if [ ! -f /etc/avaliacoes.env ]; then
  cat > /etc/avaliacoes.env <<CONF
DATABASE_URL=sqlite:///$DADOS/avaliacoes.db
SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')
ADMIN_LOGIN=admin
ADMIN_SENHA=$(python3 -c 'import secrets; print(secrets.token_urlsafe(9))')
BCRYPT_ROUNDS=10
FRONTEND_DIST=$APP/frontend/dist
CONF
  chmod 600 /etc/avaliacoes.env
  NOVO=1
fi
chown -R "$USUARIO:$USUARIO" "$APP" "$DADOS"
cat > /etc/systemd/system/avaliacoes.service <<UNIT
[Unit]
Description=Sistema de Avaliacoes
After=network.target

[Service]
User=$USUARIO
WorkingDirectory=$APP/backend
EnvironmentFile=/etc/avaliacoes.env
ExecStart=$APP/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2 --proxy-headers --forwarded-allow-ips=127.0.0.1
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now avaliacoes >/dev/null
systemctl restart avaliacoes

echo "==> 6/7 Endereço, HTTPS e firewall"
IP=$(curl -s --max-time 5 https://ifconfig.me || curl -s --max-time 5 https://api.ipify.org || true)
DOMINIO="${1:-}"
if [ -z "$DOMINIO" ]; then
  [ -n "$IP" ] || { echo "Não consegui descobrir o IP público. Rode de novo informando o domínio."; exit 1; }
  DOMINIO="$(echo "$IP" | tr . -).sslip.io"
fi
cat > /etc/caddy/Caddyfile <<CADDY
$DOMINIO {
    encode gzip
    reverse_proxy 127.0.0.1:8000
}
CADDY
systemctl restart caddy
# a imagem Ubuntu da Oracle bloqueia portas no iptables: libera 80 e 443
for PORTA in 80 443; do
  iptables -C INPUT -p tcp --dport $PORTA -m state --state NEW -j ACCEPT 2>/dev/null ||
    iptables -I INPUT -p tcp --dport $PORTA -m state --state NEW -j ACCEPT
done
netfilter-persistent save >/dev/null 2>&1 || true

echo "==> 7/7 Backup diário do banco (03h, guarda 30 dias)"
cat > /etc/cron.daily/avaliacoes-backup <<'BK'
#!/bin/sh
D=/var/backups/avaliacoes
sqlite3 /var/lib/avaliacoes/avaliacoes.db ".backup '$D/avaliacoes-$(date +%F).db'"
find "$D" -name 'avaliacoes-*.db' -mtime +30 -delete
BK
chmod +x /etc/cron.daily/avaliacoes-backup

sleep 3
if curl -s --max-time 5 http://127.0.0.1:8000/api/saude | grep -q ok; then ESTADO="rodando ✔"; else ESTADO="NÃO respondeu — veja: sudo journalctl -u avaliacoes -n 50"; fi
echo
echo "=================================================================="
echo " Sistema: $ESTADO"
echo " Endereço: https://$DOMINIO"
echo "   (o certificado HTTPS é emitido no primeiro acesso; pode levar 1 minuto)"
if [ "${NOVO:-0}" = 1 ]; then
  echo
  echo " Administrador:  login admin   senha $(grep ADMIN_SENHA /etc/avaliacoes.env | cut -d= -f2)"
  echo " ANOTE ESTA SENHA (ela só é usada se o banco for novo; troque depois de entrar)."
fi
echo
echo " Comandos úteis:"
echo "   sudo systemctl restart avaliacoes      reiniciar o sistema"
echo "   sudo journalctl -u avaliacoes -f       ver o registro (log)"
echo "   ls /var/backups/avaliacoes             backups diários do banco"
echo "=================================================================="
