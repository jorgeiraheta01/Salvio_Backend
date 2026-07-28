"""
Runner de migraciones liviano para la arquitectura DB-per-tenant de Salvio.

Por que esto y no Alembic: Alembic asume una BD objetivo. Aca hay una BD
fisica por clinica (salvio_<tenant_id>) mas salvio_tenant_template (la
plantilla que se clona al aprovisionar una clinica nueva) mas salvio_control
(esquema distinto, solo para el owner de la plataforma). Adoptar Alembic
significaria correrlo en un loop programatico contra cada BD de todos
modos -- para el tamano actual del proyecto (~12 BDs de tenant, todos los
cambios de esquema hasta ahora fueron aditivos), este runner minimo hace lo
mismo sin la maquinaria de Alembic (sin autogenerate, sin branching). Si el
ritmo de cambios de esquema crece, migrar a Alembic-por-tenant es la
evolucion natural (documentado en la auditoria de ciclo de vida, hallazgo H-00).

Convenciones:
- sql/migrations/tenant/NNNN_descripcion.sql (+ _down.sql) -- se aplica a
  salvio_tenant_template y a TODAS las BDs salvio_<tenant_id> existentes.
- sql/migrations/control/NNNN_descripcion.sql (+ _down.sql) -- se aplica
  SOLO a salvio_control (esquema distinto, linea de migraciones separada).
- Cada archivo debe ser idempotente por si mismo (CREATE TABLE IF NOT
  EXISTS, ADD COLUMN IF NOT EXISTS -- soportado desde MySQL 8.0.29) como
  segunda capa de seguridad ademas del tracking en `schema_migrations`.
- Toda migracion nueva DEBE tener su _down.sql con downgrade real. Sin
  downgrade, no se acepta la migracion (regla dura, no opcional).

Uso:
    python scripts/migrate.py control up
    python scripts/migrate.py control down 0001_create_audit_log
    python scripts/migrate.py tenant up
    python scripts/migrate.py tenant up --only salvio_clinica_qa_norte
    python scripts/migrate.py tenant status
"""

import argparse
import re
import sys
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = ROOT / "sql" / "migrations"

# TODO: leer de .env en vez de hardcodear -- por ahora coincide con el resto
# de scripts de esta sesion (docker-compose local).
DB_HOST = "127.0.0.1"
DB_USER = "root"
DB_PASSWORD = "rootroot"

RESERVED_DB_NAMES = {"salvio_control"}


def connect(database: str | None = None):
    return pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=database, autocommit=False)


def ensure_tracking_table(db_name: str) -> None:
    conn = connect(db_name)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    name VARCHAR(255) PRIMARY KEY,
                    applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        conn.commit()
    finally:
        conn.close()


def applied_migrations(db_name: str) -> set[str]:
    conn = connect(db_name)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM schema_migrations")
            return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()


def list_migration_files(track: str) -> list[Path]:
    folder = MIGRATIONS_DIR / track
    if not folder.exists():
        return []
    files = sorted(p for p in folder.glob("*.sql") if not p.name.endswith("_down.sql"))
    return files


def target_databases(track: str, only: str | None) -> list[str]:
    if track == "control":
        return ["salvio_control"]

    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SHOW DATABASES LIKE 'salvio\\_%'")
            names = [row[0] for row in cur.fetchall() if row[0] not in RESERVED_DB_NAMES]
    finally:
        conn.close()

    if only:
        if only not in names:
            raise SystemExit(f"'{only}' no es una base de datos salvio_* conocida.")
        return [only]
    return names


def run_sql_file(db_name: str, path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    conn = connect(db_name)
    try:
        with conn.cursor() as cur:
            for statement in re.split(r";\s*\n", sql):
                statement = statement.strip()
                if statement:
                    cur.execute(statement)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def mark_applied(db_name: str, name: str) -> None:
    conn = connect(db_name)
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (name,))
        conn.commit()
    finally:
        conn.close()


def mark_unapplied(db_name: str, name: str) -> None:
    conn = connect(db_name)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM schema_migrations WHERE name = %s", (name,))
        conn.commit()
    finally:
        conn.close()


def cmd_up(track: str, only: str | None) -> None:
    files = list_migration_files(track)
    if not files:
        print(f"No hay migraciones en sql/migrations/{track}/")
        return
    dbs = target_databases(track, only)
    print(f"Aplicando {len(files)} migracion(es) de '{track}' contra {len(dbs)} BD(s): {dbs}")
    failed: list[str] = []
    for db_name in dbs:
        ensure_tracking_table(db_name)
        done = applied_migrations(db_name)
        for f in files:
            name = f.stem
            if name in done:
                continue
            try:
                run_sql_file(db_name, f)
                mark_applied(db_name, name)
                print(f"  [OK]   {db_name} <- {name}")
            except Exception as exc:
                print(f"  [FAIL] {db_name} <- {name}: {exc}")
                failed.append(f"{db_name}:{name}")
                break  # no seguir aplicando migraciones posteriores a esta BD si una falla
    if failed:
        print("\nFallaron:", failed)
        sys.exit(1)
    print("\nListo, sin fallos.")


def cmd_down(track: str, migration_name: str, only: str | None) -> None:
    down_file = MIGRATIONS_DIR / track / f"{migration_name}_down.sql"
    if not down_file.exists():
        raise SystemExit(f"No existe {down_file} -- toda migracion debe tener su _down.sql.")
    dbs = target_databases(track, only)
    for db_name in dbs:
        done = applied_migrations(db_name)
        if migration_name not in done:
            print(f"  [SKIP] {db_name} (no tiene '{migration_name}' aplicada)")
            continue
        run_sql_file(db_name, down_file)
        mark_unapplied(db_name, migration_name)
        print(f"  [OK]   {db_name} <- downgrade {migration_name}")


def cmd_status(track: str, only: str | None) -> None:
    files = [f.stem for f in list_migration_files(track)]
    dbs = target_databases(track, only)
    for db_name in dbs:
        ensure_tracking_table(db_name)
        done = applied_migrations(db_name)
        pending = [f for f in files if f not in done]
        print(f"{db_name}: {len(done)} aplicadas, {len(pending)} pendientes {pending if pending else ''}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("track", choices=["control", "tenant"])
    parser.add_argument("action", choices=["up", "down", "status"])
    parser.add_argument("migration_name", nargs="?", help="requerido para 'down'")
    parser.add_argument("--only", help="limitar a una sola base de datos (por nombre completo, ej. salvio_clinica_qa_norte)")
    args = parser.parse_args()

    if args.action == "up":
        cmd_up(args.track, args.only)
    elif args.action == "status":
        cmd_status(args.track, args.only)
    elif args.action == "down":
        if not args.migration_name:
            raise SystemExit("'down' requiere el nombre de la migracion, ej: python scripts/migrate.py control down 0001_create_audit_log")
        cmd_down(args.track, args.migration_name, args.only)
