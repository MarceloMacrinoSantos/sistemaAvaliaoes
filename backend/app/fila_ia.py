"""Fila de correção por IA, em segundo plano.

Quando o aluno envia a prova, as dissertativas entram na fila (ia_status = "pendente") e a nota por
palavras-chave já vale. Esta fila corrige uma de cada vez, respeitando o limite de cada IA:
- deu certo  -> guarda a nota da IA; no modo "automatica" ela passa a valer (palavras-chave ficam como reserva);
- falhou     -> tenta de novo mais tarde (até 3 vezes); depois marca "falhou" e a nota por palavras-chave continua.
A fila guarda tudo no banco: se o servidor reiniciar, continua de onde parou.
"""
import logging
import os
import threading
from datetime import timedelta

from sqlalchemy import or_, select, update

from . import ia
from .db import SessionLocal
from .models import Resposta, agora

log = logging.getLogger("fila_ia")
MAX_TENTATIVAS = 3
_acordar = threading.Event()
_thread: threading.Thread | None = None


def situacao_por_fracao(pontos: float, maximo: float) -> str:
    if maximo and pontos >= maximo - 1e-9:
        return "certa"
    if pontos <= 0:
        return "errada"
    return "parcial"


def texto_feedback_ia(res: dict) -> str:
    partes = []
    if res.get("feedback"):
        partes.append(res["feedback"])
    if res.get("atendidos"):
        partes.append("Pontos atendidos: " + "; ".join(res["atendidos"]) + ".")
    if res.get("faltaram"):
        partes.append("Faltou ou precisa melhorar: " + "; ".join(res["faltaram"]) + ".")
    return " ".join(partes)


def aplicar(r: Resposta) -> None:
    """No modo automático, a nota da IA passa a ser a nota automática da questão."""
    av = r.tentativa.avaliacao
    if av.correcao_ia == "automatica" and r.ia_status == "ok" and r.ia_pontos is not None:
        r.pontos_auto = r.ia_pontos
        r.situacao = situacao_por_fracao(r.ia_pontos, r.questao.pontos)
        r.feedback_auto = "Correção por IA: " + (r.ia_feedback or "")
    else:  # sugestão, desligada ou IA sem resultado: vale a correção por palavras-chave / resposta esperada
        from .correcao import corrigir_dissertativa
        r.pontos_auto, r.situacao, r.feedback_auto = corrigir_dissertativa(r.questao, r.texto)


def processar_uma(rid: int) -> str:
    """Corrige uma resposta já marcada como 'processando'. Devolve o novo status."""
    from .correcao import recalcular_nota
    with SessionLocal() as db:
        r = db.get(Resposta, rid)
        if not r:
            return "sumiu"
        q = r.questao
        try:
            res = ia.corrigir(q.enunciado, q.gabarito_texto, q.explicacao, q.palavras_chave, q.pontos, r.texto or "")
            r.ia_status, r.ia_pontos, r.ia_provedor, r.ia_erro = "ok", res["pontos"], res["provedor"][:40], None
            r.ia_feedback = texto_feedback_ia(res)
        except ia.ErroIA as e:
            r.ia_tentativas = (r.ia_tentativas or 0) + 1
            r.ia_erro = str(e)[:300]
            if e.permanente or r.ia_tentativas >= MAX_TENTATIVAS:
                r.ia_status = "falhou"       # vale a correção por palavras-chave
            else:
                r.ia_status = "pendente"     # tenta de novo daqui a pouco
                r.ia_em = agora() + timedelta(seconds=e.espera or 60)
        except Exception as e:  # nunca deixa uma falha inesperada derrubar a fila
            log.exception("falha inesperada na correção por IA")
            r.ia_status, r.ia_erro = "falhou", f"erro interno: {e}"[:300]
        aplicar(r)
        recalcular_nota(r.tentativa)
        db.commit()
        return r.ia_status


def _proxima(db) -> int | None:
    """Reserva a próxima resposta pendente (seguro com mais de um processo do servidor)."""
    agora_ = agora()
    # reservas esquecidas (servidor reiniciou no meio) voltam para a fila
    db.execute(update(Resposta).where(Resposta.ia_status == "processando",
                                      Resposta.ia_em < agora_ - timedelta(minutes=10)).values(ia_status="pendente"))
    db.commit()
    rid = db.scalar(select(Resposta.id).where(Resposta.ia_status == "pendente",
                                              or_(Resposta.ia_em.is_(None), Resposta.ia_em <= agora_))
                    .order_by(Resposta.id).limit(1))
    if rid is None:
        return None
    feito = db.execute(update(Resposta).where(Resposta.id == rid, Resposta.ia_status == "pendente")
                       .values(ia_status="processando", ia_em=agora_))
    db.commit()
    return rid if feito.rowcount else None


def _laco():
    while True:
        try:
            if ia.configurada():
                with SessionLocal() as db:
                    rid = _proxima(db)
                if rid is not None:
                    processar_uma(rid)
                    continue
        except Exception:
            log.exception("erro na fila de IA")
        _acordar.wait(15)
        _acordar.clear()


def iniciar():
    global _thread
    if os.getenv("IA_FILA", "1") == "0" or (_thread and _thread.is_alive()):
        return
    _thread = threading.Thread(target=_laco, name="fila-ia", daemon=True)
    _thread.start()


def avisar():
    """Chamada quando entram itens novos na fila: corrige sem esperar o próximo ciclo."""
    _acordar.set()


def pendentes(db, avaliacao_id: int | None = None) -> dict:
    from sqlalchemy import func
    from .models import Tentativa
    q = select(Resposta.ia_status, func.count()).where(Resposta.ia_status.is_not(None))
    if avaliacao_id:
        q = q.join(Tentativa, Tentativa.id == Resposta.tentativa_id).where(Tentativa.avaliacao_id == avaliacao_id)
    cont = dict(db.execute(q.group_by(Resposta.ia_status)).all())
    return {"pendentes": cont.get("pendente", 0) + cont.get("processando", 0), "ok": cont.get("ok", 0),
            "falhou": cont.get("falhou", 0)}


# usada pelos testes e pelo "testar agora"
def processar_tudo(limite: int = 1000) -> int:
    n = 0
    while n < limite:
        with SessionLocal() as db:
            rid = _proxima(db)
        if rid is None:
            return n
        processar_uma(rid)
        n += 1
    return n

