"""Correção automática das avaliações.

- Objetivas: compara a alternativa marcada com a correta.
- Dissertativas: procura as palavras-chave cadastradas pelo professor na resposta
  do aluno (sem diferenciar maiúsculas/acentos e tolerando pequenos erros de
  digitação). Cada palavra-chave pode ter sinônimos separados por "|".
  Sem palavras-chave, compara o vocabulário da resposta com o gabarito.
  A nota das dissertativas é uma sugestão e pode ser revisada pelo professor.
"""
import re
import unicodedata
from difflib import SequenceMatcher

from .models import Alternativa, Evento, Questao, Resposta, Tentativa, agora

STOPWORDS = set("""a o as os um uma uns umas de do da dos das em no na nos nas por pelo pela pelos pelas
para pra com sem sob sobre e ou mas que se ao aos à às é são foi ser era seu sua seus suas
isso isto este esta esse essa ele ela eles elas lhe muito mais menos como quando onde já não sim
também tem têm ter há entre até após""".split())


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()


def _tokens(texto: str) -> list[str]:
    return [t for t in normalizar(texto).split() if t not in STOPWORDS]


def _parecido(a: str, b: str) -> bool:
    if a == b:
        return True
    if min(len(a), len(b)) < 5:
        return False
    return SequenceMatcher(None, a, b).ratio() >= 0.85


def _contem_termo(resposta_norm: str, tokens_resp: list[str], termo: str) -> bool:
    termo_norm = normalizar(termo)
    if not termo_norm:
        return False
    if f" {termo_norm} " in f" {resposta_norm} ":
        return True
    partes = termo_norm.split()
    if len(partes) == 1:
        return any(_parecido(partes[0], t) for t in tokens_resp)
    # expressão com várias palavras: todas precisam aparecer (com tolerância)
    return all(any(_parecido(p, t) for t in tokens_resp) for p in partes if p not in STOPWORDS)


def corrigir_dissertativa(q: Questao, texto: str | None) -> tuple[float, str, str]:
    if not texto or not texto.strip():
        return 0.0, "em_branco", "Questão não respondida."

    resp_norm = normalizar(texto)
    tokens_resp = resp_norm.split()
    chaves = [c for c in (q.palavras_chave or []) if str(c).strip()]

    if chaves:
        encontrados, faltando = [], []
        for chave in chaves:
            opcoes = [o.strip() for o in str(chave).split("|") if o.strip()]
            (encontrados if any(_contem_termo(resp_norm, tokens_resp, o) for o in opcoes) else faltando
             ).append(opcoes[0])
        fracao = len(encontrados) / len(chaves)
        partes = []
        if encontrados:
            partes.append("Pontos abordados: " + ", ".join(encontrados) + ".")
        if faltando:
            partes.append("Faltou abordar: " + ", ".join(faltando) + ".")
        feedback = " ".join(partes)
    elif q.gabarito_texto:
        esperados = set(_tokens(q.gabarito_texto))
        if not esperados:
            return 0.0, "pendente", "Aguardando correção do professor."
        presentes = {e for e in esperados if any(_parecido(e, t) for t in tokens_resp)}
        # 70% do vocabulário do gabarito já vale nota cheia
        fracao = min(1.0, (len(presentes) / len(esperados)) / 0.7)
        feedback = f"Sua resposta cobre cerca de {round(100 * fracao)}% dos conceitos esperados."
    else:
        return 0.0, "pendente", "Aguardando correção do professor."

    pontos = round(q.pontos * fracao, 2)
    if fracao >= 0.999:
        situacao = "certa"
    elif fracao <= 0:
        situacao = "errada"
    else:
        situacao = "parcial"
    return pontos, situacao, feedback


def corrigir_objetiva(q: Questao, alternativa_id: int | None) -> tuple[float, str, str]:
    corretas = [a for a in q.alternativas if a.correta]
    correta: Alternativa | None = corretas[0] if corretas else None
    if alternativa_id is None:
        return 0.0, "em_branco", "Questão não respondida."
    if correta and alternativa_id == correta.id:
        return float(q.pontos), "certa", "Resposta correta!"
    return 0.0, "errada", "Resposta incorreta."


def corrigir_tentativa(t: Tentativa, automatico: bool = False) -> None:
    """Finaliza (se necessário) e corrige toda a tentativa."""
    if t.enviado_em is None:
        t.enviado_em = min(agora(), t.prazo)
        t.envio_automatico = automatico
        if automatico:
            t.eventos.append(Evento(tipo="envio_automatico", em=t.enviado_em, detalhe="encerrado pelo servidor"))

    respostas = {r.questao_id: r for r in t.respostas}
    total, maximo = 0.0, 0.0
    for q in t.avaliacao.questoes:
        r = respostas.get(q.id)
        if r is None:
            r = Resposta(tentativa=t, questao_id=q.id)
            t.respostas.append(r)
        if q.tipo == "objetiva":
            r.pontos_auto, r.situacao, r.feedback_auto = corrigir_objetiva(q, r.alternativa_id)
        else:
            r.pontos_auto, r.situacao, r.feedback_auto = corrigir_dissertativa(q, r.texto)
            r.pontos_chaves, r.feedback_chaves = r.pontos_auto, r.feedback_auto
            _preparar_ia(t, q, r)
        total += r.pontos_finais
        maximo += q.pontos
    t.nota = round(total, 2)
    t.nota_max = round(maximo, 2)


def _preparar_ia(t: Tentativa, q: Questao, r: Resposta) -> None:
    """Põe a dissertativa na fila da IA (a nota por palavras-chave já vale enquanto isso)."""
    modo = getattr(t.avaliacao, "correcao_ia", None) or "desligada"
    if modo == "desligada" or r.ia_status in ("ok", "pendente", "processando"):
        if r.ia_status == "ok":
            from .fila_ia import aplicar
            aplicar(r)  # mantém a nota da IA (modo automático) se a correção for refeita
        return
    if not (r.texto or "").strip():
        return  # em branco: vale 0, não precisa de IA
    from . import ia
    if not ia.configurada():
        r.ia_status, r.ia_erro = "falhou", "nenhuma chave de IA configurada no servidor"
        return
    r.ia_status, r.ia_tentativas, r.ia_erro, r.ia_em = "pendente", 0, None, None


def recalcular_nota(t: Tentativa) -> None:
    t.nota = round(sum(r.pontos_finais for r in t.respostas), 2)
