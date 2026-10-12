"""Área do professor: avaliações, questões, gabaritos, resultados e revisão."""
import csv
import io
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..acesso import avaliacao_do_usuario, eh_admin, par_permitido, turma_do_usuario
from ..auth import exige_professor
from ..importacao import EXTENSOES_PROVA, MARCA_IMG_ARQUIVO, ErroImportacao, extrair_linhas, interpretar_prova
from .cadastros import ler_upload
from ..correcao import corrigir_tentativa, recalcular_nota
from ..db import get_db
from ..imagens import ErroImagem, MARCADOR, gravar, marcador, sem_imagens
from ..models import (Alternativa, Avaliacao, Matricula, Questao, Resposta, Tentativa, Turma, Usuario, agora)
from ..servicos import (carregar_tentativa, feedback_tentativa, finalizar_expiradas, iso, monitoramento_out,
                        para_utc, redistribuir_pontos, resultado_visivel)

router = APIRouter(prefix="/api", dependencies=[Depends(exige_professor)])


class AvaliacaoIn(BaseModel):
    titulo: str = Field(min_length=1)
    descricao: str | None = None
    tipo: Literal["prova", "simulado", "teste"] = "prova"
    escola_id: int
    turma_id: int
    disciplina_id: int
    inicio: datetime
    fim: datetime
    duracao_min: int | None = Field(default=None, ge=1)
    embaralhar_questoes: bool = True
    embaralhar_alternativas: bool = True
    liberar_resultado: Literal["apos_fim", "apos_envio", "manual"] = "apos_fim"
    publicada: bool = False
    nota_total: float = Field(default=10.0, gt=0, le=1000)
    peso_objetiva: float = Field(default=1.0, gt=0, le=100)
    peso_dissertativa: float = Field(default=2.0, gt=0, le=100)
    monitorar: bool = True

    @model_validator(mode="after")
    def _datas(self):
        if para_utc(self.fim) <= para_utc(self.inicio):
            raise ValueError("A data de término deve ser posterior à de início")
        return self


def _status(av: Avaliacao) -> str:
    agora_ = agora()
    if not av.publicada:
        return "rascunho"
    if agora_ < av.inicio:
        return "agendada"
    if agora_ < av.fim:
        return "em_andamento"
    return "encerrada"


def _av_out(av: Avaliacao, db: Session, completo: bool = False) -> dict:
    out = {
        "id": av.id, "titulo": av.titulo, "descricao": av.descricao, "tipo": av.tipo,
        "escola_id": av.escola_id, "escola": av.escola.nome,
        "turma_id": av.turma_id, "turma": av.turma.nome,
        "disciplina_id": av.disciplina_id, "disciplina": av.disciplina.nome,
        "professor_id": av.professor_id,
        "professor": (lambda p: p.nome if p else None)(db.get(Usuario, av.professor_id) if av.professor_id else None),
        "inicio": iso(av.inicio), "fim": iso(av.fim), "duracao_min": av.duracao_min,
        "embaralhar_questoes": av.embaralhar_questoes, "embaralhar_alternativas": av.embaralhar_alternativas,
        "liberar_resultado": av.liberar_resultado, "resultado_liberado": av.resultado_liberado,
        "publicada": av.publicada, "status": _status(av),
        "nota_total": av.nota_total, "peso_objetiva": av.peso_objetiva, "peso_dissertativa": av.peso_dissertativa,
        "monitorar": av.monitorar,
        "qtd_questoes": len(av.questoes), "pontuacao_total": round(sum(q.pontos for q in av.questoes), 2),
        "qtd_tentativas": db.scalar(select(func.count()).select_from(Tentativa)
                                    .where(Tentativa.avaliacao_id == av.id)),
    }
    if completo:
        out["questoes"] = [_questao_out(q) for q in av.questoes]
    return out


def _questao_out(q: Questao) -> dict:
    return {"id": q.id, "tipo": q.tipo, "enunciado": q.enunciado, "peso": q.peso, "pontos": q.pontos, "ordem": q.ordem,
            "explicacao": q.explicacao, "gabarito_texto": q.gabarito_texto,
            "palavras_chave": q.palavras_chave or [],
            "alternativas": [{"id": a.id, "texto": a.texto, "correta": a.correta} for a in q.alternativas]}


def _get_av(db: Session, aid: int, u: Usuario) -> Avaliacao:
    av = db.scalar(select(Avaliacao).where(Avaliacao.id == aid)
                   .options(selectinload(Avaliacao.questoes).selectinload(Questao.alternativas)))
    return avaliacao_do_usuario(u, av)


def _validar_destino(db: Session, u: Usuario, escola_id: int, turma_id: int, disciplina_id: int) -> Turma:
    """Turma do professor, na escola escolhida, e disciplina de um vínculo dele nessa escola."""
    turma = turma_do_usuario(db, u, turma_id)
    if turma.escola_id != escola_id:
        raise HTTPException(400, "A turma não pertence à escola selecionada")
    if not par_permitido(db, u, escola_id, disciplina_id):
        raise HTTPException(403, "Esta disciplina não é sua ou não pertence a esta escola")
    return turma


@router.get("/avaliacoes")
def listar(escola_id: int | None = None, turma_id: int | None = None, disciplina_id: int | None = None,
           db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    q = select(Avaliacao).options(selectinload(Avaliacao.questoes)).order_by(Avaliacao.inicio.desc())
    if not eh_admin(u):
        q = q.where(Avaliacao.professor_id == u.id)
    if escola_id:
        q = q.where(Avaliacao.escola_id == escola_id)
    if turma_id:
        q = q.where(Avaliacao.turma_id == turma_id)
    if disciplina_id:
        q = q.where(Avaliacao.disciplina_id == disciplina_id)
    return [_av_out(av, db) for av in db.scalars(q)]


@router.post("/avaliacoes")
def criar(dados: AvaliacaoIn, db: Session = Depends(get_db), prof: Usuario = Depends(exige_professor)):
    _validar_destino(db, prof, dados.escola_id, dados.turma_id, dados.disciplina_id)
    campos = dados.model_dump()
    campos["inicio"], campos["fim"] = para_utc(dados.inicio), para_utc(dados.fim)
    av = Avaliacao(**campos, professor_id=prof.id)
    db.add(av)
    db.commit()
    return _av_out(_get_av(db, av.id, prof), db, completo=True)


@router.get("/avaliacoes/{aid}")
def detalhe(aid: int, db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    return _av_out(_get_av(db, aid, u), db, completo=True)


@router.put("/avaliacoes/{aid}")
def editar(aid: int, dados: AvaliacaoIn, db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    av = _get_av(db, aid, u)
    _validar_destino(db, u, dados.escola_id, dados.turma_id, dados.disciplina_id)
    if dados.nota_total != av.nota_total and _tem_tentativas(db, av):
        raise HTTPException(400, "Não é possível mudar a nota total depois que alunos iniciaram a avaliação")
    for k, v in dados.model_dump().items():
        setattr(av, k, v)
    av.inicio, av.fim = para_utc(dados.inicio), para_utc(dados.fim)
    if not _tem_tentativas(db, av):
        redistribuir_pontos(av)
    db.commit()
    return _av_out(av, db, completo=True)


@router.delete("/avaliacoes/{aid}")
def excluir(aid: int, db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    db.delete(_get_av(db, aid, u))
    db.commit()
    return {"ok": True}


@router.post("/avaliacoes/{aid}/duplicar")
def duplicar(aid: int, turma_id: int | None = None, db: Session = Depends(get_db),
             prof: Usuario = Depends(exige_professor)):
    """Copia a avaliação (com questões e gabarito) — útil para aplicar a mesma prova em outra turma."""
    av = _get_av(db, aid, prof)
    turma = turma_do_usuario(db, prof, turma_id) if turma_id else av.turma
    nova = Avaliacao(titulo=f"{av.titulo} (cópia)", descricao=av.descricao, tipo=av.tipo,
                     escola_id=turma.escola_id, turma_id=turma.id, disciplina_id=av.disciplina_id,
                     professor_id=prof.id, inicio=av.inicio, fim=av.fim, duracao_min=av.duracao_min,
                     embaralhar_questoes=av.embaralhar_questoes, embaralhar_alternativas=av.embaralhar_alternativas,
                     liberar_resultado=av.liberar_resultado, publicada=False, nota_total=av.nota_total,
                     peso_objetiva=av.peso_objetiva, peso_dissertativa=av.peso_dissertativa, monitorar=av.monitorar)
    for q in av.questoes:
        nq = Questao(tipo=q.tipo, enunciado=q.enunciado, pontos=q.pontos, peso=q.peso, ordem=q.ordem, explicacao=q.explicacao,
                     gabarito_texto=q.gabarito_texto, palavras_chave=list(q.palavras_chave or []))
        nq.alternativas = [Alternativa(texto=a.texto, correta=a.correta, ordem=a.ordem) for a in q.alternativas]
        nova.questoes.append(nq)
    db.add(nova)
    db.commit()
    return _av_out(_get_av(db, nova.id, prof), db, completo=True)


# ---------- questões ----------
class AlternativaIn(BaseModel):
    texto: str = Field(min_length=1)
    correta: bool = False


class QuestaoIn(BaseModel):
    tipo: Literal["objetiva", "dissertativa"]
    enunciado: str = Field(min_length=1)
    peso: float | None = Field(default=None, gt=0, le=100)  # vazio = peso padrão do tipo na avaliação
    explicacao: str | None = None
    gabarito_texto: str | None = None
    palavras_chave: list[str] = []
    alternativas: list[AlternativaIn] = []

    @model_validator(mode="after")
    def _valida(self):
        if self.tipo == "objetiva":
            if len(self.alternativas) < 2:
                raise ValueError("Questões objetivas precisam de pelo menos 2 alternativas")
            if sum(a.correta for a in self.alternativas) != 1:
                raise ValueError("Marque exatamente uma alternativa correta (gabarito)")
        return self


def _tem_tentativas(db: Session, av: Avaliacao) -> bool:
    return bool(db.scalar(select(func.count()).select_from(Tentativa).where(Tentativa.avaliacao_id == av.id)))


def _bloqueia_se_iniciada(db: Session, av: Avaliacao):
    if _tem_tentativas(db, av):
        raise HTTPException(400, "Não é possível alterar questões depois que alunos iniciaram a avaliação. "
                                 "Use 'Duplicar' para criar uma nova versão.")


def _aplicar_questao(q: Questao, dados: QuestaoIn, av: Avaliacao):
    q.tipo, q.enunciado = dados.tipo, dados.enunciado
    q.peso = dados.peso or (av.peso_dissertativa if dados.tipo == "dissertativa" else av.peso_objetiva)
    q.explicacao = dados.explicacao
    q.gabarito_texto = dados.gabarito_texto if dados.tipo == "dissertativa" else None
    q.palavras_chave = [p.strip() for p in dados.palavras_chave if p.strip()] if dados.tipo == "dissertativa" else []
    q.alternativas.clear()
    if dados.tipo == "objetiva":
        q.alternativas.extend(Alternativa(texto=a.texto, correta=a.correta, ordem=i)
                              for i, a in enumerate(dados.alternativas))


@router.post("/avaliacoes/{aid}/questoes")
def criar_questao(aid: int, dados: QuestaoIn, db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    av = _get_av(db, aid, u)
    _bloqueia_se_iniciada(db, av)
    q = Questao(ordem=(max((x.ordem for x in av.questoes), default=0) + 1))
    _aplicar_questao(q, dados, av)
    av.questoes.append(q)
    redistribuir_pontos(av)
    db.commit()
    return _questao_out(q)


@router.put("/questoes/{qid}")
def editar_questao(qid: int, dados: QuestaoIn, db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    q = db.get(Questao, qid) or _404()
    av = avaliacao_do_usuario(u, q.avaliacao)
    _bloqueia_se_iniciada(db, av)
    _aplicar_questao(q, dados, av)
    redistribuir_pontos(av)
    db.commit()
    return _questao_out(q)


@router.delete("/questoes/{qid}")
def excluir_questao(qid: int, db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    q = db.get(Questao, qid) or _404()
    av = avaliacao_do_usuario(u, q.avaliacao)
    _bloqueia_se_iniciada(db, av)
    av.questoes.remove(q)
    db.delete(q)
    redistribuir_pontos(av)
    db.commit()
    return {"ok": True}


class QuestoesLoteIn(BaseModel):
    questoes: list[QuestaoIn] = Field(min_length=1, max_length=300)
    substituir: bool = False  # apaga as questões atuais antes de inserir


@router.post("/avaliacoes/importar/ler")
async def ler_prova(arquivo: UploadFile | None = File(None), texto: str | None = Form(None),
                    db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    """Lê um .docx, .pdf ou texto colado e devolve as questões encontradas (prévia).

    As figuras do .docx que estão dentro das questões são gravadas e viram marcadores [imagem:CHAVE].
    """
    nome, dados = await ler_upload(arquivo, texto)
    if nome != "colado.txt" and not nome.lower().endswith(EXTENSOES_PROVA + (".doc",)):
        raise HTTPException(400, "Formato não suportado. Use .docx, .pdf ou .txt (ou cole o texto)")
    figuras: list[bytes] = []
    try:
        res = interpretar_prova(extrair_linhas(nome, dados, figuras))
    except ErroImportacao as e:
        raise HTTPException(400, str(e))
    if figuras:
        gravadas: dict[int, str] = {}
        problemas = 0

        def trocar(m):
            nonlocal problemas
            i = int(m.group(1))
            if i not in gravadas:
                try:
                    gravadas[i] = marcador(gravar(db, figuras[i], u.id))
                except (ErroImagem, IndexError):
                    problemas += 1
                    gravadas[i] = ""
            return gravadas[i]

        for q in res["questoes"]:
            for campo in ("enunciado", "gabarito_texto", "explicacao"):
                if q.get(campo):
                    q[campo] = MARCA_IMG_ARQUIVO.sub(trocar, q[campo]).strip()
            for a in q.get("alternativas", []):
                a["texto"] = MARCA_IMG_ARQUIVO.sub(trocar, a["texto"]).strip()
        db.commit()
        qtd = sum(1 for v in gravadas.values() if v)
        if qtd:
            res["avisos"].append(f"{qtd} imagem(ns) do arquivo incluída(s) nas questões.")
        if problemas:
            res["avisos"].append(f"{problemas} imagem(ns) do arquivo não puderam ser lidas.")
    res["cabecalho"] = [MARCA_IMG_ARQUIVO.sub("", c) for c in res.get("cabecalho", [])]
    return res


@router.post("/avaliacoes/{aid}/questoes/lote")
def criar_questoes_lote(aid: int, dados: QuestoesLoteIn, db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    """Grava de uma vez as questões importadas (depois da conferência na prévia)."""
    av = _get_av(db, aid, u)
    _bloqueia_se_iniciada(db, av)
    if dados.substituir:
        for q in list(av.questoes):
            av.questoes.remove(q)
            db.delete(q)
        db.flush()
    ordem = max((x.ordem for x in av.questoes), default=0)
    for item in dados.questoes:
        ordem += 1
        q = Questao(ordem=ordem)
        _aplicar_questao(q, item, av)
        av.questoes.append(q)
    redistribuir_pontos(av)
    db.commit()
    return _av_out(_get_av(db, aid, u), db, completo=True)


class PesosIn(BaseModel):
    pesos: dict[int, float]  # {questao_id: peso}


@router.put("/avaliacoes/{aid}/pesos")
def definir_pesos(aid: int, dados: PesosIn, db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    """O professor define o peso de cada questão; a nota total é redistribuída."""
    av = _get_av(db, aid, u)
    _bloqueia_se_iniciada(db, av)
    for q in av.questoes:
        if q.id in dados.pesos:
            if not (0 < dados.pesos[q.id] <= 100):
                raise HTTPException(400, "Os pesos devem ser maiores que zero")
            q.peso = dados.pesos[q.id]
    redistribuir_pontos(av)
    db.commit()
    return _av_out(av, db, completo=True)


@router.post("/avaliacoes/{aid}/pesos-padrao")
def aplicar_pesos_padrao(aid: int, db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    """Aplica a todas as questões o peso padrão do tipo (objetiva/dissertativa) definido na avaliação."""
    av = _get_av(db, aid, u)
    _bloqueia_se_iniciada(db, av)
    for q in av.questoes:
        q.peso = av.peso_dissertativa if q.tipo == "dissertativa" else av.peso_objetiva
    redistribuir_pontos(av)
    db.commit()
    return _av_out(av, db, completo=True)


class OrdemIn(BaseModel):
    ids: list[int]


@router.put("/avaliacoes/{aid}/ordem")
def reordenar(aid: int, dados: OrdemIn, db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    av = _get_av(db, aid, u)
    pos = {qid: i for i, qid in enumerate(dados.ids)}
    for q in av.questoes:
        q.ordem = pos.get(q.id, len(pos) + q.ordem)
    db.commit()
    return {"ok": True}


# ---------- resultados ----------
@router.get("/avaliacoes/{aid}/resultados")
def resultados(aid: int, db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    av = _get_av(db, aid, u)
    finalizar_expiradas(db, aid)
    # se a avaliação já terminou, fecha também quem ainda estava respondendo
    if agora() >= av.fim:
        abertas = db.scalars(select(Tentativa).where(Tentativa.avaliacao_id == aid, Tentativa.enviado_em.is_(None))).all()
        for t in abertas:
            corrigir_tentativa(carregar_tentativa(db, t.id), automatico=True)
        if abertas:
            db.commit()

    alunos = db.scalars(select(Usuario).join(Matricula, Matricula.aluno_id == Usuario.id)
                        .where(Matricula.turma_id == av.turma_id, Usuario.papel == "aluno",
                               Usuario.ativo.is_(True)).order_by(Usuario.nome)).all()
    tentativas = {t.aluno_id: t for t in db.scalars(
        select(Tentativa).where(Tentativa.avaliacao_id == aid).options(selectinload(Tentativa.respostas)))}
    # inclui alunos que fizeram mas mudaram de turma
    ids_alunos = {a.id for a in alunos}
    extras = [x for x in (db.get(Usuario, uid) for uid in tentativas if uid not in ids_alunos) if x]

    linhas = []
    for a in list(alunos) + extras:
        t = tentativas.get(a.id)
        if t is None:
            situacao = "nao_iniciou"
        elif t.enviado_em is None:
            situacao = "respondendo"
        else:
            situacao = "enviada"
        pendente = bool(t and t.enviado_em and any(
            r.pontos_revisados is None and r.questao.tipo == "dissertativa" for r in t.respostas))
        linhas.append({"aluno_id": a.id, "nome": a.nome, "login": a.login, "situacao": situacao,
                       "tentativa_id": t.id if t else None, "nota": t.nota if t else None,
                       "nota_max": t.nota_max if t else None,
                       "iniciado_em": iso(t.iniciado_em) if t else None,
                       "enviado_em": iso(t.enviado_em) if t else None,
                       "envio_automatico": t.envio_automatico if t else False,
                       "dissertativas_nao_revisadas": pendente,
                       "monitoramento": monitoramento_out(t, incluir_eventos=False) if t else None})

    # estatística por questão
    stats = []
    enviados = [t for t in tentativas.values() if t.enviado_em]
    for n, q in enumerate(av.questoes, start=1):
        rs = [r for t in enviados for r in t.respostas if r.questao_id == q.id]
        certas = sum(1 for r in rs if r.situacao == "certa")
        media = sum(r.pontos_finais for r in rs) / len(rs) if rs else 0
        item = {"numero": n, "questao_id": q.id, "tipo": q.tipo, "enunciado": sem_imagens(q.enunciado)[:120],
                "pontos": q.pontos, "respostas": len(rs), "acertos": certas,
                "percentual_acerto": round(100 * certas / len(rs)) if rs else None,
                "media_pontos": round(media, 2)}
        if q.tipo == "objetiva":
            item["distribuicao"] = [{"texto": a.texto[:60], "correta": a.correta,
                                     "qtd": sum(1 for r in rs if r.alternativa_id == a.id)} for a in q.alternativas]
        stats.append(item)

    notas = [t.nota for t in enviados if t.nota is not None]
    return {
        "avaliacao": _av_out(av, db),
        "alunos": linhas,
        "questoes": stats,
        "resumo": {"total_alunos": len(linhas), "enviadas": len(enviados),
                   "media": round(sum(notas) / len(notas), 2) if notas else None,
                   "maior": max(notas) if notas else None, "menor": min(notas) if notas else None,
                   "resultado_visivel_para_alunos": resultado_visivel(av, enviados[0]) if enviados else False},
    }


@router.get("/avaliacoes/{aid}/resultados.csv")
def exportar_csv(aid: int, db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    dados = resultados(aid, db, u)
    buf = io.StringIO()
    buf.write("﻿")  # BOM para o Excel reconhecer acentos
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Aluno", "Login", "Situação", "Nota", "Nota máxima", "Iniciado em (UTC)", "Enviado em (UTC)",
                "Tempo gasto (min)", "Saídas da aba/janela", "Tempo fora (s)", "Fechou/recarregou a página",
                "Acessos", "Outro navegador/dispositivo", "IP", "Navegador"])
    num = lambda v: "" if v is None else str(v).replace(".", ",")  # noqa: E731
    for l in dados["alunos"]:
        m = l["monitoramento"] or {}
        w.writerow([l["nome"], l["login"], l["situacao"], num(l["nota"]), num(l["nota_max"]),
                    l["iniciado_em"] or "", l["enviado_em"] or "",
                    num(round(m["tempo_gasto_seg"] / 60, 1)) if m else "", m.get("qtd_saidas", ""),
                    m.get("tempo_fora_seg", ""), m.get("qtd_fechamentos", ""), m.get("qtd_acessos", ""),
                    ("sim" if m.get("outro_dispositivo") else "não") if m else "",
                    m.get("ip_inicio") or "", m.get("navegador_inicio") or ""])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="resultados_{aid}.csv"'})


@router.post("/avaliacoes/{aid}/publicar")
def publicar(aid: int, publicar: bool = True, db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    """Publica (os alunos da turma passam a ver) ou volta para rascunho."""
    av = _get_av(db, aid, u)
    if publicar and not av.questoes:
        raise HTTPException(400, "Adicione pelo menos uma questão antes de publicar")
    av.publicada = publicar
    db.commit()
    return _av_out(av, db)


@router.post("/avaliacoes/{aid}/liberar-resultado")
def liberar(aid: int, liberar: bool = True, db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    av = _get_av(db, aid, u)
    av.resultado_liberado = liberar
    db.commit()
    return {"ok": True, "resultado_liberado": av.resultado_liberado}


@router.post("/avaliacoes/{aid}/encerrar")
def encerrar_agora(aid: int, db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    """Encerra a avaliação imediatamente: todas as provas abertas são enviadas e corrigidas."""
    av = _get_av(db, aid, u)
    av.fim = min(av.fim, agora())
    db.commit()
    return resultados(aid, db, u)["resumo"]


@router.get("/tentativas/{tid}")
def ver_tentativa(tid: int, db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    t = carregar_tentativa(db, tid) or _404()
    avaliacao_do_usuario(u, t.avaliacao)
    if t.enviado_em is None:
        raise HTTPException(400, "O aluno ainda está respondendo")
    return feedback_tentativa(t, incluir_aluno=True)


@router.get("/tentativas/{tid}/monitoramento")
def ver_monitoramento(tid: int, db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    """Acompanhamento ao vivo de um aluno que ainda está respondendo."""
    t = carregar_tentativa(db, tid) or _404()
    avaliacao_do_usuario(u, t.avaliacao)
    return monitoramento_out(t)


@router.delete("/tentativas/{tid}")
def reabrir_tentativa(tid: int, db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    """Apaga a tentativa para o aluno refazer (ex.: queda de energia)."""
    t = db.get(Tentativa, tid) or _404()
    avaliacao_do_usuario(u, t.avaliacao)
    db.delete(t)
    db.commit()
    return {"ok": True}


class RevisaoIn(BaseModel):
    pontos: float | None = Field(default=None, ge=0)
    comentario: str | None = None


@router.put("/respostas/{rid}/revisar")
def revisar(rid: int, dados: RevisaoIn, db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    r = db.get(Resposta, rid) or _404()
    avaliacao_do_usuario(u, r.tentativa.avaliacao)
    if dados.pontos is not None and round(dados.pontos, 2) > round(r.questao.pontos, 2) + 1e-9:
        raise HTTPException(400, f"A pontuação máxima desta questão é {r.questao.pontos}")
    r.pontos_revisados = None if dados.pontos is None else round(dados.pontos, 2)
    r.comentario_professor = dados.comentario
    recalcular_nota(r.tentativa)
    db.commit()
    return {"ok": True, "nota": r.tentativa.nota}


def _404():
    raise HTTPException(404, "Registro não encontrado")
