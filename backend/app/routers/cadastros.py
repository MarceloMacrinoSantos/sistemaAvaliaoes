"""Login e cadastros: escolas, disciplinas, turmas, alunos, professores e vínculos.

Visibilidade (ver app/acesso.py): o administrador vê e cadastra tudo; o professor vê apenas as escolas e
disciplinas dos seus vínculos, as turmas que criou e os alunos matriculados nelas.
"""
import os

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..acesso import (aluno_visivel, disciplinas_proprias, eh_admin, escolas_permitidas, filtrar_turmas, ids_turmas,
                      pode_editar, turma_do_usuario, vinculos)
from ..auth import criar_token, exige_admin, exige_professor, hash_senha, usuario_atual, verificar_senha
from ..db import get_db
from ..importacao import EXTENSOES_TABELA, ErroImportacao, detectar_colunas, ler_tabela, normalizar_rm
from ..models import Avaliacao, Disciplina, Escola, Matricula, Meta, Tentativa, Turma, Usuario, Vinculo, agora

router = APIRouter(prefix="/api")


def _404(msg: str = "Registro não encontrado"):
    raise HTTPException(404, msg)


# ---------- autenticação ----------
class LoginIn(BaseModel):
    login: str
    senha: str


def _usuario_out(u: Usuario, db: Session) -> dict:
    out = {"id": u.id, "nome": u.nome, "login": u.login, "papel": u.papel, "turma": None, "escola": None}
    if u.papel == "aluno":
        turmas = [m.turma for m in u.matriculas]
        out["turma"] = ", ".join(t.nome for t in turmas) or None
        out["escola"] = ", ".join(sorted({t.escola.nome for t in turmas})) or None
    elif u.papel == "professor":
        vs = vinculos(db, u)
        out["vinculos"] = [{"escola": v.escola.nome, "disciplina": v.disciplina.nome} for v in vs]
        out["escola"] = ", ".join(sorted({v.escola.nome for v in vs})) or None
    return out


@router.post("/auth/login")
def login(dados: LoginIn, db: Session = Depends(get_db)):
    u = db.scalar(select(Usuario).where(func.lower(Usuario.login) == dados.login.strip().lower()))
    if not u or not u.ativo or not verificar_senha(dados.senha, u.senha_hash):
        raise HTTPException(401, "Usuário ou senha inválidos")
    # ajusta o custo do hash ao configurado neste servidor (BCRYPT_ROUNDS): quem veio de outro computador
    # passa a ter o login tão leve quanto o servidor permite, já a partir da próxima entrada
    custo = int(os.getenv("BCRYPT_ROUNDS", "10"))
    if u.senha_hash.startswith("$2") and u.senha_hash[4:6].isdigit() and int(u.senha_hash[4:6]) != custo:
        u.senha_hash = hash_senha(dados.senha)
        db.commit()
    return {"token": criar_token(u), "usuario": _usuario_out(u, db)}


@router.get("/auth/me")
def me(u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    return _usuario_out(u, db)


def _config(db: Session) -> dict:
    aberto = db.get(Meta, "cadastro_professor")
    codigo = db.get(Meta, "codigo_convite")
    return {"cadastro_aberto": (aberto.valor != "nao") if aberto else True,
            "codigo_convite": (codigo.valor or "") if codigo else ""}


@router.get("/auth/config")
def config_publica(db: Session = Depends(get_db)):
    c = _config(db)
    return {"cadastro_aberto": c["cadastro_aberto"], "exige_codigo": bool(c["codigo_convite"])}


class CadastroProfessorIn(BaseModel):
    nome: str = Field(min_length=3)
    login: str = Field(min_length=3, max_length=60, pattern=r"^[A-Za-z0-9._@-]+$")
    senha: str = Field(min_length=6)
    codigo: str | None = None


@router.post("/auth/cadastro")
def cadastro_professor(dados: CadastroProfessorIn, db: Session = Depends(get_db)):
    """O próprio professor cria a conta (área particular: só ele vê o que cadastrar)."""
    c = _config(db)
    if not c["cadastro_aberto"]:
        raise HTTPException(403, "O cadastro de professores está fechado. Peça ao administrador para criar sua conta.")
    if c["codigo_convite"] and (dados.codigo or "").strip() != c["codigo_convite"]:
        raise HTTPException(403, "Código de convite inválido. Peça o código ao administrador.")
    _login_livre(db, dados.login.strip())
    p = Usuario(nome=dados.nome.strip(), login=dados.login.strip(), senha_hash=hash_senha(dados.senha), papel="professor")
    db.add(p)
    db.commit()
    return {"token": criar_token(p), "usuario": _usuario_out(p, db)}


class ConfigIn(BaseModel):
    cadastro_aberto: bool
    codigo_convite: str | None = Field(default=None, max_length=60)


@router.get("/config")
def ver_config(db: Session = Depends(get_db), _=Depends(exige_admin)):
    return _config(db)


@router.put("/config")
def salvar_config(dados: ConfigIn, db: Session = Depends(get_db), _=Depends(exige_admin)):
    for chave, valor in (("cadastro_professor", "sim" if dados.cadastro_aberto else "nao"),
                         ("codigo_convite", (dados.codigo_convite or "").strip())):
        m = db.get(Meta, chave) or Meta(chave=chave)
        m.valor = valor
        db.add(m)
    db.commit()
    return _config(db)


class TrocaSenhaIn(BaseModel):
    senha_atual: str
    nova_senha: str = Field(min_length=4)


@router.post("/auth/trocar-senha")
def trocar_senha(dados: TrocaSenhaIn, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    if not verificar_senha(dados.senha_atual, u.senha_hash):
        raise HTTPException(400, "Senha atual incorreta")
    u.senha_hash = hash_senha(dados.nova_senha)
    db.commit()
    return {"ok": True}


# ---------- escolas (cadastro: só admin) ----------
class EscolaIn(BaseModel):
    nome: str = Field(min_length=1)


@router.get("/escolas")
def listar_escolas(db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    q = select(Escola).order_by(Escola.nome)
    permitidas = escolas_permitidas(db, u)
    if permitidas is not None:
        q = q.where(Escola.id.in_(permitidas or [-1]))
    return [_escola_out(e, u, db) for e in db.scalars(q)]


def _escola_out(e: Escola, u: Usuario, db: Session) -> dict:
    dono = db.get(Usuario, e.criado_por) if e.criado_por else None
    return {"id": e.id, "nome": e.nome, "editavel": pode_editar(u, e), "criado_por": dono.nome if dono else None}


def _escola_editavel(db: Session, u: Usuario, eid: int) -> Escola:
    e = db.get(Escola, eid)
    if not e or not pode_editar(u, e):
        _404("Escola não encontrada (só quem cadastrou pode alterar)")
    return e


@router.post("/escolas")
def criar_escola(dados: EscolaIn, db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    e = Escola(nome=dados.nome.strip(), criado_por=None if eh_admin(u) else u.id)
    db.add(e)
    db.commit()
    return _escola_out(e, u, db)


@router.put("/escolas/{eid}")
def editar_escola(eid: int, dados: EscolaIn, db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    e = _escola_editavel(db, u, eid)
    e.nome = dados.nome.strip()
    db.commit()
    return _escola_out(e, u, db)


@router.delete("/escolas/{eid}")
def excluir_escola(eid: int, db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    e = _escola_editavel(db, u, eid)
    if db.scalar(select(func.count()).select_from(Avaliacao).where(Avaliacao.escola_id == eid)):
        raise HTTPException(400, "Existem avaliações vinculadas a esta escola")
    db.delete(e)
    db.commit()
    return {"ok": True}


# ---------- disciplinas (cadastro: só admin; cada disciplina pertence a uma escola) ----------
class DisciplinaIn(BaseModel):
    nome: str = Field(min_length=1)
    escola_id: int | None = None


def _disc_out(d: Disciplina, escola_id: int | None = None, u: Usuario | None = None) -> dict:
    eid = escola_id if escola_id is not None else d.escola_id
    return {"id": d.id, "nome": d.nome, "escola_id": eid,
            "escola": (d.escola.nome if d.escola and eid == d.escola_id else None),
            "editavel": bool(u and pode_editar(u, d))}


@router.get("/disciplinas")
def listar_disciplinas(escola_id: int | None = None, db: Session = Depends(get_db),
                       u: Usuario = Depends(exige_professor)):
    if eh_admin(u):
        q = select(Disciplina).order_by(Disciplina.nome)
        if escola_id:
            q = q.where((Disciplina.escola_id == escola_id) | Disciplina.escola_id.is_(None))
        return [_disc_out(d, u=u) for d in db.scalars(q)]
    # professor: as disciplinas que ele cadastrou + uma linha por vínculo feito pelo administrador
    out, vistos = [], set()
    for d in disciplinas_proprias(db, u):
        if escola_id and d.escola_id != escola_id:
            continue
        out.append(_disc_out(d, u=u))
        vistos.add((d.id, d.escola_id))
    for v in vinculos(db, u):
        if (escola_id and v.escola_id != escola_id) or (v.disciplina_id, v.escola_id) in vistos:
            continue
        item = _disc_out(v.disciplina, v.escola_id, u)
        item["escola"] = v.escola.nome
        out.append(item)
    return sorted(out, key=lambda d: ((d["escola"] or ""), d["nome"]))


def _validar_escola_disciplina(db: Session, u: Usuario, escola_id: int | None) -> None:
    if not escola_id:
        if not eh_admin(u):
            raise HTTPException(400, "Escolha a escola da disciplina")
        return
    db.get(Escola, escola_id) or _404("Escola não encontrada")
    if not eh_admin(u) and escola_id not in (escolas_permitidas(db, u) or set()):
        raise HTTPException(403, "Escola não encontrada")


@router.post("/disciplinas")
def criar_disciplina(dados: DisciplinaIn, db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    _validar_escola_disciplina(db, u, dados.escola_id)
    d = Disciplina(nome=dados.nome.strip(), escola_id=dados.escola_id, criado_por=None if eh_admin(u) else u.id)
    db.add(d)
    db.commit()
    return _disc_out(d, u=u)


@router.put("/disciplinas/{did}")
def editar_disciplina(did: int, dados: DisciplinaIn, db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    d = db.get(Disciplina, did)
    if not d or not pode_editar(u, d):
        _404("Disciplina não encontrada (só quem cadastrou pode alterar)")
    _validar_escola_disciplina(db, u, dados.escola_id)
    d.nome, d.escola_id = dados.nome.strip(), dados.escola_id
    db.commit()
    return _disc_out(d, u=u)


@router.delete("/disciplinas/{did}")
def excluir_disciplina(did: int, db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    d = db.get(Disciplina, did)
    if not d or not pode_editar(u, d):
        _404("Disciplina não encontrada (só quem cadastrou pode alterar)")
    if db.scalar(select(func.count()).select_from(Avaliacao).where(Avaliacao.disciplina_id == did)):
        raise HTTPException(400, "Existem avaliações vinculadas a esta disciplina")
    db.delete(d)
    db.commit()
    return {"ok": True}


# ---------- turmas (cada turma tem um professor dono) ----------
class TurmaIn(BaseModel):
    nome: str = Field(min_length=1)
    escola_id: int
    ano_letivo: str | None = None
    professor_id: int | None = None  # só o admin escolhe; o professor é sempre o dono das turmas que cria


def _qtd_alunos(db: Session, tid: int) -> int:
    return db.scalar(select(func.count()).select_from(Matricula).where(Matricula.turma_id == tid))


def _turma_out(t: Turma, db: Session) -> dict:
    return {"id": t.id, "nome": t.nome, "ano_letivo": t.ano_letivo, "escola_id": t.escola_id,
            "escola": t.escola.nome, "qtd_alunos": _qtd_alunos(db, t.id),
            "professor_id": t.professor_id, "professor": t.professor.nome if t.professor else None}


def _nome_turma_livre(db: Session, dados: TurmaIn, dono: int | None, exceto: int | None = None) -> None:
    q = select(Turma).where(func.lower(Turma.nome) == dados.nome.strip().lower(), Turma.escola_id == dados.escola_id,
                            Turma.professor_id.is_(None) if dono is None else Turma.professor_id == dono)
    t = db.scalar(q)
    if t and t.id != exceto:
        raise HTTPException(400, f"Você já tem a turma \"{t.nome}\" nesta escola. Use a existente ou escolha outro nome.")


def _validar_turma(db: Session, u: Usuario, dados: TurmaIn) -> int | None:
    db.get(Escola, dados.escola_id) or _404("Escola não encontrada")
    if eh_admin(u):
        if dados.professor_id:
            p = db.get(Usuario, dados.professor_id)
            if not p or p.papel not in ("professor", "admin"):
                raise HTTPException(400, "Professor inválido")
        return dados.professor_id
    if dados.escola_id not in (escolas_permitidas(db, u) or set()):
        raise HTTPException(403, "Escola não encontrada entre as suas")
    return u.id


@router.get("/turmas")
def listar_turmas(escola_id: int | None = None, db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    q = filtrar_turmas(select(Turma).order_by(Turma.nome), u)
    if escola_id:
        q = q.where(Turma.escola_id == escola_id)
    return [_turma_out(t, db) for t in db.scalars(q)]


@router.post("/turmas")
def criar_turma(dados: TurmaIn, db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    dono = _validar_turma(db, u, dados)
    _nome_turma_livre(db, dados, dono)
    t = Turma(nome=dados.nome.strip(), escola_id=dados.escola_id, ano_letivo=dados.ano_letivo, professor_id=dono)
    db.add(t)
    db.commit()
    return _turma_out(t, db)


@router.put("/turmas/{tid}")
def editar_turma(tid: int, dados: TurmaIn, db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    t = turma_do_usuario(db, u, tid)
    dono = _validar_turma(db, u, dados)
    _nome_turma_livre(db, dados, dono if eh_admin(u) else t.professor_id, exceto=t.id)
    t.nome, t.escola_id, t.ano_letivo = dados.nome.strip(), dados.escola_id, dados.ano_letivo
    if eh_admin(u):
        t.professor_id = dono
    db.commit()
    return _turma_out(t, db)


@router.delete("/turmas/{tid}")
def excluir_turma(tid: int, db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    t = turma_do_usuario(db, u, tid)
    if db.scalar(select(func.count()).select_from(Avaliacao).where(Avaliacao.turma_id == tid)):
        raise HTTPException(400, "Existem avaliações vinculadas a esta turma")
    alunos = [m.aluno for m in t.matriculas]
    db.delete(t)
    db.flush()
    _apagar_orfaos(db, alunos)
    db.commit()
    return {"ok": True}


# ---------- alunos (matriculados nas turmas) ----------
class AlunoIn(BaseModel):
    nome: str = Field(min_length=1)
    login: str = Field(min_length=1, description="RM / matrícula / usuário de acesso")
    senha: str | None = None
    turma_id: int
    turma_atual_id: int | None = None  # na edição: turma de onde o aluno está sendo movido


def _aluno_out(u: Usuario, turma: Turma | None = None) -> dict:
    return {"id": u.id, "nome": u.nome, "login": u.login, "turma_id": turma.id if turma else None,
            "turma": turma.nome if turma else None, "ativo": u.ativo}


def _login_livre(db: Session, login: str, exceto: int | None = None) -> None:
    u = db.scalar(select(Usuario).where(func.lower(Usuario.login) == login.lower()))
    if u and u.id != exceto:
        raise HTTPException(400, f"O login '{login}' já está em uso")


def _matricular(db: Session, aluno: Usuario, turma: Turma, lote: str | None = None) -> bool:
    if db.scalar(select(Matricula.id).where(Matricula.turma_id == turma.id, Matricula.aluno_id == aluno.id)):
        return False
    db.add(Matricula(turma_id=turma.id, aluno_id=aluno.id, lote_importacao=lote))
    return True


def _desmatricular(db: Session, matriculas: list[Matricula]) -> int:
    """Tira os alunos da turma, apaga as provas deles nas avaliações dessa turma e remove quem ficou sem turma."""
    apagadas = 0
    alunos = []
    for m in matriculas:
        av_ids = list(db.scalars(select(Avaliacao.id).where(Avaliacao.turma_id == m.turma_id)))
        if av_ids:
            ts = db.scalars(select(Tentativa).where(Tentativa.aluno_id == m.aluno_id,
                                                    Tentativa.avaliacao_id.in_(av_ids))).all()
            for t in ts:
                db.delete(t)
            apagadas += len(ts)
        alunos.append(m.aluno)
        db.delete(m)
    db.flush()
    _apagar_orfaos(db, alunos)
    return apagadas


def _apagar_orfaos(db: Session, alunos: list[Usuario]) -> None:
    for a in alunos:
        if a.papel == "aluno" and not db.scalar(select(Matricula.id).where(Matricula.aluno_id == a.id)):
            db.delete(a)


@router.get("/alunos")
def listar_alunos(turma_id: int | None = None, db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    q = (select(Usuario, Turma).join(Matricula, Matricula.aluno_id == Usuario.id).join(Turma, Turma.id == Matricula.turma_id)
         .where(Usuario.papel == "aluno").order_by(Usuario.nome))
    if turma_id:
        turma_do_usuario(db, u, turma_id)
        q = q.where(Turma.id == turma_id)
    else:
        q = filtrar_turmas(q, u)
    return [_aluno_out(a, t) for a, t in db.execute(q)]


@router.post("/alunos")
def criar_aluno(dados: AlunoIn, db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    turma = turma_do_usuario(db, u, dados.turma_id)
    login_ = normalizar_rm(dados.login)
    existente = db.scalar(select(Usuario).where(func.lower(Usuario.login) == login_.lower()))
    if existente:
        if existente.papel != "aluno":
            raise HTTPException(400, f"O login '{login_}' pertence a um professor")
        if not _matricular(db, existente, turma):
            raise HTTPException(400, f"O aluno {existente.nome} ({login_}) já está nesta turma")
        db.commit()
        out = _aluno_out(existente, turma)
        out["ja_existia"] = True  # RM já cadastrada (em outra turma): apenas matriculado nesta
        return out
    a = Usuario(nome=dados.nome.strip(), login=login_, senha_hash=hash_senha(dados.senha or login_), papel="aluno")
    db.add(a)
    db.flush()
    _matricular(db, a, turma)
    db.commit()
    return _aluno_out(a, turma)


@router.put("/alunos/{uid}")
def editar_aluno(uid: int, dados: AlunoIn, db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    a = aluno_visivel(db, u, uid)
    nova = turma_do_usuario(db, u, dados.turma_id)
    login_ = normalizar_rm(dados.login)
    _login_livre(db, login_, exceto=uid)
    a.nome, a.login = dados.nome.strip(), login_
    if dados.senha:
        a.senha_hash = hash_senha(dados.senha)
    if dados.turma_atual_id and dados.turma_atual_id != nova.id:  # mover entre turmas do mesmo professor
        atual = turma_do_usuario(db, u, dados.turma_atual_id)
        m = db.scalar(select(Matricula).where(Matricula.turma_id == atual.id, Matricula.aluno_id == a.id))
        if m and not db.scalar(select(Matricula.id).where(Matricula.turma_id == nova.id, Matricula.aluno_id == a.id)):
            m.turma_id = nova.id
    else:
        _matricular(db, a, nova)
    db.commit()
    return _aluno_out(a, nova)


@router.delete("/alunos/{uid}")
def excluir_aluno(uid: int, turma_id: int | None = None, db: Session = Depends(get_db),
                  u: Usuario = Depends(exige_professor)):
    """Tira o aluno da turma informada (ou de todas as turmas do professor). Sem nenhuma turma, o cadastro é apagado."""
    a = aluno_visivel(db, u, uid)
    q = select(Matricula).where(Matricula.aluno_id == a.id)
    if turma_id:
        turma_do_usuario(db, u, turma_id)
        q = q.where(Matricula.turma_id == turma_id)
    elif not eh_admin(u):
        q = q.where(Matricula.turma_id.in_(ids_turmas(db, u) or [-1]))
    _desmatricular(db, list(db.scalars(q)))
    db.commit()
    return {"ok": True}


MAX_ARQUIVO = 10 * 1024 * 1024


async def ler_upload(arquivo: UploadFile | None, texto: str | None) -> tuple[str, bytes]:
    if arquivo is not None and arquivo.filename:
        dados = await arquivo.read()
        if len(dados) > MAX_ARQUIVO:
            raise HTTPException(400, "Arquivo muito grande (máx. 10 MB)")
        return arquivo.filename, dados
    if texto and texto.strip():
        return "colado.txt", texto.encode("utf-8")
    raise HTTPException(400, "Envie um arquivo ou cole o texto")


@router.post("/alunos/ler-arquivo")
async def ler_arquivo_alunos(arquivo: UploadFile | None = File(None), texto: str | None = Form(None),
                             _=Depends(exige_professor)):
    """Lê planilha/CSV/JSON/texto e sugere quais colunas são RM, nome e senha (prévia, não grava nada)."""
    nome, dados = await ler_upload(arquivo, texto)
    if nome != "colado.txt" and not nome.lower().endswith(EXTENSOES_TABELA):
        raise HTTPException(400, "Formato não suportado. Use .xlsx, .xls, .csv, .txt ou .json")
    try:
        linhas = ler_tabela(nome, dados)
    except ErroImportacao as e:
        raise HTTPException(400, str(e))
    if not linhas:
        raise HTTPException(400, "Nenhum dado encontrado no arquivo")
    linhas = linhas[:5000]
    largura = max(len(l) for l in linhas)
    linhas = [l + [""] * (largura - len(l)) for l in linhas]
    return {"arquivo": nome, "linhas": linhas, "largura": largura, "sugestao": detectar_colunas(linhas)}


class AlunoLoteItem(BaseModel):
    rm: str
    nome: str
    senha: str | None = None


class ImportarListaIn(BaseModel):
    turma_id: int
    alunos: list[AlunoLoteItem] = Field(max_length=5000)
    senha_padrao: str | None = None      # vazio = a própria RM
    atualizar_existentes: bool = False   # RM já cadastrada: atualiza nome/senha
    origem: str | None = None


@router.post("/alunos/importar-lista")
def importar_lista(dados: ImportarListaIn, db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    turma = turma_do_usuario(db, u, dados.turma_id)
    lote = f"{agora().strftime('%Y-%m-%d %H:%M:%S')} · {(dados.origem or 'importação')[:60]}"
    existentes = {x.login.lower(): x for x in db.scalars(select(Usuario))}
    criados = atualizados = matriculados = 0
    erros, vistos = [], set()
    for n, item in enumerate(dados.alunos, start=1):
        rm, nome = normalizar_rm(item.rm), " ".join((item.nome or "").split())
        if not rm or not nome:
            erros.append(f"Linha {n}: RM ou nome vazio")
            continue
        if rm.lower() in vistos:
            erros.append(f"Linha {n}: RM {rm} repetida no arquivo")
            continue
        vistos.add(rm.lower())
        senha = (item.senha or "").strip() or (dados.senha_padrao or "").strip() or rm
        a = existentes.get(rm.lower())
        if a:
            if a.papel != "aluno":
                erros.append(f"Linha {n}: o login {rm} pertence a um professor")
                continue
            novo_na_turma = _matricular(db, a, turma, lote)
            if dados.atualizar_existentes:
                a.nome, a.ativo = nome, True
                if (item.senha or "").strip():
                    a.senha_hash = hash_senha(senha)
                atualizados += 1
            elif novo_na_turma:
                matriculados += 1
            else:
                erros.append(f"Linha {n}: RM {rm} já está nesta turma — ignorada")
            continue
        a = Usuario(nome=nome, login=rm, senha_hash=hash_senha(senha), papel="aluno")
        db.add(a)
        db.flush()
        existentes[rm.lower()] = a
        _matricular(db, a, turma, lote)
        criados += 1
    db.commit()
    return {"criados": criados, "atualizados": atualizados, "matriculados": matriculados, "erros": erros,
            "lote": lote if (criados or matriculados) else None}


@router.get("/alunos/lotes")
def listar_lotes(turma_id: int, db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    """Importações feitas nesta turma (para desfazer uma importação errada)."""
    turma_do_usuario(db, u, turma_id)
    q = (select(Matricula.lote_importacao, func.count()).where(Matricula.turma_id == turma_id,
         Matricula.lote_importacao.is_not(None)).group_by(Matricula.lote_importacao)
         .order_by(Matricula.lote_importacao.desc()))
    return [{"lote": l, "qtd": n} for l, n in db.execute(q)]


class ExcluirLoteIn(BaseModel):
    turma_id: int
    modo: str = Field(pattern="^(todos|selecionados|lote)$")
    ids: list[int] = []
    lote: str | None = None
    confirmacao: str | None = None  # para "todos": o nome da turma digitado


@router.post("/alunos/excluir-lote")
def excluir_lote(dados: ExcluirLoteIn, db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    turma = turma_do_usuario(db, u, dados.turma_id)
    q = select(Matricula).where(Matricula.turma_id == turma.id)
    if dados.modo == "todos":
        if (dados.confirmacao or "").strip().lower() != turma.nome.strip().lower():
            raise HTTPException(400, f"Para excluir todos, digite o nome da turma exatamente: {turma.nome}")
    elif dados.modo == "selecionados":
        if not dados.ids:
            raise HTTPException(400, "Nenhum aluno selecionado")
        q = q.where(Matricula.aluno_id.in_(dados.ids))
    else:
        if not dados.lote:
            raise HTTPException(400, "Informe a importação a desfazer")
        q = q.where(Matricula.lote_importacao == dados.lote)
    ms = list(db.scalars(q))
    apagadas = _desmatricular(db, ms)
    db.commit()
    return {"excluidos": len(ms), "tentativas_apagadas": apagadas}


# ---------- professores e vínculos (somente admin) ----------
class ProfessorIn(BaseModel):
    nome: str = Field(min_length=1)
    login: str = Field(min_length=1)
    senha: str | None = None
    papel: str = "professor"


class VinculoIn(BaseModel):
    escola_id: int
    disciplina_id: int


def _prof_out(p: Usuario, db: Session) -> dict:
    return {"id": p.id, "nome": p.nome, "login": p.login, "papel": p.papel,
            "vinculos": [{"id": v.id, "escola_id": v.escola_id, "escola": v.escola.nome,
                          "disciplina_id": v.disciplina_id, "disciplina": v.disciplina.nome}
                         for v in sorted(vinculos(db, p), key=lambda v: (v.escola.nome, v.disciplina.nome))],
            "qtd_turmas": db.scalar(select(func.count()).select_from(Turma).where(Turma.professor_id == p.id))}


@router.get("/professores")
def listar_professores(db: Session = Depends(get_db), _=Depends(exige_admin)):
    q = select(Usuario).where(Usuario.papel.in_(["professor", "admin"]), Usuario.ativo.is_(True)).order_by(Usuario.nome)
    return [_prof_out(p, db) for p in db.scalars(q)]


@router.post("/professores")
def criar_professor(dados: ProfessorIn, db: Session = Depends(get_db), _=Depends(exige_admin)):
    if dados.papel not in ("professor", "admin"):
        raise HTTPException(400, "Papel inválido")
    if not dados.senha:
        raise HTTPException(400, "Informe uma senha")
    _login_livre(db, dados.login.strip())
    p = Usuario(nome=dados.nome.strip(), login=dados.login.strip(), senha_hash=hash_senha(dados.senha),
                papel=dados.papel)
    db.add(p)
    db.commit()
    return _prof_out(p, db)


class ProfessorEdicaoIn(BaseModel):
    nome: str | None = None
    papel: str | None = Field(default=None, pattern="^(professor|admin)$")
    senha: str | None = Field(default=None, min_length=4)


@router.put("/professores/{uid}")
def editar_professor(uid: int, dados: ProfessorEdicaoIn, db: Session = Depends(get_db),
                     atual: Usuario = Depends(exige_admin)):
    """Troca o perfil (professor/administrador), o nome ou a senha de um usuário da equipe."""
    p = db.get(Usuario, uid)
    if not p or p.papel == "aluno":
        _404()
    if dados.papel and dados.papel != p.papel:
        if p.id == atual.id:
            raise HTTPException(400, "Você não pode mudar o seu próprio perfil")
        p.papel = dados.papel
    if dados.nome:
        p.nome = dados.nome.strip()
    if dados.senha:
        p.senha_hash = hash_senha(dados.senha)
    db.commit()
    return _prof_out(p, db)


@router.post("/professores/{uid}/vinculos")
def adicionar_vinculo(uid: int, dados: VinculoIn, db: Session = Depends(get_db), _=Depends(exige_admin)):
    p = db.get(Usuario, uid)
    if not p or p.papel not in ("professor", "admin"):
        _404("Professor não encontrado")
    db.get(Escola, dados.escola_id) or _404("Escola não encontrada")
    d = db.get(Disciplina, dados.disciplina_id) or _404("Disciplina não encontrada")
    if d.escola_id and d.escola_id != dados.escola_id:
        raise HTTPException(400, f"A disciplina {d.nome} pertence a outra escola")
    if not db.scalar(select(Vinculo.id).where(Vinculo.professor_id == uid, Vinculo.escola_id == dados.escola_id,
                                             Vinculo.disciplina_id == dados.disciplina_id)):
        db.add(Vinculo(professor_id=uid, escola_id=dados.escola_id, disciplina_id=dados.disciplina_id))
        db.commit()
    return _prof_out(p, db)


@router.delete("/vinculos/{vid}")
def remover_vinculo(vid: int, db: Session = Depends(get_db), _=Depends(exige_admin)):
    v = db.get(Vinculo, vid) or _404()
    db.delete(v)
    db.commit()
    return {"ok": True}


@router.delete("/professores/{uid}")
def excluir_professor(uid: int, db: Session = Depends(get_db), atual: Usuario = Depends(exige_admin)):
    p = db.get(Usuario, uid)
    if not p or p.papel == "aluno":
        _404()
    if p.id == atual.id:
        raise HTTPException(400, "Você não pode excluir a si mesmo")
    p.ativo = False  # preserva autoria das avaliações e turmas
    p.login = f"{p.login}#removido{p.id}"
    db.commit()
    return {"ok": True}
