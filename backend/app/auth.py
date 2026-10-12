import os
from datetime import timedelta

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from .db import get_db
from .models import Usuario, agora

SECRET_KEY = os.getenv("SECRET_KEY", "troque-esta-chave-em-producao")
ALGORITMO = "HS256"
EXPIRA_HORAS = int(os.getenv("TOKEN_EXPIRA_HORAS", "12"))

_bearer = HTTPBearer(auto_error=False)


def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt(rounds=int(os.getenv("BCRYPT_ROUNDS", "10")))).decode()


def verificar_senha(senha: str, hash_: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode(), hash_.encode())
    except ValueError:
        return False


def criar_token(usuario: Usuario) -> str:
    payload = {"sub": str(usuario.id), "papel": usuario.papel,
               "exp": agora() + timedelta(hours=EXPIRA_HORAS)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITMO)


def usuario_atual(cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
                  db: Session = Depends(get_db)) -> Usuario:
    if not cred:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Não autenticado")
    try:
        payload = jwt.decode(cred.credentials, SECRET_KEY, algorithms=[ALGORITMO])
        uid = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão inválida ou expirada")
    user = db.get(Usuario, uid)
    if not user or not user.ativo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuário inativo")
    return user


def exige_professor(user: Usuario = Depends(usuario_atual)) -> Usuario:
    if user.papel not in ("admin", "professor"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Acesso restrito a professores")
    return user


def exige_admin(user: Usuario = Depends(usuario_atual)) -> Usuario:
    if user.papel != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Acesso restrito ao administrador")
    return user


def exige_aluno(user: Usuario = Depends(usuario_atual)) -> Usuario:
    if user.papel != "aluno":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Acesso restrito a alunos")
    return user
