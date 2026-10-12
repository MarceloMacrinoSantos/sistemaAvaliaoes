import os
import random
import tempfile
from datetime import datetime, timedelta, timezone

os.environ.setdefault("DATABASE_URL", "sqlite:///" + os.path.join(tempfile.mkdtemp(), "t.db"))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402


def h(t):
    return {"Authorization": f"Bearer {t}"}


def test_painel_de_analises():
    random.seed(3)
    with TestClient(app) as c:
        t = c.post("/api/auth/cadastro", json={"nome": "Prof Analise", "login": "an_prof", "senha": "segredo1"}).json()["token"]
        e = c.post("/api/escolas", json={"nome": "An Escola"}, headers=h(t)).json()
        d = c.post("/api/disciplinas", json={"nome": "Web", "escola_id": e["id"]}, headers=h(t)).json()
        tu = c.post("/api/turmas", json={"nome": "An T1", "escola_id": e["id"]}, headers=h(t)).json()
        c.post("/api/alunos/importar-lista", headers=h(t), json={"turma_id": tu["id"], "alunos": [
            {"rm": f"an{i}", "nome": f"Aluno {i}"} for i in range(6)]})
        agora = datetime.now(timezone.utc)
        for k in range(2):
            av = c.post("/api/avaliacoes", headers=h(t), json={
                "titulo": f"P{k+1}", "escola_id": e["id"], "turma_id": tu["id"], "disciplina_id": d["id"], "publicada": True,
                "inicio": (agora - timedelta(hours=2 - k)).isoformat(), "fim": (agora + timedelta(hours=1)).isoformat()}).json()
            for j in range(4):
                c.post(f"/api/avaliacoes/{av['id']}/questoes", headers=h(t), json={"tipo": "objetiva", "enunciado": f"Q{j}",
                       "alternativas": [{"texto": "certa", "correta": True}, {"texto": "errada"}]})
            for i in range(5):  # aluno 5 não faz nenhuma
                ta = c.post("/api/auth/login", json={"login": f"an{i}", "senha": f"an{i}"}).json()["token"]
                p = c.post(f"/api/aluno/avaliacoes/{av['id']}/iniciar", headers=h(ta), json={}).json()
                for q in p["questoes"]:
                    acerta = random.random() < (0.9 - 0.15 * i)
                    alt = next(a for a in q["alternativas"] if (a["texto"] == "certa") == acerta)
                    c.put(f"/api/aluno/tentativas/{p['tentativa_id']}/respostas", headers=h(ta),
                          json={"questao_id": q["id"], "alternativa_id": alt["id"]})
                c.post(f"/api/aluno/tentativas/{p['tentativa_id']}/enviar", headers=h(ta))
            c.post(f"/api/avaliacoes/{av['id']}/encerrar", headers=h(t))
        r = c.get("/api/analises", headers=h(t)).json()
        assert r["resumo"]["avaliacoes"] == 2 and r["resumo"]["provas_corrigidas"] == 10
        assert r["resumo"]["participacao"] == round(100 * 10 / 12)
        assert sum(f["qtd"] for f in r["distribuicao"]) == 10
        assert len(r["questoes_dificeis"]) == 8 and "tipos" in r
        faltou = next(a for a in r["alunos"] if a["login"] == "an5")
        assert faltou["faltas"] == 2 and faltou["atencao"]
        # outro professor não vê nada
        t2 = c.post("/api/auth/cadastro", json={"nome": "Outro An", "login": "an_prof2", "senha": "segredo2"}).json()["token"]
        assert c.get("/api/analises", headers=h(t2)).json()["resumo"]["avaliacoes"] == 0
        # filtro por turma inexistente para ele
        assert c.get(f"/api/analises?turma_id={tu['id']}", headers=h(t2)).json()["resumo"]["avaliacoes"] == 0
