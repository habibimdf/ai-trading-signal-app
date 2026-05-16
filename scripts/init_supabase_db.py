from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import dotenv_values


def _database_url() -> str:
    env = dotenv_values(ROOT / ".env")
    return str(env.get("DATABASE_URL") or "").strip().strip('"')


def _init_postgres(database_url: str) -> None:
    import psycopg

    schema = (ROOT / "supabase" / "schema.sql").read_text(encoding="utf-8")
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(schema)
        conn.commit()


if __name__ == "__main__":
    database_url = _database_url()
    if database_url.startswith(("postgres://", "postgresql://")):
        _init_postgres(database_url)
        print("Supabase/Postgres tables are ready.")
    else:
        from app.db import init_db

        init_db()
        print("SQLite tables are ready.")
