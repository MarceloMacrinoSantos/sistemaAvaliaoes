"""Conexão com o banco de dados.

Por padrão usa SQLite (arquivo local, zero configuração) em modo WAL, que
suporta tranquilamente dezenas de alunos simultâneos. Para hospedagem na
nuvem, defina DATABASE_URL apontando para um PostgreSQL (ex.: Neon, Supabase).
"""
import os

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./avaliacoes.db")

# Provedores costumam entregar "postgres://" ou "postgresql://"; usamos o driver psycopg 3.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

IS_SQLITE = DATABASE_URL.startswith("sqlite")

if IS_SQLITE:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False, "timeout": 30},
        pool_size=20,
        max_overflow=20,
    )

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")      # leitores não bloqueiam escritores
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.close()
else:
    engine = create_engine(DATABASE_URL, pool_size=10, max_overflow=10, pool_pre_ping=True, pool_recycle=300)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def migrar_colunas() -> None:
    """Adiciona colunas novas em bancos já existentes (atualização sem perder dados)."""
    insp = inspect(engine)
    with engine.begin() as conn:
        for tabela in Base.metadata.sorted_tables:
            if not insp.has_table(tabela.name):
                continue
            existentes = {c["name"] for c in insp.get_columns(tabela.name)}
            for col in tabela.columns:
                if col.name in existentes:
                    continue
                tipo = col.type.compile(engine.dialect)
                padrao = ""
                if col.default is not None and getattr(col.default, "is_scalar", False):
                    v = col.default.arg
                    padrao = " DEFAULT " + (("TRUE" if v else "FALSE") if isinstance(v, bool) else repr(v))
                conn.execute(text(f'ALTER TABLE {tabela.name} ADD COLUMN {col.name} {tipo}{padrao}'))
