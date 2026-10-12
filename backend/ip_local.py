"""Mostra os IPs deste computador na rede local (usado pelos scripts iniciar).

Uso: python ip_local.py        -> IP principal
     python ip_local.py todos  -> todos os IPs (útil quando há VPN, VirtualBox, cabo + Wi-Fi)
"""
import socket
import sys


def principal() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))  # não envia nada; só descobre a interface de rede
        return s.getsockname()[0]
    except OSError:
        return "localhost"


def todos() -> list[str]:
    ips = {principal()}
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    return sorted(ip for ip in ips if not ip.startswith("127.") and ip != "localhost")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        for ip in todos():
            print(f"   http://{ip}:8000")
    else:
        print(principal())
