"""
Database Connection & Management for Smart Procurement Vendor AI
Supports direct raw SQL queries with psycopg2 on PostgreSQL (strict tech stack),
with a transparent local SQLite fallback mode if PostgreSQL is not running locally.
"""

import os
import re
import sqlite3
from contextlib import contextmanager
from typing import Generator, Any
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://postgres:postgres@localhost:5432/smart_procurement"
)

# Detect if Postgres connection is requested
USE_POSTGRES = DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://")

# Try importing psycopg2
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False


class SQLiteDictCursor:
    """Wrapper around sqlite3 cursor to behave like psycopg2 RealDictCursor with %s support."""
    def __init__(self, cursor: sqlite3.Cursor):
        self._cursor = cursor
        self.description = cursor.description

    def execute(self, sql: str, params: Any = None):
        # Convert %s placeholders to ? for SQLite compatibility
        converted_sql = re.sub(r'(?<!%)(%s)', '?', sql)
        # Convert PostgreSQL CURRENT_TIMESTAMP / INTERVAL syntax if needed
        converted_sql = re.sub(r"CURRENT_DATE\s*\+\s*INTERVAL\s*'(\d+)\s*days'", r"date('now', '+\1 days')", converted_sql, flags=re.IGNORECASE)
        # Handle ON CONFLICT DO NOTHING
        if params is None:
            self._cursor.execute(converted_sql)
        else:
            # Flatten or adapt params if necessary
            param_list = list(params) if isinstance(params, (tuple, list)) else [params]
            self._cursor.execute(converted_sql, param_list)
        self.description = self._cursor.description
        return self

    def executemany(self, sql: str, seq_of_parameters: Any):
        converted_sql = re.sub(r'(?<!%)(%s)', '?', sql)
        self._cursor.executemany(converted_sql, seq_of_parameters)
        return self

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def fetchall(self):
        rows = self._cursor.fetchall()
        return [dict(r) for r in rows]

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    def close(self):
        self._cursor.close()


def _test_postgres_connection() -> bool:
    if not PSYCOPG2_AVAILABLE or not USE_POSTGRES:
        return False
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=2)
        conn.close()
        return True
    except Exception:
        return False


# Determine mode at startup
IS_POSTGRES_CONNECTED = _test_postgres_connection()
SQLITE_DB_PATH = os.path.join(os.path.dirname(__file__), "procurement.db")


def get_raw_connection():
    global IS_POSTGRES_CONNECTED
    if IS_POSTGRES_CONNECTED:
        try:
            return psycopg2.connect(DATABASE_URL)
        except Exception:
            # Fall back if connection dropped
            pass

    # SQLite connection with dict rows
    conn = sqlite3.connect(SQLITE_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_db_cursor(commit: bool = False) -> Generator[Any, None, None]:
    """Context manager for obtaining a database cursor returning dictionary rows."""
    conn = get_raw_connection()
    is_psycopg = hasattr(conn, "cursor_factory") or type(conn).__module__.startswith("psycopg2")

    if is_psycopg:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            yield cursor
            if commit:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()
    else:
        raw_cur = conn.cursor()
        cursor = SQLiteDictCursor(raw_cur)
        try:
            yield cursor
            if commit:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            raw_cur.close()
            conn.close()


def init_db(force: bool = False):
    """Executes schema.sql and seed.sql if tables do not exist or force=True."""
    global IS_POSTGRES_CONNECTED
    IS_POSTGRES_CONNECTED = _test_postgres_connection()

    schema_file = os.path.join(os.path.dirname(__file__), "schema.sql")
    seed_file = os.path.join(os.path.dirname(__file__), "seed.sql")

    with open(schema_file, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    with open(seed_file, "r", encoding="utf-8") as f:
        seed_sql = f.read()

    with get_db_cursor(commit=True) as cur:
        if IS_POSTGRES_CONNECTED:
            # PostgreSQL execution
            if force:
                cur.execute(schema_sql)
                cur.execute(seed_sql)
                print("[Database] PostgreSQL initialized with schema.sql and seed.sql successfully.")
            else:
                # Run table creations (without DROP TABLE unless force)
                clean_lines = [l for l in schema_sql.splitlines() if not l.strip().startswith("--") and not l.strip().upper().startswith("DROP TABLE")]
                cur.execute("\n".join(clean_lines))
                # Check if vendors table is empty
                cur.execute("SELECT COUNT(*) as count FROM vendors")
                cnt = cur.fetchone()["count"]
                if cnt == 0:
                    cur.execute(seed_sql)
                    print("[Database] PostgreSQL seeded successfully (vendors table was empty).")
                else:
                    print(f"[Database] PostgreSQL already contains {cnt} vendors. Skipping seed.")
        else:
            # Drop tables if force
            if force:
                for tbl in ["ai_analysis", "quotes", "rfqs", "vendors", "users"]:
                    try:
                        cur.execute(f"DROP TABLE IF EXISTS {tbl}")
                    except Exception:
                        pass

            # Convert PostgreSQL DDL to SQLite DDL
            clean_lines = [l for l in schema_sql.splitlines() if not l.strip().startswith("--")]
            clean_schema = "\n".join(clean_lines)

            sqlite_schema = clean_schema
            sqlite_schema = re.sub(r'SERIAL\s+PRIMARY\s+KEY', 'INTEGER PRIMARY KEY AUTOINCREMENT', sqlite_schema, flags=re.IGNORECASE)
            sqlite_schema = re.sub(r'TIMESTAMP\s+WITH\s+TIME\s+ZONE', 'DATETIME', sqlite_schema, flags=re.IGNORECASE)
            sqlite_schema = re.sub(r'NUMERIC\(\d+,\s*\d+\)', 'REAL', sqlite_schema, flags=re.IGNORECASE)

            # Split statements and run schema creation
            for stmt in sqlite_schema.split(';'):
                stmt = stmt.strip()
                if stmt and not stmt.upper().startswith("DROP TABLE"):
                    cur.execute(stmt)

            # Check if vendors table has records
            cur.execute("SELECT COUNT(*) as count FROM vendors")
            cnt_row = cur.fetchone()
            vendor_count = cnt_row["count"] if cnt_row else 0

            # ONLY run seed if vendors table is empty
            if vendor_count == 0:
                clean_seed_lines = [l for l in seed_sql.splitlines() if not l.strip().startswith("--")]
                sqlite_seed = "\n".join(clean_seed_lines)
                sqlite_seed = re.sub(r"CURRENT_DATE\s*\+\s*INTERVAL\s*'(\d+)\s*days'", r"date('now', '+\1 days')", sqlite_seed, flags=re.IGNORECASE)

                for stmt in sqlite_seed.split(';'):
                    stmt = stmt.strip()
                    if stmt:
                        try:
                            cur.execute(stmt)
                        except Exception as e:
                            # Ignore unique constraint collisions if any
                            pass
                print(f"[Database] SQLite seeded at {SQLITE_DB_PATH} (vendors table was empty).")
            else:
                print(f"[Database] SQLite already contains {vendor_count} vendors. Skipping seed.")
