"""Regras de visibilidade: o administrador vê tudo; o professor vê só o que é dele.

- Escolas e disciplinas: as que ele mesmo cadastrou + as dos vínculos feitos pelo administrador.
- Turmas: as que ele criou (Turma.professor_id).
- Alunos: os matriculados nas turmas dele.
- Avaliações: as que ele criou (Avaliacao.professor_id).
"""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Avaliacao, Disciplina, Escola, Matricula, Turma, Usuario, Vinculo


def eh_admin(u: Usuario) -> bool:
    return u.papel == "admin"


def vinculos(db: Session, u: Usuario) -> list[Vinculo]:
    return list(db.scalars(select(Vinculo).where(Vinculo.professor_id == u.id)))


def escolas_permitidas(db: Session, u: Usuario) -> set[int] | None:
    """None = todas (admin)."""
    if eh_admin(u):
        return None
    proprias = set(db.scalars(select(Escola.id).where(Escola.criado_por == u.id)))
    return proprias | {v.escola_id for v in vinculos(db, u)}


def disciplinas_proprias(db: Session, u: Usuario) -> list[Disciplina]:
    return list(db.scalars(select(Disciplina).where(Disciplina.criado_por == u.id)))


def par_permitido(db: Session, u: Usuario, escola_id: int, disciplina_id: int) -> bool:
    if eh_admin(u):
        return True
    if any(v.escola_id == escola_id and v.disciplina_id == disciplina_id for v in vinculos(db, u)):
        return True
    d = db.get(Disciplina, disciplina_id)
    return bool(d and d.criado_por == u.id and d.escola_id == escola_id)


def pode_editar(u: Usuario, obj) -> bool:
    """Escola/disciplina: o admin edita qualquer uma; o professor, só as que ele cadastrou."""
    return eh_admin(u) or getattr(obj, "criado_por", None) == u.id


def filtrar_turmas(q, u: Usuario):
    return q if eh_admin(u) else q.where(Turma.professor_id == u.id)


def turma_do_usuario(db: Session, u: Usuario, turma_id: int) -> Turma:
    t = db.get(Turma, turma_id)
    if not t or (not eh_admin(u) and t.professor_id != u.id):
        raise HTTPException(404, "Turma não encontrada")
    return t


def ids_turmas(db: Session, u: Usuario) -> list[int] | None:
    if eh_admin(u):
        return None
    return list(db.scalars(select(Turma.id).where(Turma.professor_id == u.id)))


def aluno_visivel(db: Session, u: Usuario, aluno_id: int) -> Usuario:
    a = db.get(Usuario, aluno_id)
    if not a or a.papel != "aluno":
        raise HTTPException(404, "Aluno não encontrado")
    if not eh_admin(u):
        tids = ids_turmas(db, u)
        if not db.scalar(select(Matricula.id).where(Matricula.aluno_id == a.id, Matricula.turma_id.in_(tids or [-1]))):
            raise HTTPException(404, "Aluno não encontrado")
    return a


def avaliacao_do_usuario(u: Usuario, av: Avaliacao | None) -> Avaliacao:
    if not av or (not eh_admin(u) and av.professor_id != u.id):
        raise HTTPException(404, "Avaliação não encontrada")
    return av
