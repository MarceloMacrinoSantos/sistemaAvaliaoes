"""Teste geral do sistema publicado: 66 alunos fazendo uma prova AO MESMO TEMPO.

Uso:  python teste_carga.py https://sistema-avaliacoes.onrender.com  LOGIN_PROFESSOR  SENHA

Segurança dos seus dados
- Cria uma escola, turma, disciplina e avaliação de TESTE, separadas de tudo o que é real.
- Os alunos de teste usam login "T" + RM (ex.: T2624993) e senha "teste123": as contas reais não são tocadas.
- No final apaga tudo o que criou (avaliação, turma, alunos de teste, disciplina e escola).
Só usa a biblioteca padrão do Python: não precisa instalar nada.
"""
import csv
import json
import random
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
NOME_TESTE = "TESTE DE CARGA (pode apagar)"
SENHA_ALUNO = "teste123"


class Cliente:
    def __init__(self, base):
        self.base, self.token = base.rstrip("/"), None

    def req(self, metodo, caminho, corpo=None, tempo=120):
        dados = json.dumps(corpo).encode() if corpo is not None else None
        r = urllib.request.Request(self.base + caminho, data=dados, method=metodo)
        r.add_header("Content-Type", "application/json")
        r.add_header("User-Agent", "teste-de-carga/1.0")
        if self.token:
            r.add_header("Authorization", "Bearer " + self.token)
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(r, timeout=tempo) as resp:
                txt = resp.read().decode() or "null"
                return resp.status, json.loads(txt), time.perf_counter() - t0
        except urllib.error.HTTPError as e:
            try:
                det = json.loads(e.read().decode()).get("detail")
            except Exception:
                det = e.reason
            return e.code, {"detail": det}, time.perf_counter() - t0
        except Exception as e:
            return 0, {"detail": str(e)}, time.perf_counter() - t0


def ok(st, js, oque):
    if st >= 400 or st == 0:
        sys.exit(f"\n✗ Falhou ao {oque}: {st} {js.get('detail') if isinstance(js, dict) else js}")
    return js


def questoes():
    q = []
    for i in range(1, 9):
        alts = [{"texto": f"Alternativa {l} da questão {i}", "correta": l == "B"} for l in "ABCDE"]
        q.append({"tipo": "objetiva", "enunciado": f"Questão de teste {i}: escolha a alternativa B.",
                  "peso": 0.25, "alternativas": alts, "explicacao": "Questão de teste."})
    for i in (9, 10):
        q.append({"tipo": "dissertativa", "enunciado": f"Questão dissertativa de teste {i}: explique o que é Git.",
                  "peso": 1.0, "gabarito_texto": "Git é um sistema de controle de versão distribuído.",
                  "palavras_chave": ["controle de versão|versionamento", "distribuído|local", "commit|histórico"],
                  "alternativas": []})
    return q


def main():
    if len(sys.argv) < 4:
        sys.exit("Uso: python teste_carga.py URL LOGIN_PROFESSOR SENHA")
    base, login, senha = sys.argv[1], sys.argv[2], sys.argv[3]
    alunos = [(l["RM"].strip(), l["Nome"].strip())
              for l in csv.DictReader(open(AQUI / "alunos_turma.csv", encoding="utf-8"), delimiter=";")]
    n = len(alunos)
    prof = Cliente(base)
    criado = {}

    print(f"\n=== Teste geral: {n} alunos ao mesmo tempo em {base} ===\n")
    print("1) Acordando o servidor (no plano gratuito pode levar até 1 minuto)...")
    t0 = time.perf_counter()
    for _ in range(12):
        st, js, _ = prof.req("GET", "/api/saude", tempo=90)
        if st == 200:
            break
        time.sleep(5)
    ok(st, js, "acessar o servidor")
    print(f"   ✓ no ar (versão {js.get('versao')}) em {time.perf_counter() - t0:.0f} s")

    try:
        print("2) Entrando como professor e preparando a prova de teste...")
        prof.token = ok(*prof.req("POST", "/api/auth/login", {"login": login, "senha": senha})[:2], "entrar como professor")["token"]
        criado["escola"] = ok(*prof.req("POST", "/api/escolas", {"nome": NOME_TESTE})[:2], "criar a escola de teste")["id"]
        criado["disciplina"] = ok(*prof.req("POST", "/api/disciplinas", {"nome": "Disciplina de teste", "escola_id": criado["escola"]})[:2], "criar a disciplina de teste")["id"]
        criado["turma"] = ok(*prof.req("POST", "/api/turmas", {"nome": "Turma de teste", "escola_id": criado["escola"]})[:2], "criar a turma de teste")["id"]
        lista = [{"rm": "T" + rm, "nome": f"[TESTE] {nome}", "senha": SENHA_ALUNO} for rm, nome in alunos]
        st, js, dt = prof.req("POST", "/api/alunos/importar-lista", {"turma_id": criado["turma"], "alunos": lista, "origem": "teste de carga"}, tempo=300)
        js = ok(st, js, "importar os alunos de teste")
        print(f"   ✓ {js['criados'] + js['matriculados']} alunos de teste importados em {dt:.1f} s")
        agora = datetime.now(timezone.utc)
        av = ok(*prof.req("POST", "/api/avaliacoes", {
            "titulo": "Prova de teste de carga", "tipo": "teste", "escola_id": criado["escola"], "turma_id": criado["turma"],
            "disciplina_id": criado["disciplina"], "inicio": (agora - timedelta(minutes=2)).isoformat(),
            "fim": (agora + timedelta(hours=1)).isoformat(), "duracao_min": 50, "nota_total": 4, "monitorar": True,
            "liberar_resultado": "apos_envio"})[:2], "criar a avaliação de teste")
        criado["avaliacao"] = av["id"]
        ok(*prof.req("POST", f"/api/avaliacoes/{av['id']}/questoes/lote", {"questoes": questoes()})[:2], "cadastrar as questões")
        ok(*prof.req("POST", f"/api/avaliacoes/{av['id']}/publicar")[:2], "publicar a prova")
        print("   ✓ prova de teste com 8 objetivas e 2 dissertativas publicada (4,0 pontos)")

        print(f"3) {n} alunos entram, respondem e enviam AO MESMO TEMPO...")
        tempos = {"login": [], "iniciar": [], "salvar": [], "eventos": [], "enviar": [], "resultado": []}
        falhas, notas = [], []
        trava = threading.Lock()
        largada = threading.Barrier(n)

        def aluno(item):
            rm, _ = item
            c = Cliente(base)

            def passo(nome, metodo, caminho, corpo=None):
                st, js, dt = c.req(metodo, caminho, corpo)
                with trava:
                    tempos[nome].append(dt)
                    if st >= 400 or st == 0:
                        falhas.append(f"{nome} (T{rm}): {st} {js.get('detail') if isinstance(js, dict) else ''}")
                return st, js

            largada.wait()  # todos fazem login no mesmo instante: o pior caso possível
            st, js = passo("login", "POST", "/api/auth/login", {"login": "T" + rm, "senha": SENHA_ALUNO})
            if st != 200:
                return
            c.token = js["token"]
            st, p = passo("iniciar", "POST", f"/api/aluno/avaliacoes/{criado['avaliacao']}/iniciar", {"tela": "1366x768"})
            if st != 200:
                return
            tid = p["tentativa_id"]
            for q in p["questoes"]:
                time.sleep(random.uniform(0.5, 2.5))  # tempo de leitura de cada questão
                if q["tipo"] == "objetiva":
                    corpo = {"questao_id": q["id"], "alternativa_id": random.choice(q["alternativas"])["id"]}
                else:
                    corpo = {"questao_id": q["id"], "texto": "Git é um sistema de controle de versão distribuído, "
                             "com commits locais e histórico."}
                passo("salvar", "PUT", f"/api/aluno/tentativas/{tid}/respostas", corpo)
            if random.random() < 0.3:
                passo("eventos", "POST", f"/api/aluno/tentativas/{tid}/eventos",
                      {"eventos": [{"tipo": "saiu_aba"}, {"tipo": "voltou", "duracao_seg": 3}]})
            st, _ = passo("enviar", "POST", f"/api/aluno/tentativas/{tid}/enviar")
            st, r = passo("resultado", "GET", f"/api/aluno/tentativas/{tid}/resultado")
            if st == 200 and isinstance(r, dict) and r.get("nota") is not None:
                with trava:
                    notas.append(r["nota"])

        t0 = time.perf_counter()
        with ThreadPoolExecutor(n) as ex:
            list(ex.map(aluno, alunos))
        total = time.perf_counter() - t0

        res = ok(*prof.req("GET", f"/api/avaliacoes/{criado['avaliacao']}/resultados")[:2], "ler os resultados")
        enviadas = sum(1 for a in res.get("alunos", []) if a.get("nota") is not None)

        print("\n=================== RESULTADO ===================")
        print(f" Alunos simultâneos:       {n}")
        print(f" Provas enviadas:          {enviadas} de {n}")
        print(f" Requisições com erro:     {len(falhas)}")
        print(f" Duração total do teste:   {total:.0f} s")
        print(" Tempo de resposta do servidor (mediana / pior):")
        for k, v in tempos.items():
            if v:
                print(f"   {k:<10} {statistics.median(v):5.2f} s / {max(v):5.2f} s   ({len(v)} vezes)")
        for f in falhas[:8]:
            print("   ✗", f)
        lento = tempos["login"] and max(tempos["login"]) > 15
        if not falhas and enviadas == n:
            print("\n ✓ APROVADO: todos entraram, responderam e enviaram sem erro.")
            if lento:
                print("   O login de todos ao mesmo tempo demorou; na sala, peça que entrem em duas levas.")
        elif enviadas >= n * 0.95:
            print("\n ◐ QUASE: houve erros pontuais. Mande este resultado para análise.")
        else:
            print("\n ✗ REPROVADO para esta quantidade de alunos simultâneos. Mande este resultado para análise.")
        print("=================================================\n")
    finally:
        print("4) Apagando tudo o que o teste criou...")
        limpo = True
        for oque, metodo, caminho in [("avaliacao", "DELETE", "/api/avaliacoes/{}"), ("turma", "DELETE", "/api/turmas/{}"),
                                      ("disciplina", "DELETE", "/api/disciplinas/{}"), ("escola", "DELETE", "/api/escolas/{}")]:
            if oque in criado:
                st, js, _ = prof.req(metodo, caminho.format(criado[oque]))
                if st >= 400 or st == 0:
                    limpo = False
                    print(f"   ! não consegui apagar {oque}: {js.get('detail') if isinstance(js, dict) else st}")
        print("   ✓ dados de teste apagados" if limpo else
              f"   Apague manualmente em Cadastros a escola \"{NOME_TESTE}\".")


if __name__ == "__main__":
    main()
