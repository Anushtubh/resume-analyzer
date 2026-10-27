"""SQLite persistence for recruiter accounts and uploaded resume records."""
import json
import sqlite3
from contextlib import contextmanager
from app.config import DATA_DIR

DATABASE_PATH = DATA_DIR / "talentlens.sqlite3"


@contextmanager
def connect():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def initialize_database():
    with connect() as db:
        db.execute("PRAGMA journal_mode = WAL")
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS resumes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                file_bytes BLOB NOT NULL,
                profile_json TEXT NOT NULL,
                embedding BLOB NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS resumes_owner_id ON resumes(user_id, id);
            CREATE TABLE IF NOT EXISTS resume_storage (
                resume_id INTEGER PRIMARY KEY REFERENCES resumes(id) ON DELETE CASCADE,
                backend TEXT NOT NULL DEFAULT 'sqlite',
                object_key TEXT,
                file_size INTEGER NOT NULL DEFAULT 0
            );
        """)
        # Preserve existing local records and expose accurate file sizes after
        # introducing the optional object-storage metadata table.
        db.execute("""INSERT OR IGNORE INTO resume_storage(resume_id, backend, object_key, file_size)
                      SELECT id, 'sqlite', NULL, length(file_bytes) FROM resumes""")


def user_count() -> int:
    with connect() as db:
        return db.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def list_user_ids() -> list[int]:
    with connect() as db:
        return [int(row[0]) for row in db.execute("SELECT id FROM users ORDER BY id")]


def create_initial_user(email: str, display_name: str, password_hash: str) -> int:
    """Atomically allow only the first local account to be registered."""
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] != 0:
            raise ValueError("Initial account setup is already complete")
        cursor = db.execute("INSERT INTO users(email, display_name, password_hash) VALUES (?, ?, ?)",
                            (email.strip().lower(), display_name.strip(), password_hash))
        return int(cursor.lastrowid)


def create_user(email: str, display_name: str, password_hash: str) -> int:
    """Create an additional recruiter account; email uniqueness is enforced by SQLite."""
    with connect() as db:
        try:
            cursor = db.execute(
                "INSERT INTO users(email, display_name, password_hash) VALUES (?, ?, ?)",
                (email.strip().lower(), display_name.strip(), password_hash),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("An account with this email already exists.") from exc
        return int(cursor.lastrowid)


def get_user(email: str):
    with connect() as db:
        row = db.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int):
    with connect() as db:
        row = db.execute("SELECT id, email, display_name FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def save_resume(user_id: int, filename: str, content_type: str, file_bytes: bytes, profile: dict,
                embedding, *, storage_backend: str = "sqlite", object_key: str | None = None,
                file_size: int | None = None):
    with connect() as db:
        cursor = db.execute("""INSERT INTO resumes
            (user_id, filename, content_type, file_bytes, profile_json, embedding)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, filename, content_type, file_bytes,
             json.dumps(profile, ensure_ascii=False), embedding.tobytes()))
        db.execute("""INSERT INTO resume_storage(resume_id, backend, object_key, file_size)
                      VALUES (?, ?, ?, ?)""",
                   (int(cursor.lastrowid), storage_backend, object_key,
                    len(file_bytes) if file_size is None else int(file_size)))
        return int(cursor.lastrowid)


def list_resumes(user_id: int):
    with connect() as db:
        rows = db.execute("SELECT id, filename, profile_json, embedding FROM resumes WHERE user_id = ? ORDER BY id",
                          (user_id,)).fetchall()
        return [dict(row) for row in rows]


def list_resume_files(user_id: int):
    with connect() as db:
        rows = db.execute("""SELECT r.id, r.filename, r.content_type, r.file_bytes, r.created_at,
                            COALESCE(s.backend, 'sqlite') AS storage_backend,
                            s.object_key,
                            COALESCE(s.file_size, length(r.file_bytes)) AS file_size
                            FROM resumes AS r LEFT JOIN resume_storage AS s ON s.resume_id = r.id
                            WHERE r.user_id = ? ORDER BY r.id""",
                          (user_id,)).fetchall()
        return [dict(row) for row in rows]


def get_resume_file_for_candidate(user_id: int, candidate_id: str):
    """Find an original resume by candidate ID, always scoped to its owner."""
    with connect() as db:
        rows = db.execute("""SELECT r.id, r.filename, r.content_type, r.file_bytes,
                            r.profile_json, COALESCE(s.backend, 'sqlite') AS storage_backend,
                            s.object_key
                            FROM resumes AS r
                            LEFT JOIN resume_storage AS s ON s.resume_id = r.id
                            WHERE r.user_id = ? ORDER BY r.id""", (user_id,)).fetchall()
        for row in rows:
            if json.loads(row["profile_json"]).get("candidate_id") == candidate_id:
                return dict(row)
    return None
