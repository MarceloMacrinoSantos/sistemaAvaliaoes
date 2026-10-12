"""Migração de dados para o modelo com vínculos (professor x escola x disciplina) e matrículas.

Roda uma única vez em bancos criados por versões anteriores, sem perder nada:
- cada aluno ganha a matrícula na turma em que estava;
- cada disciplina passa a pertencer à escola das avaliações que a usam (quando for uma só);
- cada turma passa a ter como dono o professor das avaliações dela (quando for um só);
- cada professor ganha vínculo com as escolas/disciplinas em que já tem avaliações.
Turmas sem dono e disciplinas sem escola continuam visíveis para o administrador, que pode ajustá-las.
"""
from collections import defaultdict

from sqlalchemy import select

from .models import Avaliacao, Disciplina, Matricula, Meta, Turma, Usuario, Vinculo

CHAVE = "migracao_vinculos_v10"


def migrar_dados(db) -> None:
    if db.get(Meta, CHAVE):
        return
    # 1) matrículas a partir do campo antigo usuarios.turma_id
    existentes = {(m.turma_id, m.aluno_id) for m in db.scalars(select(Matricula))}
    for a in db.scalars(select(Usuario).where(Usuario.papel == "aluno", Usuario.turma_id.is_not(None))):
        if (a.turma_id, a.id) not in existentes:
            db.add(Matricula(turma_id=a.turma_id, aluno_id=a.id, lote_importacao=a.lote_importacao))
    avs = list(db.scalars(select(Avaliacao)))
    # 2) escola das disciplinas
    esc_por_disc = defaultdict(set)
    for av in avs:
        esc_por_disc[av.disciplina_id].add(av.escola_id)
    for d in db.scalars(select(Disciplina).where(Disciplina.escola_id.is_(None))):
        if len(esc_por_disc.get(d.id, ())) == 1:
            d.escola_id = next(iter(esc_por_disc[d.id]))
    # 3) dono das turmas
    prof_por_turma = defaultdict(set)
    for av in avs:
        if av.professor_id:
            prof_por_turma[av.turma_id].add(av.professor_id)
    for t in db.scalars(select(Turma).where(Turma.professor_id.is_(None))):
        if len(prof_por_turma.get(t.id, ())) == 1:
            t.professor_id = next(iter(prof_por_turma[t.id]))
    # 4) vínculos dos professores
    ja = {(v.professor_id, v.escola_id, v.disciplina_id) for v in db.scalars(select(Vinculo))}
    papeis = {u.id: u.papel for u in db.scalars(select(Usuario).where(Usuario.papel != "aluno"))}
    for av in avs:
        chave = (av.professor_id, av.escola_id, av.disciplina_id)
        if av.professor_id and papeis.get(av.professor_id) == "professor" and chave not in ja:
            db.add(Vinculo(professor_id=av.professor_id, escola_id=av.escola_id, disciplina_id=av.disciplina_id))
            ja.add(chave)
    db.add(Meta(chave=CHAVE, valor="ok"))
    db.commit()


CHAVE_V11 = "migracao_dono_escolas_v11"


def migrar_donos(db) -> None:
    """Escolas/disciplinas antigas passam a pertencer ao professor que as usa (quando é um só)."""
    if db.get(Meta, CHAVE_V11):
        return
    from .models import Escola
    profs = {u.id for u in db.scalars(select(Usuario).where(Usuario.papel == "professor"))}
    usos_escola, usos_disc = defaultdict(set), defaultdict(set)
    for t in db.scalars(select(Turma)):
        if t.professor_id in profs:
            usos_escola[t.escola_id].add(t.professor_id)
    for av in db.scalars(select(Avaliacao)):
        if av.professor_id in profs:
            usos_escola[av.escola_id].add(av.professor_id)
            usos_disc[av.disciplina_id].add(av.professor_id)
    for e in db.scalars(select(Escola).where(Escola.criado_por.is_(None))):
        if len(usos_escola.get(e.id, ())) == 1:
            e.criado_por = next(iter(usos_escola[e.id]))
    for d in db.scalars(select(Disciplina).where(Disciplina.criado_por.is_(None))):
        if len(usos_disc.get(d.id, ())) == 1:
            d.criado_por = next(iter(usos_disc[d.id]))
    db.add(Meta(chave=CHAVE_V11, valor="ok"))
    db.commit()
