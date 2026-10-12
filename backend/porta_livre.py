"""Sai com erro se a porta 8000 já estiver em uso (outra cópia do sistema aberta)."""
import socket
import sys

s = socket.socket()
try:
    s.bind(("0.0.0.0", 8000))
except OSError:
    print("\n  ATENCAO: ja existe um sistema aberto usando a porta 8000.")
    print("  Provavelmente e a janela preta de uma versao ANTIGA. Feche-a e rode este arquivo de novo.\n")
    sys.exit(1)
finally:
    s.close()
