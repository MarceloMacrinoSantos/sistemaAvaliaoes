"""Área do aluno: listar avaliações, responder (com questões embaralhadas) e ver o feedback."""
import random
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..auth import exige_aluno
from ..correcao import corrigir_tentativa
from ..db import get_db
from ..models import Avaliacao, Evento, Matricula, Questao, Resposta, Tentativa, Usuario, agora
from ..servicos import (carregar_tentativa, feedback_tentativa, ip_da_requisicao, iso, para_utc, resultado_visivel,
                        tentativa_expirada)

router = APIRouter(prefix="/api/aluno")
_rng = random.SystemRandom()

TOLERANCIA = timedelta(seconds=15)  # absorve atraso de rede no último salvamento


def _turmas_do_aluno(db: Session, aluno: Usuario) -> list[int]:
    return list(db.scalars(select(Matricula.turma_id).where(Matricula.aluno_id == aluno.id)))


@router.get("/avaliacoes")
def minhas_avaliacoes(db: Session = Depends(get_db), aluno: Usuario = Depends(exige_aluno)):
    turmas = _turmas_do_aluno(db, aluno)
    if not turmas:
        return []
    avs = db.scalars(select(Avaliacao).where(Avaliacao.turma_id.in_(turmas), Avaliacao.publicada.is_(True))
                     .options(selectinload(Avaliacao.questoes)).order_by(Avaliacao.inicio.desc())).all()
    tentativas = {t.avaliacao_id: t for t in db.scalars(
        select(Tentativa).where(Tentativa.aluno_id == aluno.id)
        .options(selectinload(Tentativa.respostas),
                 selectinload(Tentativa.avaliacao).selectinload(Avaliacao.questoes)
                 .selectinload(Questao.alternativas)))}
    mudou = False
    out = []
    agora_ = agora()
    for av in avs:
        t = tentativas.get(av.id)
        if t and (tentativa_expirada(t) or (t.enviado_em is None and agora_ >= av.fim)):
            corrigir_tentativa(t, automatico=True)
            mudou = True
        if t and t.enviado_em:
            situacao = "enviada"
        elif t:
            situacao = "em_andamento"
        elif agora_ < av.inicio:
            situacao = "agendada"
        elif agora_ < av.fim:
            situacao = "disponivel"
        else:
            situacao = "perdida"
        visivel = resultado_visivel(av, t)
        out.append({"id": av.id, "titulo": av.titulo, "descricao": av.descricao, "tipo": av.tipo,
                    "disciplina": av.disciplina.nome, "turma": av.turma.nome, "escola": av.escola.nome, "inicio": iso(av.inicio), "fim": iso(av.fim),
                    "duracao_min": av.duracao_min, "qtd_questoes": len(av.questoes), "situacao": situacao,
                    "nota_total": av.nota_total, "monitorar": av.monitorar,
                    "tentativa_id": t.id if t else None, "resultado_disponivel": visivel,
                    "nota": t.nota if (t and visivel) else None, "nota_max": t.nota_max if (t and visivel) else None})
    if mudou:
        db.commit()
    return out


def _prova_out(t: Tentativa) -> dict:
    av = t.avaliacao
    questoes = {q.id: q for q in av.questoes}
    respostas = {r.questao_id: r for r in t.respostas}
    itens = []
    for n, qid in enumerate([i for i in t.ordem_questoes if i in questoes], start=1):
        q = questoes[qid]
        item = {"numero": n, "id": q.id, "tipo": q.tipo, "enunciado": q.enunciado, "pontos": q.pontos, "peso": q.peso}
        if q.tipo == "objetiva":
            alts = {a.id: a for a in q.alternativas}
            ordem = t.ordem_alternativas.get(str(q.id)) or list(alts)
            item["alternativas"] = [{"id": alts[i].id, "texto": alts[i].texto} for i in ordem if i in alts]
        itens.append(item)
    return {
        "tentativa_id": t.id, "titulo": av.titulo, "descricao": av.descricao, "disciplina": av.disciplina.nome,
        "prazo": iso(t.prazo), "agora": iso(agora()), "questoes": itens, "nota_total": av.nota_total,
        "monitorar": av.monitorar,
        "monitoramento": {"qtd_saidas": t.qtd_saidas or 0, "tempo_fora_seg": t.tempo_fora_seg or 0,
                          "qtd_fechamentos": t.qtd_fechamentos or 0, "qtd_acessos": t.qtd_acessos or 1,
                          "outro_dispositivo": bool(t.outro_dispositivo)},
        "respostas": {str(qid): {"alternativa_id": r.alternativa_id, "texto": r.texto} for qid, r in respostas.items()},
    }


class InicioIn(BaseModel):
    tela: str | None = Field(default=None, max_length=40)  # resolução da tela, ex.: "1366x768"


@router.post("/avaliacoes/{aid}/iniciar")
def iniciar(aid: int, request: Request, dados: InicioIn | None = None, db: Session = Depends(get_db),
            aluno: Usuario = Depends(exige_aluno)):
    ip = ip_da_requisicao(request)
    ua = (request.headers.get("user-agent") or "")[:500]
    av = db.scalar(select(Avaliacao).where(Avaliacao.id == aid)
                   .options(selectinload(Avaliacao.questoes).selectinload(Questao.alternativas)))
    if not av or not av.publicada or av.turma_id not in _turmas_do_aluno(db, aluno):
        raise HTTPException(404, "Avaliação não encontrada")

    t = db.scalar(select(Tentativa).where(Tentativa.avaliacao_id == aid, Tentativa.aluno_id == aluno.id))
    if t:
        t = carregar_tentativa(db, t.id)
        if t.enviado_em is None and (tentativa_expirada(t) or agora() >= av.fim):
            corrigir_tentativa(t, automatico=True)
            db.commit()
        if t.enviado_em:
            raise HTTPException(409, "Você já enviou esta avaliação")
        # reabertura: registra e verifica se é outro navegador/dispositivo
        ultimo = next((e for e in reversed(t.eventos) if e.navegador), None)
        mudou = bool(ultimo and (ultimo.navegador != ua or ultimo.ip != ip))
        t.qtd_acessos = (t.qtd_acessos or 1) + 1
        if mudou:
            t.outro_dispositivo = True
        t.eventos.append(Evento(tipo="outro_dispositivo" if mudou else "retomada", ip=ip, navegador=ua,
                                detalhe=(dados.tela if dados else None)))
        db.commit()
        return _prova_out(t)

    agora_ = agora()
    if agora_ < av.inicio:
        raise HTTPException(400, "A avaliação ainda não começou")
    if agora_ >= av.fim:
        raise HTTPException(400, "O prazo desta avaliação terminou")
    if not av.questoes:
        raise HTTPException(400, "Avaliação sem questões")

    ids = [q.id for q in av.questoes]
    if av.embaralhar_questoes:
        _rng.shuffle(ids)
    ordem_alts = {}
    for q in av.questoes:
        if q.tipo == "objetiva":
            alts = [a.id for a in q.alternativas]
            if av.embaralhar_alternativas:
                _rng.shuffle(alts)
            ordem_alts[str(q.id)] = alts
    prazo = av.fim
    if av.duracao_min:
        prazo = min(av.fim, agora_ + timedelta(minutes=av.duracao_min))

    t = Tentativa(avaliacao_id=aid, aluno_id=aluno.id, iniciado_em=agora_, prazo=prazo,
                  ordem_questoes=ids, ordem_alternativas=ordem_alts, ip_inicio=ip, navegador_inicio=ua,
                  tela=(dados.tela if dados else None), qtd_acessos=1)
    t.eventos.append(Evento(tipo="inicio", em=agora_, ip=ip, navegador=ua, detalhe=(dados.tela if dados else None)))
    db.add(t)
    try:
        db.commit()
    except IntegrityError:  # clique duplo / duas abas ao mesmo tempo
        db.rollback()
        t = db.scalar(select(Tentativa).where(Tentativa.avaliacao_id == aid, Tentativa.aluno_id == aluno.id))
    return _prova_out(carregar_tentativa(db, t.id))


def _tentativa_do_aluno(db: Session, tid: int, aluno: Usuario) -> Tentativa:
    t = carregar_tentativa(db, tid)
    if not t or t.aluno_id != aluno.id:
        raise HTTPException(404, "Tentativa não encontrada")
    return t


class RespostaIn(BaseModel):
    questao_id: int
    alternativa_id: int | None = None
    texto: str | None = None


@router.put("/tentativas/{tid}/respostas")
def salvar_resposta(tid: int, dados: RespostaIn, db: Session = Depends(get_db),
                    aluno: Usuario = Depends(exige_aluno)):
    t = _tentativa_do_aluno(db, tid, aluno)
    if t.enviado_em:
        raise HTTPException(409, "Avaliação já enviada")
    if agora() > t.prazo + TOLERANCIA:
        corrigir_tentativa(t, automatico=True)
        db.commit()
        raise HTTPException(409, "O tempo acabou. Sua avaliação foi enviada automaticamente.")

    q = next((q for q in t.avaliacao.questoes if q.id == dados.questao_id), None)
    if not q:
        raise HTTPException(400, "Questão inválida")
    if q.tipo == "objetiva" and dados.alternativa_id is not None and \
            dados.alternativa_id not in {a.id for a in q.alternativas}:
        raise HTTPException(400, "Alternativa inválida")

    r = next((r for r in t.respostas if r.questao_id == q.id), None)
    if r is None:
        r = Resposta(tentativa_id=t.id, questao_id=q.id)
        db.add(r)
    if q.tipo == "objetiva":
        r.alternativa_id = dados.alternativa_id
    else:
        r.texto = (dados.texto or "")[:20000]
    try:
        db.commit()
    except IntegrityError:  # duas gravações simultâneas da mesma questão
        db.rollback()
        return salvar_resposta(tid, dados, db, aluno)
    return {"ok": True, "salvo_em": iso(agora())}


class EventoIn(BaseModel):
    tipo: Literal["saiu_aba", "saiu_janela", "voltou", "fechou"]
    em: datetime | None = None                       # horário no navegador (eventos guardados sem internet)
    duracao_seg: int | None = Field(default=None, ge=0, le=86400)


class EventosIn(BaseModel):
    eventos: list[EventoIn] = Field(max_length=200)


@router.post("/tentativas/{tid}/eventos")
def registrar_eventos(tid: int, dados: EventosIn, request: Request, db: Session = Depends(get_db),
                      aluno: Usuario = Depends(exige_aluno)):
    """Recebe do navegador as saídas de aba/janela, retornos e fechamentos da página."""
    t = _tentativa_do_aluno(db, tid, aluno)
    if t.enviado_em is None and t.avaliacao.monitorar:
        ip = ip_da_requisicao(request)
        agora_ = agora()
        for ev in dados.eventos:
            em = para_utc(ev.em) if ev.em else agora_
            if not (t.iniciado_em - timedelta(minutes=1) <= em <= agora_ + timedelta(minutes=1)):
                em = agora_  # relógio do aluno errado: usa o do servidor
            t.eventos.append(Evento(tipo=ev.tipo, em=em, duracao_seg=ev.duracao_seg, ip=ip))
            if ev.tipo in ("saiu_aba", "saiu_janela"):
                t.qtd_saidas = (t.qtd_saidas or 0) + 1
            elif ev.tipo == "voltou":
                t.tempo_fora_seg = (t.tempo_fora_seg or 0) + (ev.duracao_seg or 0)
            elif ev.tipo == "fechou":
                t.qtd_fechamentos = (t.qtd_fechamentos or 0) + 1
        db.commit()
    return {"qtd_saidas": t.qtd_saidas or 0, "tempo_fora_seg": t.tempo_fora_seg or 0,
            "qtd_fechamentos": t.qtd_fechamentos or 0}


@router.post("/tentativas/{tid}/enviar")
def enviar(tid: int, request: Request, db: Session = Depends(get_db), aluno: Usuario = Depends(exige_aluno)):
    t = _tentativa_do_aluno(db, tid, aluno)
    if t.enviado_em is None:
        automatico = agora() > t.prazo + TOLERANCIA
        corrigir_tentativa(t, automatico=automatico)
        t.ip_envio = ip_da_requisicao(request)
        t.navegador_envio = (request.headers.get("user-agent") or "")[:500]
        if not automatico:  # o envio automático já é registrado na correção
            t.eventos.append(Evento(tipo="envio", ip=t.ip_envio, navegador=t.navegador_envio))
        db.commit()
    return {"ok": True, "resultado_disponivel": resultado_visivel(t.avaliacao, t),
            "fim_avaliacao": iso(t.avaliacao.fim)}


@router.get("/tentativas/{tid}/resultado")
def resultado(tid: int, db: Session = Depends(get_db), aluno: Usuario = Depends(exige_aluno)):
    t = _tentativa_do_aluno(db, tid, aluno)
    if t.enviado_em is None and tentativa_expirada(t):
        corrigir_tentativa(t, automatico=True)
        db.commit()
    if not resultado_visivel(t.avaliacao, t):
        raise HTTPException(403, "O resultado será liberado após o encerramento da avaliação")
    return feedback_tentativa(t)
