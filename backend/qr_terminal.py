"""Desenha no terminal o QR code do endereço dos alunos (usado pelos scripts iniciar).

Uso: python qr_terminal.py http://192.168.0.10:8000/aluno
"""
import sys


def desenhar(texto: str) -> str:
    import segno
    qr = segno.make(texto, error="m", micro=False)
    m = [list(l) for l in qr.matrix]
    borda = 2
    n = len(m) + 2 * borda
    claro = lambda r, c: not (borda <= r < n - borda and borda <= c < n - borda and m[r - borda][c - borda])
    linhas = []
    # cada caractere representa 2 módulos na vertical; o "claro" é desenhado (fundo do terminal é escuro)
    for r in range(0, n, 2):
        s = ""
        for c in range(n):
            a, b = claro(r, c), (claro(r + 1, c) if r + 1 < n else False)
            s += "█" if a and b else "▀" if a else "▄" if b else " "
        linhas.append("   " + s)
    return "\n".join(linhas)


if __name__ == "__main__":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        print(desenhar(sys.argv[1]))
    except Exception:
        pass  # sem QR no terminal não impede o sistema de iniciar
