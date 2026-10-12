"""Painel de análises do professor: desempenho por avaliação, turma, disciplina, questão e aluno.

Tudo é calculado a partir das avaliações do próprio professor (o administrador vê todas).
As notas são normalizadas em % da nota máxima, para comparar avaliações com valores diferentes.
"""
from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..acesso import eh_admin
from ..auth import exige_professor
from ..db import get_db
from ..imagens import sem_imagens
from ..models import Avaliacao, Matricula, Questao, Tentativa, Usuario, agora
from ..servicos import finalizar_expiradas, iso, para_utc

router = APIRouter(prefix="/api")


def _pct(nota, maximo):
    return round(100 * nota / maximo, 1) if maximo else None


def _media(vals):
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 1) if vals else None


@router.get("/analises")
def analises(escola_id: int | None = None, turma_id: int | None = None, disciplina_id: int | None = None,
             inicio: datetime | None = None, fim: datetime | None = None,
             corte: float = Query(60, ge=0, le=100, description="% mínimo para aprovação"),
             db: Session = Depends(get_db), u: Usuario = Depends(exige_professor)):
    q = (select(Avaliacao).where(Avaliacao.publicada.is_(True))
         .options(selectinload(Avaliacao.questoes).selectinload(Questao.alternativas),
                  selectinload(Avaliacao.tentativas).selectinload(Tentativa.respostas))
         .order_by(Avaliacao.inicio))
    if not eh_admin(u):
        q = q.where(Avaliacao.professor_id == u.id)
    if escola_id:
        q = q.where(Avaliacao.escola_id == escola_id)
    if turma_id:
        q = q.where(Avaliacao.turma_id == turma_id)
    if disciplina_id:
        q = q.where(Avaliacao.disciplina_id == disciplina_id)
    if inicio:
        q = q.where(Avaliacao.inicio >= para_utc(inicio))
    if fim:
        q = q.where(Avaliacao.inicio <= para_utc(fim))
    avs = list(db.scalars(q))
    for av in avs:  # garante que provas com tempo esgotado entrem corrigidas
        finalizar_expiradas(db, av.id)

    # alunos matriculados por turma
    turma_ids = {av.turma_id for av in avs}
    matriculados = defaultdict(set)
    for m in db.scalars(select(Matricula).where(Matricula.turma_id.in_(turma_ids or [-1]))):
        matriculados[m.turma_id].add(m.aluno_id)
    alunos = {a.id: a for a in db.scalars(select(Usuario).where(
        Usuario.id.in_({aid for s in matriculados.values() for aid in s} or [-1])))}

    agora_ = agora()
    por_av, todas_pct = [], []
    turmas = {}
    nota_aluno = defaultdict(dict)     # aluno_id -> {av_id: pct | None (não fez)}
    saidas_aluno = defaultdict(int)
    questoes, tipos = [], defaultdict(lambda: [0.0, 0.0])  # tipo -> [pontos obtidos, pontos possíveis]

    for av in avs:
        enviadas = [t for t in av.tentativas if t.enviado_em]
        pcts = [_pct(t.nota or 0, t.nota_max or av.nota_total) for t in enviadas]
        mats = matriculados.get(av.turma_id, set())
        encerrada = agora_ >= av.fim
        turmas.setdefault(av.turma_id, {"id": av.turma_id, "nome": av.turma.nome, "escola": av.escola.nome,
                                        "pcts": [], "esperadas": 0, "feitas": 0})
        tu = turmas[av.turma_id]
        tu["pcts"] += pcts
        if encerrada:
            tu["esperadas"] += len(mats)
            tu["feitas"] += len({t.aluno_id for t in enviadas} & mats)
        todas_pct += pcts
        por_av.append({
            "id": av.id, "titulo": av.titulo, "data": iso(av.inicio), "turma_id": av.turma_id, "turma": av.turma.nome,
            "disciplina": av.disciplina.nome, "encerrada": encerrada, "enviadas": len(enviadas),
            "matriculados": len(mats), "media": _media(pcts),
            "aprovacao": round(100 * sum(p >= corte for p in pcts) / len(pcts)) if pcts else None,
        })
        feitos = {}
        for t in enviadas:
            feitos[t.aluno_id] = _pct(t.nota or 0, t.nota_max or av.nota_total)
            saidas_aluno[t.aluno_id] += (t.qtd_saidas or 0) + (t.qtd_fechamentos or 0)
        for aid in mats:
            if aid in feitos:
                nota_aluno[aid][av.id] = feitos[aid]
            elif encerrada:
                nota_aluno[aid][av.id] = None  # faltou
        # questões
        respostas = defaultdict(list)
        for t in enviadas:
            for r in t.respostas:
                respostas[r.questao_id].append(r)
        for n, qu in enumerate(av.questoes, start=1):
            rs = respostas.get(qu.id, [])
            if not rs or not qu.pontos:
                continue
            obtido = sum(r.pontos_finais for r in rs)
            tipos[qu.tipo][0] += obtido
            tipos[qu.tipo][1] += qu.pontos * len(rs)
            item = {"avaliacao_id": av.id, "avaliacao": av.titulo, "turma": av.turma.nome, "numero": n,
                    "tipo": qu.tipo, "enunciado": sem_imagens(qu.enunciado).strip().split("\n")[0][:140], "respostas": len(rs),
                    "aproveitamento": round(100 * obtido / (qu.pontos * len(rs)), 1)}
            if qu.tipo == "objetiva":
                cont = defaultdict(int)
                for r in rs:
                    cont[r.alternativa_id] += 1
                erradas = [(cont[a.id], a.texto) for a in qu.alternativas if not a.correta and cont[a.id]]
                if erradas:
                    qtd, texto = max(erradas)
                    item["distrator"] = {"texto": texto[:90], "percentual": round(100 * qtd / len(rs))}
            questoes.append(item)

    # distribuição das notas (faixas de 10%)
    faixas = [0] * 10
    for p in todas_pct:
        faixas[min(9, int(p // 10))] += 1

    # alunos: média, tendência, faltas, monitoramento
    lista_alunos = []
    ordem_av = [a["id"] for a in por_av]
    for aid, notas in nota_aluno.items():
        a = alunos.get(aid)
        if not a:
            continue
        seq = [notas[i] for i in ordem_av if i in notas and notas[i] is not None]
        faltas = sum(1 for v in notas.values() if v is None)
        media = _media(seq)
        tendencia = round(seq[-1] - seq[-2], 1) if len(seq) >= 2 else None
        motivos = []
        if media is not None and media < corte:
            motivos.append("abaixo do corte")
        if tendencia is not None and tendencia <= -20:
            motivos.append("queda forte")
        if faltas:
            motivos.append(f"{faltas} não feita(s)")
        if saidas_aluno[aid] >= 3:
            motivos.append("saiu da prova várias vezes")
        lista_alunos.append({"id": aid, "nome": a.nome, "login": a.login, "media": media, "avaliacoes": len(seq),
                             "faltas": faltas, "tendencia": tendencia, "saidas": saidas_aluno[aid],
                             "notas": {str(k): v for k, v in notas.items()}, "atencao": motivos})
    lista_alunos.sort(key=lambda x: (x["media"] is None, x["media"] if x["media"] is not None else 0))

    lista_turmas = []
    for t in turmas.values():
        pcts = t.pop("pcts")
        t["media"] = _media(pcts)
        t["aprovacao"] = round(100 * sum(p >= corte for p in pcts) / len(pcts)) if pcts else None
        t["participacao"] = round(100 * t["feitas"] / t["esperadas"]) if t["esperadas"] else None
        lista_turmas.append(t)

    esperadas = sum(t["esperadas"] for t in lista_turmas)
    feitas = sum(t["feitas"] for t in lista_turmas)
    return {
        "corte": corte,
        "resumo": {
            "avaliacoes": len(avs), "provas_corrigidas": len(todas_pct),
            "alunos": len(lista_alunos), "media": _media(todas_pct),
            "aprovacao": round(100 * sum(p >= corte for p in todas_pct) / len(todas_pct)) if todas_pct else None,
            "participacao": round(100 * feitas / esperadas) if esperadas else None,
            "alunos_atencao": sum(1 for a in lista_alunos if a["atencao"]),
        },
        "avaliacoes": por_av,
        "turmas": sorted(lista_turmas, key=lambda t: t["nome"]),
        "distribuicao": [{"faixa": f"{i * 10}–{i * 10 + 10}%", "qtd": q} for i, q in enumerate(faixas)],
        "questoes_dificeis": sorted(questoes, key=lambda x: x["aproveitamento"])[:10],
        "questoes_faceis": sorted(questoes, key=lambda x: -x["aproveitamento"])[:5],
        "tipos": {k: round(100 * v[0] / v[1], 1) for k, v in tipos.items() if v[1]},
        "alunos": lista_alunos,
    }
