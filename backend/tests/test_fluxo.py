import os, tempfile
from datetime import datetime, timedelta, timezone

os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "t.db")

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.correcao import corrigir_dissertativa  # noqa: E402
from app.models import Questao  # noqa: E402


def h(tok):
    return {"Authorization": f"Bearer {tok}"}


def login(c, u, s):
    r = c.post("/api/auth/login", json={"login": u, "senha": s})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def test_correcao_dissertativa():
    q = Questao(tipo="dissertativa", pontos=2, enunciado="x",
                palavras_chave=["luz|solar", "gás carbônico|CO2", "água", "oxigenio"])
    p, sit, fb = corrigir_dissertativa(q, "A planta usa LUZ do sol, agua e co2 para fazer glicose")
    assert p == 1.5 and sit == "parcial" and "oxigenio" in fb
    p, sit, _ = corrigir_dissertativa(q, "luz, gás carbonico, água e oxigênio")
    assert p == 2 and sit == "certa"
    p, sit, _ = corrigir_dissertativa(q, "fotosintese com luz solar, agua, CO2 e oxigenio")  # erros de digitação
    assert sit == "certa"
    assert corrigir_dissertativa(q, "")[1] == "em_branco"


def test_fluxo_completo():
    with TestClient(app) as c:
        adm = login(c, "admin", "admin123")
        e = c.post("/api/escolas", json={"nome": "Escola X"}, headers=h(adm)).json()
        t = c.post("/api/turmas", json={"nome": "8A", "escola_id": e["id"]}, headers=h(adm)).json()
        d = c.post("/api/disciplinas", json={"nome": "Mat"}, headers=h(adm)).json()
        r = c.post("/api/alunos/importar-lista", headers=h(adm), json={"turma_id": t["id"], "senha_padrao": "1234", "alunos": [
            {"rm": "a1", "nome": "Ana", "senha": "123"}, {"rm": "a2", "nome": "Bia"}, {"rm": "a1", "nome": "Caio"}]}).json()
        assert r["criados"] == 2 and len(r["erros"]) == 1

        agora = datetime.now(timezone.utc)
        av = c.post("/api/avaliacoes", headers=h(adm), json={
            "titulo": "P1", "escola_id": e["id"], "turma_id": t["id"], "disciplina_id": d["id"],
            "inicio": (agora - timedelta(minutes=1)).isoformat(), "fim": (agora + timedelta(hours=1)).isoformat(),
            "duracao_min": 30, "publicada": True, "liberar_resultado": "apos_fim"}).json()
        # validação de gabarito
        bad = c.post(f"/api/avaliacoes/{av['id']}/questoes", headers=h(adm), json={
            "tipo": "objetiva", "enunciado": "?", "alternativas": [{"texto": "a"}, {"texto": "b"}]})
        assert bad.status_code == 422 and "correta" in bad.json()["detail"]
        qids = []
        for i in range(6):
            q = c.post(f"/api/avaliacoes/{av['id']}/questoes", headers=h(adm), json={
                "tipo": "objetiva", "enunciado": f"Q{i}",
                "alternativas": [{"texto": "certa", "correta": True}, {"texto": "errada"}, {"texto": "outra"}]}).json()
            qids.append(q["id"])
        qd = c.post(f"/api/avaliacoes/{av['id']}/questoes", headers=h(adm), json={
            "tipo": "dissertativa", "enunciado": "Explique",
            "gabarito_texto": "x", "palavras_chave": ["soma", "parcela"]}).json()

        # nota total 10 distribuída: 6 objetivas peso 1 + dissertativa peso 2 (padrão) = soma 8
        det_av = c.get(f"/api/avaliacoes/{av['id']}", headers=h(adm)).json()
        pts = {q["tipo"]: q["pontos"] for q in det_av["questoes"]}
        assert pts == {"objetiva": 1.25, "dissertativa": 2.5} and det_av["pontuacao_total"] == 10
        # professor altera o peso da dissertativa para 4 -> soma 10: objetiva 1, dissertativa 4
        r = c.put(f"/api/avaliacoes/{av['id']}/pesos", headers=h(adm), json={"pesos": {str(qd["id"]): 4}}).json()
        assert {q["tipo"]: q["pontos"] for q in r["questoes"]} == {"objetiva": 1.0, "dissertativa": 4.0}
        r = c.post(f"/api/avaliacoes/{av['id']}/pesos-padrao", headers=h(adm)).json()
        assert r["pontuacao_total"] == 10

        a1 = login(c, "a1", "123")
        lst = c.get("/api/aluno/avaliacoes", headers=h(a1)).json()
        assert lst[0]["situacao"] == "disponivel"
        ua1 = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0) Chrome/128.0 Safari/537.36"}
        prova = c.post(f"/api/aluno/avaliacoes/{av['id']}/iniciar", headers={**h(a1), **ua1}, json={"tela": "1366x768"}).json()
        assert prova["monitorar"] is True
        assert "correta" not in str(prova["questoes"])  # gabarito não vaza
        # retomar devolve a mesma ordem
        prova2 = c.post(f"/api/aluno/avaliacoes/{av['id']}/iniciar", headers={**h(a1), **ua1}).json()
        assert [q["id"] for q in prova["questoes"]] == [q["id"] for q in prova2["questoes"]]
        tid = prova["tentativa_id"]
        # monitoramento: saiu da aba 2x, fechou a página 1x, reabriu em outro navegador
        m = c.post(f"/api/aluno/tentativas/{tid}/eventos", headers=h(a1), json={"eventos": [
            {"tipo": "saiu_aba"}, {"tipo": "voltou", "duracao_seg": 12},
            {"tipo": "saiu_janela"}, {"tipo": "voltou", "duracao_seg": 5}, {"tipo": "fechou"}]}).json()
        assert m == {"qtd_saidas": 2, "tempo_fora_seg": 17, "qtd_fechamentos": 1}
        p3 = c.post(f"/api/aluno/avaliacoes/{av['id']}/iniciar",
                    headers={**h(a1), "User-Agent": "Mozilla/5.0 (Linux; Android 14) Firefox/130.0"}).json()
        assert p3["monitoramento"]["outro_dispositivo"] is True and p3["monitoramento"]["qtd_acessos"] == 3
        for q in prova["questoes"]:
            if q["tipo"] == "objetiva":
                alt = next(a for a in q["alternativas"] if a["texto"] == ("certa" if q["enunciado"] != "Q0" else "errada"))
                assert c.put(f"/api/aluno/tentativas/{tid}/respostas", headers=h(a1),
                             json={"questao_id": q["id"], "alternativa_id": alt["id"]}).status_code == 200
            else:
                c.put(f"/api/aluno/tentativas/{tid}/respostas", headers=h(a1),
                      json={"questao_id": q["id"], "texto": "É a soma de cada parcela"})
        assert c.post(f"/api/aluno/tentativas/{tid}/enviar", headers=h(a1)).json()["resultado_disponivel"] is False
        assert c.get(f"/api/aluno/tentativas/{tid}/resultado", headers=h(a1)).status_code == 403
        assert c.post(f"/api/aluno/avaliacoes/{av['id']}/iniciar", headers=h(a1)).status_code == 409

        # não pode alterar questões depois de iniciada
        assert c.delete(f"/api/questoes/{qids[0]}", headers=h(adm)).status_code == 400

        # a2 inicia mas não envia; professor encerra -> envio automático
        a2 = login(c, "a2", "1234")
        c.post(f"/api/aluno/avaliacoes/{av['id']}/iniciar", headers=h(a2))
        resumo = c.post(f"/api/avaliacoes/{av['id']}/encerrar", headers=h(adm)).json()
        assert resumo["enviadas"] == 2

        res = c.get(f"/api/aluno/tentativas/{tid}/resultado", headers=h(a1)).json()
        assert res["nota"] == 8.75 and res["nota_max"] == 10.0 and res["acertos"] == 6
        mon = res["monitoramento"]
        assert mon["qtd_saidas"] == 2 and mon["outro_dispositivo"] and mon["navegador_inicio"] == "Chrome 128 · Windows"
        tipos = [e["tipo"] for e in mon["eventos"]]
        assert tipos[0] == "inicio" and "outro_dispositivo" in tipos and tipos[-1] == "envio"
        errada = next(q for q in res["questoes"] if q["enunciado"] == "Q0")
        assert errada["situacao"] == "errada" and any(a["correta"] and not a["marcada"] for a in errada["alternativas"])

        # revisão do professor
        det = c.get(f"/api/tentativas/{tid}", headers=h(adm)).json()
        rid = next(q["resposta_id"] for q in det["questoes"] if q["tipo"] == "dissertativa")
        assert c.put(f"/api/respostas/{rid}/revisar", headers=h(adm), json={"pontos": 1, "comentario": "Incompleta"}).json()["nota"] == 7.25
        rs = c.get(f"/api/avaliacoes/{av['id']}/resultados", headers=h(adm)).json()
        assert rs["resumo"]["enviadas"] == 2 and rs["questoes"][0]["respostas"] == 2
        linha = next(l for l in rs["alunos"] if l["login"] == "a1")
        assert linha["monitoramento"]["qtd_fechamentos"] == 1 and linha["monitoramento"]["alerta"]
        auto = next(l for l in rs["alunos"] if l["login"] == "a2")
        assert auto["envio_automatico"]
        csv_ = c.get(f"/api/avaliacoes/{av['id']}/resultados.csv", headers=h(adm)).text
        assert "Saídas da aba/janela" in csv_ and "Chrome 128" in csv_
        assert c.get(f"/api/avaliacoes/{av['id']}/resultados.csv", headers=h(adm)).status_code == 200
        # aluno não acessa área do professor
        assert c.get("/api/escolas", headers=h(a1)).status_code == 403


def test_migracao_banco_antigo(tmp_path):
    """Um banco criado pela versão anterior ganha as colunas novas sem perder dados."""
    import sqlite3
    from sqlalchemy import create_engine, inspect
    import app.db as dbmod
    arq = tmp_path / "antigo.db"
    con = sqlite3.connect(arq)
    con.execute("CREATE TABLE questoes (id INTEGER PRIMARY KEY, avaliacao_id INT, tipo TEXT, enunciado TEXT, pontos FLOAT, ordem INT)")
    con.execute("INSERT INTO questoes VALUES (1, 1, 'objetiva', 'x', 2.0, 0)")
    con.commit(); con.close()
    original = dbmod.engine
    dbmod.engine = create_engine(f"sqlite:///{arq}")
    try:
        dbmod.migrar_colunas()
        cols = {c["name"] for c in inspect(dbmod.engine).get_columns("questoes")}
        assert "peso" in cols
        with dbmod.engine.connect() as conn:
            from sqlalchemy import text
            assert conn.execute(text("SELECT peso, pontos FROM questoes")).one() == (1.0, 2.0)
    finally:
        dbmod.engine = original
