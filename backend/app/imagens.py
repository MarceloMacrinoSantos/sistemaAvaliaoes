"""Tratamento das imagens das questões: valida, reduz e grava no banco."""
import io
import re
import secrets

from sqlalchemy.orm import Session

from .models import Imagem

MARCADOR = re.compile(r"\[imagem:([0-9a-f]{16,40})\]")
LIMITE_ENVIO = 10 * 1024 * 1024    # 10 MB por arquivo enviado
LADO_MAXIMO = 1600                 # px — suficiente para leitura em tela cheia
ASSINATURAS = {b"\x89PNG": "image/png", b"\xff\xd8\xff": "image/jpeg", b"GIF8": "image/gif", b"RIFF": "image/webp"}


class ErroImagem(ValueError):
    pass


def _tipo_por_assinatura(dados: bytes) -> str | None:
    for ini, mime in ASSINATURAS.items():
        if dados.startswith(ini):
            return mime
    return None


def preparar(dados: bytes) -> tuple[bytes, str, int | None, int | None]:
    """Devolve (bytes, mime, largura, altura). Reduz imagens grandes e remove metadados (ex.: GPS de fotos)."""
    if not dados:
        raise ErroImagem("Arquivo vazio")
    if len(dados) > LIMITE_ENVIO:
        raise ErroImagem("Imagem muito grande (máximo 10 MB)")
    try:
        from PIL import Image, ImageOps
    except ImportError:  # sem Pillow: aceita apenas formatos conhecidos, sem reduzir
        mime = _tipo_por_assinatura(dados)
        if not mime:
            raise ErroImagem("Formato não suportado. Use PNG, JPG, GIF ou WEBP.")
        return dados, mime, None, None
    try:
        img = Image.open(io.BytesIO(dados))
        img.load()
    except Exception:
        raise ErroImagem("Arquivo não é uma imagem válida. Use PNG, JPG, GIF ou WEBP.")
    if img.format == "GIF" and getattr(img, "n_frames", 1) > 1 and len(dados) <= 3 * 1024 * 1024:
        return dados, "image/gif", img.width, img.height  # GIF animado: mantém
    formato = img.format
    img = ImageOps.exif_transpose(img)  # fotos de celular na orientação certa
    if max(img.size) > LADO_MAXIMO:
        img.thumbnail((LADO_MAXIMO, LADO_MAXIMO))
    transparente = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
    saida = io.BytesIO()
    if formato in ("PNG", "GIF") or transparente:
        # PNG preserva a nitidez de prints de código, gráficos e textos
        if img.mode not in ("RGB", "RGBA", "L", "LA", "P"):
            img = img.convert("RGBA")
        img.save(saida, "PNG", optimize=True)
        mime = "image/png"
    else:  # fotos (JPG, WEBP, BMP, HEIC convertido…)
        img.convert("RGB").save(saida, "JPEG", quality=85, optimize=True)
        mime = "image/jpeg"
    return saida.getvalue(), mime, img.width, img.height


def gravar(db: Session, dados: bytes, dono_id: int | None) -> Imagem:
    conteudo, mime, larg, alt = preparar(dados)
    im = Imagem(chave=secrets.token_hex(16), dono_id=dono_id, mime=mime, largura=larg, altura=alt, dados=conteudo)
    db.add(im)
    db.flush()
    return im


def marcador(im: Imagem) -> str:
    return f"[imagem:{im.chave}]"


def sem_imagens(texto: str, troca: str = "🖼") -> str:
    return MARCADOR.sub(troca, texto or "")
