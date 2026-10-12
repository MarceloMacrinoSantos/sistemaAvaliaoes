"""Transforma um usuário em ADMINISTRADOR (ou cria um admin), direto no banco.

Use quando ninguém lembrar a senha do admin:
    python tornar_admin.py                 -> lista os usuários da equipe
    python tornar_admin.py LOGIN           -> torna LOGIN administrador
    python tornar_admin.py LOGIN NOVASENHA -> torna administrador e redefine a senha
Rode com o sistema FECHADO, dentro da pasta backend.
"""
import sys

from sqlalchemy import func, select

from app.auth import hash_senha
from app.db import Base, SessionLocal, engine, migrar_colunas
from app.models import Usuario

Base.metadata.create_all(engine)
migrar_colunas()
with SessionLocal() as db:
    if len(sys.argv) < 2:
        print("Usuários da equipe:")
        for u in db.scalars(select(Usuario).where(Usuario.papel != "aluno").order_by(Usuario.nome)):
            print(f"  {u.login:20} {u.papel:10} {u.nome}")
        print("\nUso: python tornar_admin.py LOGIN [NOVASENHA]")
        sys.exit(0)
    login = sys.argv[1].strip()
    u = db.scalar(select(Usuario).where(func.lower(Usuario.login) == login.lower()))
    if not u:
        sys.exit(f"Usuário '{login}' não encontrado.")
    u.papel, u.ativo = "admin", True
    if len(sys.argv) > 2:
        u.senha_hash = hash_senha(sys.argv[2])
    db.commit()
    print(f"OK: {u.nome} ({u.login}) agora é ADMINISTRADOR." + (" Senha redefinida." if len(sys.argv) > 2 else ""))
