import os
import tempfile
from datetime import datetime, timedelta, timezone

os.environ.setdefault("DATABASE_URL", "sqlite:///" + os.path.join(tempfile.mkdtemp(), "t.db"))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402


def h(t):
    return {"Authorization": f"Bearer {t}"}


def login(c, u, s):
    r = c.post("/api/auth/login", json={"login": u, "senha": s})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def test_professor_so_ve_o_que_e_dele():
    with TestClient(app) as c:
        adm = login(c, "admin", "admin123")
        e1 = c.post("/api/escolas", json={"nome": "Iso Escola 1"}, headers=h(adm)).json()
        e2 = c.post("/api/escolas", json={"nome": "Iso Escola 2"}, headers=h(adm)).json()
        d1 = c.post("/api/disciplinas", json={"nome": "Iso Web", "escola_id": e1["id"]}, headers=h(adm)).json()
        d1b = c.post("/api/disciplinas", json={"nome": "Iso Redes", "escola_id": e1["id"]}, headers=h(adm)).json()
        d2 = c.post("/api/disciplinas", json={"nome": "Iso Mat", "escola_id": e2["id"]}, headers=h(adm)).json()
        p1 = c.post("/api/professores", json={"nome": "P1", "login": "iso_p1", "senha": "x1234"}, headers=h(adm)).json()
        p2 = c.post("/api/professores", json={"nome": "P2", "login": "iso_p2", "senha": "x1234"}, headers=h(adm)).json()
        # disciplina de outra escola não pode ser vinculada
        assert c.post(f"/api/professores/{p1['id']}/vinculos", headers=h(adm),
                      json={"escola_id": e1["id"], "disciplina_id": d2["id"]}).status_code == 400
        r = c.post(f"/api/professores/{p1['id']}/vinculos", headers=h(adm), json={"escola_id": e1["id"], "disciplina_id": d1["id"]}).json()
        assert r["vinculos"][0]["disciplina"] == "Iso Web"
        c.post(f"/api/professores/{p2['id']}/vinculos", headers=h(adm), json={"escola_id": e2["id"], "disciplina_id": d2["id"]})

        t1, t2 = login(c, "iso_p1", "x1234"), login(c, "iso_p2", "x1234")
        me = c.get("/api/auth/me", headers=h(t1)).json()
        assert me["vinculos"] == [{"escola": "Iso Escola 1", "disciplina": "Iso Web"}]
        # escolas e disciplinas só dos vínculos
        assert [e["nome"] for e in c.get("/api/escolas", headers=h(t1)).json()] == ["Iso Escola 1"]
        assert [d["nome"] for d in c.get("/api/disciplinas", headers=h(t1)).json()] == ["Iso Web"]
        # professor não altera escola do admin nem cria turma em escola alheia
        assert c.put(f"/api/escolas/{e1['id']}", json={"nome": "X"}, headers=h(t1)).status_code == 404
        assert c.post("/api/turmas", json={"nome": "T", "escola_id": e2["id"]}, headers=h(t1)).status_code == 403
        tu1 = c.post("/api/turmas", json={"nome": "Iso T1", "escola_id": e1["id"]}, headers=h(t1)).json()
        tu2 = c.post("/api/turmas", json={"nome": "Iso T2", "escola_id": e2["id"]}, headers=h(t2)).json()
        assert [t["nome"] for t in c.get("/api/turmas", headers=h(t1)).json()] == ["Iso T1"]
        assert c.get(f"/api/alunos?turma_id={tu2['id']}", headers=h(t1)).status_code == 404
        # o mesmo RM nas turmas dos dois professores: uma conta só, duas matrículas
        c.post("/api/alunos/importar-lista", headers=h(t1), json={"turma_id": tu1["id"], "alunos": [
            {"rm": "iso100", "nome": "Aluno Comum", "senha": "a1"}, {"rm": "iso101", "nome": "So do P1"}]})
        r = c.post("/api/alunos/importar-lista", headers=h(t2), json={"turma_id": tu2["id"], "alunos": [
            {"rm": "iso100", "nome": "Aluno Comum"}]}).json()
        assert r["criados"] == 0 and r["matriculados"] == 1
        assert c.post("/api/alunos/importar-lista", headers=h(t2), json={"turma_id": tu1["id"], "alunos": []}).status_code == 404
        assert [a["login"] for a in c.get("/api/alunos", headers=h(t2)).json()] == ["iso100"]
        assert len(c.get("/api/alunos", headers=h(t1)).json()) == 2
        so_p1 = next(a for a in c.get("/api/alunos", headers=h(t1)).json() if a["login"] == "iso101")
        assert c.put(f"/api/alunos/{so_p1['id']}", headers=h(t2), json={"nome": "x", "login": "iso101", "turma_id": tu2["id"]}).status_code == 404

        agora = datetime.now(timezone.utc)
        base = {"titulo": "Iso P", "inicio": agora.isoformat(), "fim": (agora + timedelta(hours=1)).isoformat(), "publicada": True}
        # disciplina sem vínculo é recusada
        assert c.post("/api/avaliacoes", headers=h(t1), json={**base, "escola_id": e1["id"], "turma_id": tu1["id"],
                                                               "disciplina_id": d1b["id"]}).status_code == 403
        av1 = c.post("/api/avaliacoes", headers=h(t1), json={**base, "escola_id": e1["id"], "turma_id": tu1["id"],
                                                              "disciplina_id": d1["id"]}).json()
        c.post(f"/api/avaliacoes/{av1['id']}/questoes", headers=h(t1), json={"tipo": "objetiva", "enunciado": "?",
               "alternativas": [{"texto": "a", "correta": True}, {"texto": "b"}]})
        av2 = c.post("/api/avaliacoes", headers=h(t2), json={**base, "titulo": "Iso P2", "escola_id": e2["id"],
                                                              "turma_id": tu2["id"], "disciplina_id": d2["id"]}).json()
        c.post(f"/api/avaliacoes/{av2['id']}/questoes", headers=h(t2), json={"tipo": "dissertativa", "enunciado": "Explique"})
        assert [a["titulo"] for a in c.get("/api/avaliacoes", headers=h(t1)).json()] == ["Iso P"]
        assert c.get(f"/api/avaliacoes/{av2['id']}", headers=h(t1)).status_code == 404
        assert c.get(f"/api/avaliacoes/{av2['id']}/resultados", headers=h(t1)).status_code == 404
        assert c.delete(f"/api/avaliacoes/{av2['id']}", headers=h(t1)).status_code == 404
        # o aluno comum vê as provas das duas turmas
        ta = login(c, "iso100", "a1")
        titulos = sorted(a["titulo"] for a in c.get("/api/aluno/avaliacoes", headers=h(ta)).json())
        assert titulos == ["Iso P", "Iso P2"]
        # P1 tira o aluno comum da turma dele: a conta continua existindo para o P2
        comum = next(a for a in c.get("/api/alunos", headers=h(t1)).json() if a["login"] == "iso100")
        assert c.delete(f"/api/alunos/{comum['id']}?turma_id={tu1['id']}", headers=h(t1)).status_code == 200
        assert [a["titulo"] for a in c.get("/api/aluno/avaliacoes", headers=h(ta)).json()] == ["Iso P2"]
        # admin continua vendo tudo
        assert {"Iso T1", "Iso T2"} <= {t["nome"] for t in c.get("/api/turmas", headers=h(adm)).json()}
        assert len(c.get("/api/professores", headers=h(adm)).json()) >= 3
        assert c.get("/api/professores", headers=h(t1)).status_code == 403


def test_migracao_banco_antigo_para_vinculos(tmp_path):
    """Banco da versão anterior (sem vínculos/matrículas) continua funcionando para cada professor."""
    import sqlite3
    arq = tmp_path / "v9.db"
    con = sqlite3.connect(arq)
    con.executescript("""
    CREATE TABLE escolas (id INTEGER PRIMARY KEY, nome TEXT);
    CREATE TABLE turmas (id INTEGER PRIMARY KEY, nome TEXT, ano_letivo TEXT, escola_id INT);
    CREATE TABLE disciplinas (id INTEGER PRIMARY KEY, nome TEXT);
    CREATE TABLE usuarios (id INTEGER PRIMARY KEY, nome TEXT, login TEXT UNIQUE, senha_hash TEXT, papel TEXT,
        turma_id INT, ativo BOOLEAN, lote_importacao TEXT);
    INSERT INTO escolas VALUES (1,'E1'); INSERT INTO turmas VALUES (1,'T1','2026',1);
    INSERT INTO disciplinas VALUES (1,'Web');
    INSERT INTO usuarios VALUES (1,'Prof','prof','x','professor',NULL,1,NULL);
    INSERT INTO usuarios VALUES (2,'Aluno','rm1','x','aluno',1,1,'lote1');
    """)
    con.commit(); con.close()
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import app.db as dbmod
    from app.models import Base, Avaliacao, Matricula, Turma, Vinculo, Disciplina, agora
    eng = create_engine(f"sqlite:///{arq}")
    orig = dbmod.engine
    dbmod.engine = eng
    try:
        Base.metadata.create_all(eng)
        dbmod.migrar_colunas()
        S = sessionmaker(bind=eng)
        with S() as db:
            db.add(Avaliacao(titulo="A", escola_id=1, turma_id=1, disciplina_id=1, professor_id=1, inicio=agora(), fim=agora()))
            db.commit()
            from app.migracao import migrar_dados
            migrar_dados(db)
            assert db.get(Turma, 1).professor_id == 1
            assert db.get(Disciplina, 1).escola_id == 1
            assert db.query(Vinculo).count() == 1
            m = db.query(Matricula).one()
            assert (m.turma_id, m.aluno_id, m.lote_importacao) == (1, 2, "lote1")
            migrar_dados(db)  # idempotente
            assert db.query(Matricula).count() == 1
    finally:
        dbmod.engine = orig


def test_professor_se_cadastra_e_monta_sua_area():
    with TestClient(app) as c:
        adm = login(c, "admin", "admin123")
        assert c.get("/api/auth/config").json() == {"cadastro_aberto": True, "exige_codigo": False}
        r = c.post("/api/auth/cadastro", json={"nome": "Prof Livre", "login": "livre1", "senha": "segredo1"})
        assert r.status_code == 200 and r.json()["usuario"]["papel"] == "professor"
        t = r.json()["token"]
        esc = c.post("/api/escolas", json={"nome": "Minha Escola Livre"}, headers=h(t)).json()
        assert esc["editavel"]
        assert c.post("/api/disciplinas", json={"nome": "Sem escola"}, headers=h(t)).status_code == 400
        dis = c.post("/api/disciplinas", json={"nome": "Lógica", "escola_id": esc["id"]}, headers=h(t)).json()
        tur = c.post("/api/turmas", json={"nome": "ADS 1", "escola_id": esc["id"]}, headers=h(t)).json()
        c.post("/api/alunos/importar-lista", headers=h(t), json={"turma_id": tur["id"], "alunos": [{"rm": "lv1", "nome": "Ana Livre"}]})
        agora = datetime.now(timezone.utc)
        av = c.post("/api/avaliacoes", headers=h(t), json={"titulo": "P1 livre", "escola_id": esc["id"], "turma_id": tur["id"],
                    "disciplina_id": dis["id"], "inicio": agora.isoformat(), "fim": (agora + timedelta(hours=1)).isoformat()})
        assert av.status_code == 200, av.text
        # outro professor autocadastrado não vê nada disso
        t2 = c.post("/api/auth/cadastro", json={"nome": "Outro Livre", "login": "livre2", "senha": "segredo2"}).json()["token"]
        assert c.get("/api/escolas", headers=h(t2)).json() == []
        assert c.get("/api/disciplinas", headers=h(t2)).json() == []
        assert c.get("/api/turmas", headers=h(t2)).json() == []
        assert c.get("/api/alunos", headers=h(t2)).json() == []
        assert c.put(f"/api/escolas/{esc['id']}", json={"nome": "Hack"}, headers=h(t2)).status_code == 404
        assert c.post("/api/disciplinas", json={"nome": "X", "escola_id": esc["id"]}, headers=h(t2)).status_code == 403
        # usar a disciplina de outro professor numa avaliação é recusado
        e2 = c.post("/api/escolas", json={"nome": "Escola do Outro"}, headers=h(t2)).json()
        tu2 = c.post("/api/turmas", json={"nome": "T", "escola_id": e2["id"]}, headers=h(t2)).json()
        r = c.post("/api/avaliacoes", headers=h(t2), json={"titulo": "x", "escola_id": e2["id"], "turma_id": tu2["id"],
                   "disciplina_id": dis["id"], "inicio": agora.isoformat(), "fim": (agora + timedelta(hours=1)).isoformat()})
        assert r.status_code == 403
        # o admin vê a escola do professor e sabe quem a criou
        esc_adm = next(e for e in c.get("/api/escolas", headers=h(adm)).json() if e["id"] == esc["id"])
        assert esc_adm["criado_por"] == "Prof Livre"
        # código de convite / cadastro fechado
        c.put("/api/config", headers=h(adm), json={"cadastro_aberto": True, "codigo_convite": "ABC123"})
        assert c.post("/api/auth/cadastro", json={"nome": "Sem Codigo", "login": "livre3", "senha": "segredo3"}).status_code == 403
        assert c.post("/api/auth/cadastro", json={"nome": "Com Codigo", "login": "livre3", "senha": "segredo3", "codigo": "ABC123"}).status_code == 200
        c.put("/api/config", headers=h(adm), json={"cadastro_aberto": False, "codigo_convite": ""})
        assert c.post("/api/auth/cadastro", json={"nome": "Fechado", "login": "livre4", "senha": "segredo4"}).status_code == 403
        c.put("/api/config", headers=h(adm), json={"cadastro_aberto": True, "codigo_convite": ""})
