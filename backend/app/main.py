import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from .auth import hash_senha
from .db import Base, SessionLocal, engine, migrar_colunas
from .models import Usuario
from .routers import aluno, analises, avaliacoes, cadastros, imagens

def _inicializar():
    Base.metadata.create_all(engine)
    migrar_colunas()
    with SessionLocal() as db:
        from .migracao import migrar_dados, migrar_donos
        migrar_dados(db)
        migrar_donos(db)
        if not db.scalar(select(Usuario).where(Usuario.papel == "admin")):
            db.add(Usuario(nome="Administrador", login=os.getenv("ADMIN_LOGIN", "admin"),
                           senha_hash=hash_senha(os.getenv("ADMIN_SENHA", "admin123")), papel="admin"))
            db.commit()
    if os.getenv("SEED_DEMO") == "1":
        from .seed import popular_demo
        popular_demo()



@asynccontextmanager
async def lifespan(_app):
    _inicializar()
    from .fila_ia import iniciar
    iniciar()  # correção por IA em segundo plano (só trabalha se houver chave configurada)
    yield


app = FastAPI(title="Sistema de Avaliações", version="1.0.0", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)
origens = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(CORSMiddleware, allow_origins=origens, allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(RequestValidationError)
async def _erro_validacao(_: Request, exc: RequestValidationError):
    """Devolve mensagens de validação legíveis em português."""
    msgs = []
    for e in exc.errors():
        msg = str(e.get("msg", "")).removeprefix("Value error, ")
        campo = ".".join(str(x) for x in e.get("loc", [])[1:])
        msgs.append(msg if e.get("type") == "value_error" else f"{campo}: {msg}")
    return JSONResponse(status_code=422, content={"detail": "; ".join(msgs)})


app.include_router(cadastros.router)
app.include_router(avaliacoes.router)
app.include_router(aluno.router)
app.include_router(analises.router)
app.include_router(imagens.router)


MODELOS = Path(__file__).resolve().parent / "modelos"


@app.get("/api/modelos/{nome}")
def baixar_modelo(nome: str):
    arq = MODELOS / Path(nome).name
    if not arq.is_file():
        return JSONResponse(status_code=404, content={"detail": "Modelo não encontrado"})
    return FileResponse(arq, filename=arq.name)


@app.get("/api/acesso")
def acesso(request: Request):
    """Endereços para o QR code de acesso dos alunos."""
    from .rede import enderecos
    return {"enderecos": enderecos(request), "caminho": "/aluno"}


@app.get("/api/saude")
def saude():
    return {"ok": True, "versao": 20}


# ---------- frontend (Vue) compilado, servido pelo próprio backend ----------
DIST = Path(os.getenv("FRONTEND_DIST", Path(__file__).resolve().parents[2] / "frontend" / "dist"))
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{caminho:path}", include_in_schema=False)
    def spa(caminho: str):
        arquivo = DIST / caminho
        if caminho and arquivo.is_file() and DIST in arquivo.resolve().parents:
            return FileResponse(arquivo)
        # index.html nunca fica em cache: depois de atualizar o sistema o navegador carrega as telas novas
        return FileResponse(DIST / "index.html", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
