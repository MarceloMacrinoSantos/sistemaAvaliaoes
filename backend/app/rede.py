"""Endereços pelos quais os alunos alcançam este servidor (para o QR code de acesso)."""
import socket

from fastapi import Request


def ips_locais() -> list[str]:
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))  # não envia nada; só descobre a interface principal
        ips.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            if info[4][0] not in ips:
                ips.append(info[4][0])
    except OSError:
        pass
    return [ip for ip in ips if not ip.startswith("127.")]


def enderecos(request: Request) -> list[str]:
    host = (request.headers.get("x-forwarded-host") or request.url.hostname or "").split(":")[0]
    esquema = request.headers.get("x-forwarded-proto") or request.url.scheme
    origem = f"{esquema}://{request.headers.get('x-forwarded-host') or request.headers.get('host')}"
    if host in ("localhost", "127.0.0.1", "::1", ""):
        # professor abriu pelo próprio computador: o aluno precisa do IP da rede
        porta = request.url.port or (443 if esquema == "https" else 80)
        sufixo = "" if porta in (80, 443) else f":{porta}"
        lista = [f"{esquema}://{ip}{sufixo}" for ip in ips_locais()]
        return lista or [origem]
    return [origem]
