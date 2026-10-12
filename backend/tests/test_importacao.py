import io
import os
import tempfile
from datetime import datetime, timedelta, timezone

os.environ.setdefault("DATABASE_URL", "sqlite:///" + os.path.join(tempfile.mkdtemp(), "t.db"))

import openpyxl  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402


def h(t):
    return {"Authorization": f"Bearer {t}"}


def test_importar_e_excluir_alunos():
    with TestClient(app) as c:
        adm = c.post("/api/auth/login", json={"login": "admin", "senha": "admin123"}).json()["token"]
        e = c.post("/api/escolas", json={"nome": "Imp"}, headers=h(adm)).json()
        t = c.post("/api/turmas", json={"nome": "7B", "escola_id": e["id"]}, headers=h(adm)).json()
        # planilha fora de ordem, com coluna extra e "Nº" da chamada
        wb = openpyxl.Workbook(); ws = wb.active
        ws.append(["Nº", "Nome completo", "Turma", "RA", "Senha"])
        ws.append([1, "Lara Campos", "7B", 70001.0, "l1"])
        ws.append([2, "Mateus Rocha", "7B", 70002, None])
        b = io.BytesIO(); wb.save(b)
        r = c.post("/api/alunos/ler-arquivo", headers=h(adm), files={"arquivo": ("lista.xlsx", b.getvalue())}).json()
        s = r["sugestao"]
        assert (s["rm"], s["nome"], s["senha"], s["tem_cabecalho"]) == (3, 1, 4, True)
        linhas = r["linhas"][1:]
        alunos = [{"rm": l[3], "nome": l[1], "senha": l[4]} for l in linhas]
        imp = c.post("/api/alunos/importar-lista", headers=h(adm),
                     json={"turma_id": t["id"], "alunos": alunos, "origem": "lista.xlsx"}).json()
        assert imp["criados"] == 2 and imp["lote"]
        # senha vazia = RM
        assert c.post("/api/auth/login", json={"login": "70002", "senha": "70002"}).status_code == 200
        assert c.post("/api/auth/login", json={"login": "70001", "senha": "l1"}).status_code == 200
        # json sem cabeçalho e texto colado
        r = c.post("/api/alunos/ler-arquivo", headers=h(adm),
                   files={"arquivo": ("a.json", b'[["70003","Nina Prado"],["70004","Otto Reis"]]')}).json()
        assert r["sugestao"]["rm"] == 0 and r["sugestao"]["nome"] == 1
        r = c.post("/api/alunos/ler-arquivo", headers=h(adm), data={"texto": "Pedro Luz;70005;p5\nRita Mar;70006;r6"}).json()
        assert r["sugestao"]["nome"] == 0 and r["sugestao"]["rm"] == 1 and r["sugestao"]["senha"] == 2
        imp2 = c.post("/api/alunos/importar-lista", headers=h(adm), json={"turma_id": t["id"], "alunos": [
            {"rm": "70005", "nome": "Pedro Luz"}, {"rm": "70006", "nome": "Rita Mar"}, {"rm": "70001", "nome": "Dup"}]}).json()
        assert imp2["criados"] == 2 and len(imp2["erros"]) == 1
        lotes = c.get(f"/api/alunos/lotes?turma_id={t['id']}", headers=h(adm)).json()
        assert len(lotes) == 2
        # desfaz a segunda importação
        d = c.post("/api/alunos/excluir-lote", headers=h(adm), json={"turma_id": t["id"], "modo": "lote", "lote": imp2["lote"]}).json()
        assert d["excluidos"] == 2
        # excluir todos exige digitar o nome da turma
        assert c.post("/api/alunos/excluir-lote", headers=h(adm), json={"turma_id": t["id"], "modo": "todos", "confirmacao": "x"}).status_code == 400
        d = c.post("/api/alunos/excluir-lote", headers=h(adm), json={"turma_id": t["id"], "modo": "todos", "confirmacao": "7b"}).json()
        assert d["excluidos"] == 2
        assert c.get(f"/api/alunos?turma_id={t['id']}", headers=h(adm)).json() == []


def test_importar_prova_docx():
    import docx
    with TestClient(app) as c:
        adm = c.post("/api/auth/login", json={"login": "admin", "senha": "admin123"}).json()["token"]
        e = c.post("/api/escolas", json={"nome": "Imp2"}, headers=h(adm)).json()
        t = c.post("/api/turmas", json={"nome": "8C", "escola_id": e["id"]}, headers=h(adm)).json()
        dsc = c.post("/api/disciplinas", json={"nome": "Geo"}, headers=h(adm)).json()
        agora = datetime.now(timezone.utc)
        av = c.post("/api/avaliacoes", headers=h(adm), json={
            "titulo": "Imp", "escola_id": e["id"], "turma_id": t["id"], "disciplina_id": dsc["id"],
            "inicio": agora.isoformat(), "fim": (agora + timedelta(hours=1)).isoformat()}).json()
        modelo = c.get("/api/modelos/modelo-avaliacao.docx")
        assert modelo.status_code == 200
        r = c.post("/api/avaliacoes/importar/ler", headers=h(adm),
                   files={"arquivo": ("modelo.docx", modelo.content)}).json()
        assert len(r["questoes"]) == 5 and not r["avisos"]
        qs = r["questoes"]
        corpo = [{"tipo": q["tipo"], "enunciado": q["enunciado"], "peso": q["peso"],
                  "gabarito_texto": q.get("gabarito_texto"), "palavras_chave": q.get("palavras_chave") or [],
                  "alternativas": q["alternativas"], "explicacao": q["explicacao"]} for q in qs]
        res = c.post(f"/api/avaliacoes/{av['id']}/questoes/lote", headers=h(adm), json={"questoes": corpo}).json()
        assert res["qtd_questoes"] == 5 and res["pontuacao_total"] == 10
        pts = [q["pontos"] for q in res["questoes"]]
        assert pts[3] > pts[0]  # dissertativa (peso 2) vale mais
        # texto colado sem gabarito gera aviso
        r = c.post("/api/avaliacoes/importar/ler", headers=h(adm), data={"texto": "1) Pergunta?\na) x\nb) y"}).json()
        assert r["avisos"]
        # pdf escaneado / vazio
        assert c.post("/api/avaliacoes/importar/ler", headers=h(adm), data={"texto": "sem questões aqui"}).status_code == 400
