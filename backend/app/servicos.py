from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .correcao import corrigir_tentativa
from .models import Avaliacao, Questao, Resposta, Tentativa, agora


def iso(dt: datetime | None) -> str | None:
    """Datas saem sempre em UTC com 'Z' para o navegador converter para o fuso local."""
    return dt.replace(microsecond=0).isoformat() + "Z" if dt else None


def para_utc(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def tentativa_expirada(t: Tentativa) -> bool:
    return t.enviado_em is None and agora() >= t.prazo


def carregar_tentativa(db: Session, tentativa_id: int) -> Tentativa | None:
    return db.scalar(
        select(Tentativa).where(Tentativa.id == tentativa_id).options(
            selectinload(Tentativa.respostas), selectinload(Tentativa.eventos),
            selectinload(Tentativa.avaliacao).selectinload(Avaliacao.questoes).selectinload(Questao.alternativas),
        )
    )


def finalizar_expiradas(db: Session, avaliacao_id: int) -> None:
    """Envia e corrige automaticamente as tentativas cujo tempo acabou.

    É chamada de forma "preguiçosa" (sempre que alguém consulta resultados ou a
    própria tentativa), dispensando um processo agendado em segundo plano.
    """
    pendentes = db.scalars(
        select(Tentativa).where(Tentativa.avaliacao_id == avaliacao_id, Tentativa.enviado_em.is_(None),
                                Tentativa.prazo <= agora())
        .options(selectinload(Tentativa.respostas),
                 selectinload(Tentativa.avaliacao).selectinload(Avaliacao.questoes)
                 .selectinload(Questao.alternativas))
    ).all()
    for t in pendentes:
        corrigir_tentativa(t, automatico=True)
    if pendentes:
        db.commit()


def resultado_visivel(av: Avaliacao, t: Tentativa | None) -> bool:
    if t is None or t.enviado_em is None:
        return False
    if av.resultado_liberado:
        return True
    if av.liberar_resultado == "apos_envio":
        return True
    if av.liberar_resultado == "apos_fim":
        return agora() >= av.fim
    return False


def feedback_tentativa(t: Tentativa, incluir_aluno: bool = False) -> dict:
    """Monta o relatório de correção questão a questão (na ordem vista pelo aluno)."""
    av = t.avaliacao
    questoes = {q.id: q for q in av.questoes}
    respostas: dict[int, Resposta] = {r.questao_id: r for r in t.respostas}
    ordem = [qid for qid in (t.ordem_questoes or []) if qid in questoes]
    ordem += [qid for qid in questoes if qid not in ordem]

    itens = []
    for n, qid in enumerate(ordem, start=1):
        q = questoes[qid]
        r = respostas.get(qid)
        item = {
            "numero": n,
            "questao_id": q.id,
            "tipo": q.tipo,
            "enunciado": q.enunciado,
            "pontos_max": q.pontos,
            "peso": q.peso,
            "pontos": r.pontos_finais if r else 0.0,
            "situacao": (r.situacao if r else "em_branco"),
            "feedback": r.feedback_auto if r else "Questão não respondida.",
            "comentario_professor": r.comentario_professor if r else None,
            "revisado": bool(r and r.pontos_revisados is not None),
            "explicacao": q.explicacao,
            "resposta_id": r.id if r else None,
        }
        if r and r.pontos_revisados is not None and q.tipo == "dissertativa":
            if r.pontos_revisados >= q.pontos:
                item["situacao"] = "certa"
            elif r.pontos_revisados <= 0:
                item["situacao"] = "errada"
            else:
                item["situacao"] = "parcial"
        if q.tipo == "objetiva":
            alt_ids = (t.ordem_alternativas or {}).get(str(q.id)) or [a.id for a in q.alternativas]
            alts = {a.id: a for a in q.alternativas}
            item["alternativas"] = [
                {"id": a.id, "texto": a.texto, "correta": a.correta,
                 "marcada": bool(r and r.alternativa_id == a.id)}
                for a in (alts[i] for i in alt_ids if i in alts)
            ]
        else:
            item["resposta_texto"] = r.texto if r else None
            item["gabarito"] = q.gabarito_texto
            if incluir_aluno and r:  # visão do professor: as duas correções lado a lado
                item["ia"] = {"modo": av.correcao_ia or "desligada", "status": r.ia_status, "pontos": r.ia_pontos,
                              "feedback": r.ia_feedback, "provedor": r.ia_provedor, "erro": r.ia_erro,
                              "pontos_chaves": r.pontos_chaves, "feedback_chaves": r.feedback_chaves}
        itens.append(item)

    acertos = sum(1 for i in itens if i["situacao"] == "certa")
    out = {
        "tentativa_id": t.id,
        "avaliacao": {"id": av.id, "titulo": av.titulo, "disciplina": av.disciplina.nome},
        "nota": t.nota,
        "nota_max": t.nota_max,
        "acertos": acertos,
        "total_questoes": len(itens),
        "enviado_em": iso(t.enviado_em),
        "envio_automatico": t.envio_automatico,
        "questoes": itens,
    }
    out["monitoramento"] = monitoramento_out(t)
    if incluir_aluno:
        out["aluno"] = {"id": t.aluno.id, "nome": t.aluno.nome, "login": t.aluno.login}
    return out


# ---------------- distribuição da nota pelos pesos ----------------
def redistribuir_pontos(av: Avaliacao) -> None:
    """Reparte a nota total entre as questões, proporcional ao peso de cada uma.

    Ex.: nota 10, quatro objetivas peso 1 e uma dissertativa peso 2 -> soma 6;
    cada objetiva vale 10*1/6 = 1,67 e a dissertativa 10*2/6 = 3,33.
    A diferença de arredondamento vai para a questão de maior peso, para a soma fechar exata.
    """
    qs = list(av.questoes)
    soma = sum(max(q.peso or 0, 0) for q in qs)
    if not qs or soma <= 0:
        return
    total = float(av.nota_total or 0)
    for q in qs:
        q.pontos = round(total * q.peso / soma, 2)
    diferenca = round(total - sum(q.pontos for q in qs), 2)
    if diferenca:
        maior = max(qs, key=lambda q: (q.peso, q.ordem))
        maior.pontos = round(maior.pontos + diferenca, 2)


# ---------------- metadados de acesso ----------------
def ip_da_requisicao(request) -> str | None:
    cf = request.headers.get("cf-connecting-ip")  # acesso pelo túnel da Cloudflare
    if cf:
        return cf.strip()[:64]
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()[:64]
    return request.client.host if request.client else None


def descrever_navegador(ua: str | None) -> str:
    """Resumo legível do User-Agent, ex.: 'Chrome 128 · Windows'."""
    if not ua:
        return "desconhecido"
    import re
    nav = "Outro navegador"
    for nome, padrao in [("Edge", r"Edg(?:e|A|iOS)?/(\d+)"), ("Opera", r"(?:OPR|Opera)/(\d+)"),
                         ("Samsung Internet", r"SamsungBrowser/(\d+)"), ("Firefox", r"(?:Firefox|FxiOS)/(\d+)"),
                         ("Chrome", r"(?:Chrome|CriOS)/(\d+)"), ("Safari", r"Version/(\d+).*Safari")]:
        m = re.search(padrao, ua)
        if m:
            nav = f"{nome} {m.group(1)}"
            break
    so = "SO desconhecido"
    for nome, padrao in [("Android", r"Android"), ("iPhone/iPad", r"iPhone|iPad|iOS"), ("Windows", r"Windows"),
                         ("ChromeOS", r"CrOS"), ("macOS", r"Mac OS X|Macintosh"), ("Linux", r"Linux")]:
        if re.search(padrao, ua):
            so = nome
            break
    celular = " (celular)" if re.search(r"Mobi|Android|iPhone", ua) else ""
    return f"{nav} · {so}{celular}"


ROTULO_EVENTO = {
    "inicio": "Iniciou a avaliação",
    "retomada": "Reabriu a avaliação",
    "outro_dispositivo": "Abriu em outro navegador/dispositivo",
    "saiu_aba": "Saiu da aba (trocou de aba ou minimizou)",
    "saiu_janela": "Saiu da janela (clicou em outro programa/janela)",
    "voltou": "Voltou para a avaliação",
    "fechou": "Fechou ou recarregou a página",
    "envio": "Enviou a avaliação",
    "envio_automatico": "Envio automático (tempo esgotado)",
}


def monitoramento_out(t: Tentativa, incluir_eventos: bool = True) -> dict:
    fim = t.enviado_em or agora()
    out = {
        "iniciado_em": iso(t.iniciado_em), "enviado_em": iso(t.enviado_em),
        "tempo_gasto_seg": int((fim - t.iniciado_em).total_seconds()),
        "ip_inicio": t.ip_inicio, "navegador_inicio": descrever_navegador(t.navegador_inicio),
        "ip_envio": t.ip_envio, "navegador_envio": descrever_navegador(t.navegador_envio) if t.navegador_envio else None,
        "tela": t.tela,
        "qtd_acessos": t.qtd_acessos or 1, "qtd_saidas": t.qtd_saidas or 0, "tempo_fora_seg": t.tempo_fora_seg or 0,
        "qtd_fechamentos": t.qtd_fechamentos or 0, "outro_dispositivo": bool(t.outro_dispositivo),
    }
    out["alerta"] = bool(out["qtd_saidas"] or out["qtd_fechamentos"] or out["outro_dispositivo"])
    if incluir_eventos:
        out["eventos"] = [{"tipo": e.tipo, "rotulo": ROTULO_EVENTO.get(e.tipo, e.tipo), "em": iso(e.em),
                           "duracao_seg": e.duracao_seg, "ip": e.ip,
                           "navegador": descrever_navegador(e.navegador) if e.navegador else None,
                           "detalhe": e.detalhe} for e in t.eventos]
    return out
