import os
import sqlite3
import numpy as np
from datetime import datetime
from typing import Optional

from .types import Memory, MemoryType, MemoryStatus

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

TURSO_URL = os.environ.get("TURSO_URL")
TURSO_TOKEN = os.environ.get("TURSO_TOKEN")
_USE_TURSO = bool(TURSO_URL and TURSO_TOKEN)

if _USE_TURSO:
    import libsql_experimental as libsql

EMBEDDING_DTYPE = np.float32


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def _open(path: str):
    """Open a connection. For Turso: creates embedded replica and syncs from cloud."""
    if _USE_TURSO:
        conn = libsql.connect(path, sync_url=TURSO_URL, auth_token=TURSO_TOKEN)
        try:
            conn.sync()
        except ValueError:
            # Stale WAL artifacts from unclean shutdown — delete local replica and retry.
            # Safe because Turso cloud is the source of truth.
            conn.close()
            for ext in ("-wal", "-shm", "-info"):
                artifact = path + ext
                if os.path.exists(artifact):
                    os.remove(artifact)
            conn = libsql.connect(path, sync_url=TURSO_URL, auth_token=TURSO_TOKEN)
            conn.sync()
        return conn
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _write_close(conn) -> None:
    """Commit, push to Turso, and close."""
    conn.commit()
    if _USE_TURSO:
        conn.sync()
    conn.close()


def _read_close(conn) -> None:
    conn.close()


def _fetchone(cursor) -> Optional[dict]:
    """Fetch one row as a dict regardless of backend."""
    if cursor.description is None:
        return None
    cols = [d[0] for d in cursor.description]
    row = cursor.fetchone()
    return dict(zip(cols, row)) if row else None


def _fetchall(cursor) -> list[dict]:
    """Fetch all rows as dicts regardless of backend."""
    if cursor.description is None:
        return []
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def init_db(path: str) -> None:
    conn = _open(path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id               TEXT PRIMARY KEY,
            type             TEXT NOT NULL,
            content          TEXT NOT NULL,
            source           TEXT NOT NULL,
            confidence       REAL NOT NULL,
            created_at       TEXT NOT NULL,
            updated_at       TEXT NOT NULL,
            status           TEXT NOT NULL DEFAULT 'active',
            embedding        BLOB,
            corrected_by     TEXT,
            replaced_by      TEXT,
            last_confirmed_at TEXT,
            confirmed_count  INTEGER NOT NULL DEFAULT 0,
            decay_rate       REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memory_meta (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    for col_sql in [
        "ALTER TABLE memories ADD COLUMN last_confirmed_at TEXT",
        "ALTER TABLE memories ADD COLUMN confirmed_count INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE memories ADD COLUMN decay_rate REAL",
    ]:
        try:
            conn.execute(col_sql)
        except Exception:
            pass  # column already exists
    _write_close(conn)


# ---------------------------------------------------------------------------
# Row mapping
# ---------------------------------------------------------------------------

def _row_to_memory(row: dict) -> Memory:
    embedding = None
    if row["embedding"] is not None:
        embedding = np.frombuffer(row["embedding"], dtype=EMBEDDING_DTYPE).copy()

    last_confirmed_at = None
    if row["last_confirmed_at"] is not None:
        last_confirmed_at = datetime.fromisoformat(row["last_confirmed_at"])

    return Memory(
        id=row["id"],
        type=MemoryType(row["type"]),
        content=row["content"],
        source=row["source"],
        confidence=row["confidence"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        status=MemoryStatus(row["status"]),
        embedding=embedding,
        corrected_by=row["corrected_by"],
        replaced_by=row["replaced_by"],
        last_confirmed_at=last_confirmed_at,
        confirmed_count=row["confirmed_count"] or 0,
        decay_rate=row["decay_rate"],
    )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def insert(path: str, memory: Memory) -> None:
    embedding_blob = None
    if memory.embedding is not None:
        embedding_blob = memory.embedding.astype(EMBEDDING_DTYPE).tobytes()

    last_confirmed_iso = (
        memory.last_confirmed_at.isoformat() if memory.last_confirmed_at else None
    )

    conn = _open(path)
    conn.execute(
        """
        INSERT INTO memories
            (id, type, content, source, confidence, created_at, updated_at,
             status, embedding, corrected_by, replaced_by,
             last_confirmed_at, confirmed_count, decay_rate)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            memory.id,
            memory.type.value,
            memory.content,
            memory.source,
            memory.confidence,
            memory.created_at.isoformat(),
            memory.updated_at.isoformat(),
            memory.status.value,
            embedding_blob,
            memory.corrected_by,
            memory.replaced_by,
            last_confirmed_iso,
            memory.confirmed_count,
            memory.decay_rate,
        ),
    )
    _write_close(conn)


def get_by_id(path: str, id: str) -> Optional[Memory]:
    conn = _open(path)
    cur = conn.execute("SELECT * FROM memories WHERE id = ?", (id,))
    row = _fetchone(cur)
    _read_close(conn)
    return _row_to_memory(row) if row else None


def get_all_active(path: str) -> list[Memory]:
    conn = _open(path)
    cur = conn.execute("SELECT * FROM memories WHERE status = 'active'")
    rows = _fetchall(cur)
    _read_close(conn)
    return [_row_to_memory(r) for r in rows]


def get_needing_decay(path: str) -> list[Memory]:
    """Fetch active memories without embedding blobs — for decay computation only."""
    conn = _open(path)
    cur = conn.execute(
        """
        SELECT id, type, content, source, confidence, created_at, updated_at,
               status, corrected_by, replaced_by,
               last_confirmed_at, confirmed_count, decay_rate,
               NULL as embedding
        FROM memories
        WHERE status = 'active'
        """
    )
    rows = _fetchall(cur)
    _read_close(conn)
    return [_row_to_memory(r) for r in rows]


def get_stale(path: str) -> list[Memory]:
    conn = _open(path)
    cur = conn.execute("SELECT * FROM memories WHERE status = 'stale'")
    rows = _fetchall(cur)
    _read_close(conn)
    return [_row_to_memory(r) for r in rows]


def update_status(
    path: str,
    id: str,
    status: MemoryStatus,
    corrected_by: Optional[str] = None,
    replaced_by: Optional[str] = None,
) -> None:
    now = datetime.utcnow().isoformat()
    conn = _open(path)
    conn.execute(
        """
        UPDATE memories
        SET status = ?, updated_at = ?,
            corrected_by = COALESCE(?, corrected_by),
            replaced_by  = COALESCE(?, replaced_by)
        WHERE id = ?
        """,
        (status.value, now, corrected_by, replaced_by, id),
    )
    _write_close(conn)


def update_confidence(
    path: str,
    id: str,
    confidence: float,
    last_confirmed_at: Optional[datetime] = None,
    confirmed_count_delta: int = 0,
    status: Optional[MemoryStatus] = None,
) -> None:
    now = datetime.utcnow().isoformat()
    last_confirmed_iso = (
        last_confirmed_at.isoformat() if last_confirmed_at else None
    )
    status_val = status.value if status else None
    conn = _open(path)
    conn.execute(
        """
        UPDATE memories
        SET confidence       = ?,
            updated_at       = ?,
            last_confirmed_at = COALESCE(?, last_confirmed_at),
            confirmed_count  = confirmed_count + ?,
            status           = COALESCE(?, status)
        WHERE id = ?
        """,
        (confidence, now, last_confirmed_iso, confirmed_count_delta, status_val, id),
    )
    _write_close(conn)


def upsert_meta(path: str, key: str, value: str) -> None:
    conn = _open(path)
    conn.execute(
        "INSERT INTO memory_meta (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    _write_close(conn)


def get_meta(path: str, key: str) -> Optional[str]:
    conn = _open(path)
    cur = conn.execute("SELECT value FROM memory_meta WHERE key = ?", (key,))
    row = _fetchone(cur)
    _read_close(conn)
    return row["value"] if row else None
