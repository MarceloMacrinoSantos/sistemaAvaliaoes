"""Publica o sistema na internet com um túnel gratuito da Cloudflare (sem conta, sem mexer em Firewall).

Útil quando a rede da escola não deixa os computadores se enxergarem.
Uso: python backend/tunel.py   (o sistema precisa estar rodando na porta 8000)
"""
import os
import platform
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PASTA = Path(__file__).resolve().parent.parent
BASE = "https://github.com/cloudflare/cloudflared/releases/latest/download/"


def executavel() -> Path:
    sistema, maq = platform.system(), platform.machine().lower()
    arm = maq in ("arm64", "aarch64")
    if sistema == "Windows":
        nome, arquivo = "cloudflared.exe", "cloudflared-windows-amd64.exe"
    elif sistema == "Linux":
        nome, arquivo = "cloudflared", "cloudflared-linux-arm64" if arm else "cloudflared-linux-amd64"
    else:
        sys.exit("No Mac, instale com:  brew install cloudflared   e rode:  cloudflared tunnel --url http://localhost:8000")
    destino = PASTA / nome
    if not destino.exists():
        print("Baixando o programa do túnel (cloudflared, ~30 MB, só na primeira vez)...")
        urllib.request.urlretrieve(BASE + arquivo, destino)
        if sistema != "Windows":
            destino.chmod(0o755)
    return destino


def esperar_sistema():
    print("Aguardando o sistema responder em http://localhost:8000 ...")
    for _ in range(180):
        try:
            urllib.request.urlopen("http://localhost:8000/api/saude", timeout=2)
            return
        except Exception:
            time.sleep(2)
    sys.exit("O sistema não respondeu. Abra primeiro o iniciar.bat e depois este túnel.")


def main():
    esperar_sistema()
    exe = executavel()
    cmd = [str(exe), "tunnel", "--no-autoupdate", "--protocol", "http2", "--url", "http://localhost:8000"]
    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True, errors="replace")
    link = None
    print("Criando o link público (pode levar até 30 segundos)...")
    for linha in proc.stderr:
        m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", linha)
        if m and not link:
            link = m.group(0)
            (PASTA / "link-internet.txt").write_text(link + "\n", encoding="utf-8")
            print("\n" + "=" * 62)
            print("  LINK PARA OS ALUNOS (funciona de qualquer rede/celular):")
            print(f"\n      {link}\n")
            try:
                from qr_terminal import desenhar
                print("  Ou escaneie com o celular:")
                print(desenhar(link.rstrip("/") + "/aluno"))
                print()
            except Exception:
                pass
            print("  O link também foi salvo em link-internet.txt")
            print("  Deixe ESTA janela e a do sistema abertas durante a prova.")
            print("  O link muda toda vez que o túnel é reiniciado.")
            print("=" * 62 + "\n")
        elif not link and ("ERR" in linha or "failed" in linha.lower()):
            print("  !", linha.strip())
    codigo = proc.wait()
    if not link:
        print("\nNão foi possível criar o link. A internet ou o proxy da escola pode estar bloqueando")
        print("a Cloudflare. Tente outra rede (ex.: roteador do celular) ou hospede no Render (ver README).")
    sys.exit(codigo)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
