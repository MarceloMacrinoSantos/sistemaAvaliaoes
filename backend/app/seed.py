"""Dados de demonstração: python -m app.seed"""
from datetime import timedelta

from sqlalchemy import select

from .auth import hash_senha
from .db import Base, SessionLocal, engine
from .servicos import redistribuir_pontos
from .models import (Alternativa, Avaliacao, Disciplina, Escola, Matricula, Meta, Questao, Turma, Usuario,
                     Vinculo, agora)


def popular_demo():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(Escola)):
            return
        if not db.scalar(select(Usuario).where(Usuario.papel == "admin")):
            db.add(Usuario(nome="Administrador", login="admin", senha_hash=hash_senha("admin123"), papel="admin"))
        prof = Usuario(nome="Profa. Ana Souza", login="professor", senha_hash=hash_senha("prof123"), papel="professor")
        escola = Escola(nome="E.E. Monteiro Lobato")
        ciencias = Disciplina(nome="Ciências", escola=escola)
        db.add_all([prof, escola, ciencias, Disciplina(nome="Matemática", escola=escola),
                    Disciplina(nome="Língua Portuguesa", escola=escola)])
        db.flush()
        turma = Turma(nome="9º Ano A", ano_letivo="2026", escola=escola, professor_id=prof.id)
        db.add_all([turma, Turma(nome="9º Ano B", ano_letivo="2026", escola=escola, professor_id=prof.id),
                    Vinculo(professor_id=prof.id, escola_id=escola.id, disciplina_id=ciencias.id)])
        db.flush()
        nomes = ["Beatriz Lima", "Carlos Pereira", "Daniela Rocha", "Eduardo Martins", "Fernanda Alves"]
        for i, nome in enumerate(nomes, start=1):
            a = Usuario(nome=nome, login=f"aluno{i}", senha_hash=hash_senha("1234"), papel="aluno")
            db.add(a)
            db.flush()
            db.add(Matricula(turma_id=turma.id, aluno_id=a.id))

        # segundo professor, em outra escola: não enxerga nada da Profa. Ana (e vice-versa)
        prof2 = Usuario(nome="Prof. Bruno Costa", login="professor2", senha_hash=hash_senha("prof123"), papel="professor")
        escola2 = Escola(nome="Colégio Vila Nova")
        mat2 = Disciplina(nome="Matemática", escola=escola2)
        db.add_all([prof2, escola2, mat2])
        db.flush()
        turma2 = Turma(nome="1º EM", ano_letivo="2026", escola=escola2, professor_id=prof2.id)
        db.add_all([turma2, Vinculo(professor_id=prof2.id, escola_id=escola2.id, disciplina_id=mat2.id)])
        db.flush()
        for i, nome in enumerate(["Gabriel Nunes", "Helena Dias"], start=6):
            a = Usuario(nome=nome, login=f"aluno{i}", senha_hash=hash_senha("1234"), papel="aluno")
            db.add(a)
            db.flush()
            db.add(Matricula(turma_id=turma2.id, aluno_id=a.id))
        db.flush()

        av = Avaliacao(titulo="Simulado de Ciências — Bimestre 3", tipo="simulado",
                       descricao="Leia com atenção. Suas respostas são salvas automaticamente.",
                       escola=escola, turma=turma, disciplina=ciencias, professor_id=prof.id,
                       inicio=agora() - timedelta(minutes=5), fim=agora() + timedelta(days=7),
                       duracao_min=40, publicada=True, liberar_resultado="apos_envio")

        def obj(enun, alts, correta, expl, pts=1.0):
            q = Questao(tipo="objetiva", enunciado=enun, peso=1.0, explicacao=expl)
            q.alternativas = [Alternativa(texto=t, correta=(i == correta), ordem=i) for i, t in enumerate(alts)]
            return q

        av.questoes = [
            obj("Qual organela é responsável pela respiração celular?",
                ["Ribossomo", "Mitocôndria", "Complexo de Golgi", "Lisossomo"], 1,
                "A mitocôndria produz ATP a partir da glicose e do oxigênio."),
            obj("Qual é a fórmula química da água?", ["H2O", "CO2", "O2", "NaCl"], 0,
                "Cada molécula de água tem dois átomos de hidrogênio e um de oxigênio."),
            obj("Qual planeta é conhecido como Planeta Vermelho?", ["Vênus", "Júpiter", "Marte", "Saturno"], 2,
                "O óxido de ferro na superfície dá a Marte a cor avermelhada."),
            obj("A unidade de medida de força no SI é:", ["Joule", "Watt", "Pascal", "Newton"], 3,
                "1 newton é a força que acelera 1 kg a 1 m/s²."),
            Questao(tipo="dissertativa", peso=2.0,
                    enunciado="Explique o que é a fotossíntese e cite os principais elementos envolvidos.",
                    gabarito_texto="Processo em que as plantas usam a luz solar, gás carbônico e água para "
                                   "produzir glicose e liberar oxigênio, com participação da clorofila.",
                    palavras_chave=["luz|solar|luminosa", "gás carbônico|CO2|dióxido de carbono", "água",
                                    "glicose|açúcar", "oxigênio", "clorofila"],
                    explicacao="Resposta completa menciona luz, CO2, água, glicose, oxigênio e clorofila."),
        ]
        for i, q in enumerate(av.questoes):
            q.ordem = i
        av.nota_total = 10.0
        redistribuir_pontos(av)  # 4 objetivas peso 1 + 1 dissertativa peso 2 -> 1,67 cada e 3,32
        db.add(av)
        db.commit()


if __name__ == "__main__":
    popular_demo()
    print("Dados de demonstração criados.")
