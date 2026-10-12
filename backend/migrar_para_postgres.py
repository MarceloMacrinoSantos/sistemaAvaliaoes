"""Copia todos os dados do banco local (SQLite, avaliacoes.db) para um PostgreSQL na internet (ex.: Neon).

Uso (com o sistema FECHADO):
    python migrar_para_postgres.py "postgresql://usuario:senha@servidor/banco?sslmode=require"

Opções:
    --origem CAMINHO   outro arquivo .db (padrão: avaliacoes.db ao lado deste script)
    --substituir       apaga o que já existir no PostgreSQL antes de copiar

Nada é alterado no banco local. Usuários, senhas, turmas, avaliações, respostas, monitoramento
e imagens são copiados exatamente como estão.
"""
import argparse
import os
import sqlite3
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent


def url_pg(url: str) -> str:
    url = url.strip().strip('"').strip("'")
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    if not url.startswith("postgresql+psycopg://"):
        sys.exit("O endereço precisa começar com postgresql://  (copie a 'connection string' do Neon)")
    return url


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("destino", help="connection string do PostgreSQL")
    ap.add_argument("--origem", default=str(AQUI / "avaliacoes.db"))
    ap.add_argument("--substituir", action="store_true")
    args = ap.parse_args()

    origem = Path(args.origem)
    if not origem.is_file():
        sys.exit(f"Banco local não encontrado: {origem}")
    # grava no arquivo principal o que ainda está no diário (-wal); exige o sistema fechado
    try:
        con = sqlite3.connect(origem)
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        con.close()
    except sqlite3.Error as e:
        sys.exit(f"Não consegui abrir o banco local ({e}). Feche o sistema e tente de novo.")

    # o app usa a variável DATABASE_URL: apontamos para o banco local para atualizá-lo à versão atual
    os.environ["DATABASE_URL"] = f"sqlite:///{origem}"
    sys.path.insert(0, str(AQUI))
    from sqlalchemy import create_engine, func, inspect, select, text
    from app.db import Base, engine as eng_origem
    from app.main import _inicializar
    import app.models  # noqa: F401  (registra as tabelas)

    print("1/4 Conferindo o banco local...")
    _inicializar()  # cria tabelas/colunas novas que faltarem no banco local

    print("2/4 Conectando ao PostgreSQL...")
    eng_destino = create_engine(url_pg(args.destino), pool_pre_ping=True)
    try:
        with eng_destino.connect() as c:
            c.execute(text("select 1"))
    except Exception as e:
        sys.exit(f"Não consegui conectar ao PostgreSQL: {e}")

    tabelas = Base.metadata.sorted_tables
    existentes = set(inspect(eng_destino).get_table_names())
    if "usuarios" in existentes:
        with eng_destino.connect() as c:
            ja_tem = c.execute(select(func.count()).select_from(Base.metadata.tables["usuarios"])).scalar()
        if ja_tem and not args.substituir:
            sys.exit("O PostgreSQL já tem dados. Para apagar e copiar de novo, rode com --substituir")
    if args.substituir:
        with eng_destino.begin() as c:
            for t in reversed(tabelas):
                c.execute(text(f'DROP TABLE IF EXISTS "{t.name}" CASCADE'))
    Base.metadata.create_all(eng_destino)

    # chaves estrangeiras "circulares" (ex.: escola criada por um usuário que pertence a uma turma da escola)
    # entram vazias e são preenchidas no final
    posicao = {t.name: i for i, t in enumerate(tabelas)}
    adiadas = {t.name: [fk.parent.name for fk in t.foreign_keys if posicao[fk.column.table.name] >= posicao[t.name]]
               for t in tabelas}

    print("3/4 Copiando...")
    totais = {}
    with eng_origem.connect() as src, eng_destino.begin() as dst:
        pendentes = []
        for t in tabelas:
            linhas = [dict(r._mapping) for r in src.execute(select(t))]
            totais[t.name] = len(linhas)
            if not linhas:
                continue
            cols = adiadas[t.name]
            if cols:
                for r in linhas:
                    vals = {c: r[c] for c in cols if r.get(c) is not None}
                    if vals:
                        pendentes.append((t, r["id"], vals))
                    for c in cols:
                        r[c] = None
            for i in range(0, len(linhas), 500):
                dst.execute(t.insert(), linhas[i:i + 500])
            print(f"    {t.name:<14} {len(linhas):>6}")
        for t, pk, vals in pendentes:
            dst.execute(t.update().where(t.c.id == pk).values(**vals))
        # os próximos cadastros continuam a numeração de onde parou
        for t in tabelas:
            if "id" in t.c and t.c.id.primary_key:
                dst.execute(text(f"SELECT setval(pg_get_serial_sequence('{t.name}', 'id'), "
                                 f"COALESCE((SELECT MAX(id) FROM {t.name}), 1), "
                                 f"(SELECT MAX(id) FROM {t.name}) IS NOT NULL)"))

    print("4/4 Conferindo...")
    erros = 0
    with eng_destino.connect() as c:
        for t in tabelas:
            n = c.execute(select(func.count()).select_from(t)).scalar()
            if n != totais[t.name]:
                erros += 1
                print(f"    ✗ {t.name}: {n} no PostgreSQL, {totais[t.name]} no local")
    if erros:
        sys.exit("A cópia ficou incompleta. Rode de novo com --substituir.")
    print(f"\nPronto! {sum(totais.values())} registros copiados. "
          f"{totais.get('usuarios', 0)} usuários, {totais.get('avaliacoes', 0)} avaliações, "
          f"{totais.get('imagens', 0)} imagens.")
    print("Agora use este mesmo endereço em DATABASE_URL no Render.")


if __name__ == "__main__":
    main()
