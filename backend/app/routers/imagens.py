"""Envio e exibição das imagens das questões."""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import exige_professor
from ..db import get_db
from ..imagens import ErroImagem, LIMITE_ENVIO, gravar, marcador
from ..models import Imagem, Usuario

router = APIRouter(prefix="/api")


@router.post("/imagens")
async def enviar_imagem(arquivo: UploadFile = File(...), db: Session = Depends(get_db),
                        u: Usuario = Depends(exige_professor)):
    dados = await arquivo.read(LIMITE_ENVIO + 1)
    try:
        im = gravar(db, dados, u.id)
    except ErroImagem as e:
        raise HTTPException(400, str(e))
    db.commit()
    return {"chave": im.chave, "marcador": marcador(im), "largura": im.largura, "altura": im.altura,
            "tamanho": len(im.dados)}


@router.get("/imagens/{chave}")
def ver_imagem(chave: str, db: Session = Depends(get_db)):
    # sem login: a tag <img> do navegador não envia o token. A chave é aleatória (128 bits) e
    # só aparece para quem já vê a questão.
    im = db.scalar(select(Imagem).where(Imagem.chave == chave))
    if not im:
        raise HTTPException(404, "Imagem não encontrada")
    return Response(im.dados, media_type=im.mime, headers={
        "Cache-Control": "public, max-age=31536000, immutable", "X-Content-Type-Options": "nosniff"})
