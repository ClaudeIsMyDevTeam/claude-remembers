import sqlite3
from datetime import datetime
from typing import Optional
import numpy as np

from .types import Memory, MemoryType, MemoryStatus

EMBEDDING_DTYPE = np.float32


def _connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(path: str) -> None:
    with _connect(path) as conn:
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

        # Idempotent migrations for databases created before decay support
        for col_sql in [
            "ALTER TABLE memories ADD COLUMN last_confirmed_at TEXT",
            "ALTER TABLE memories ADD COLUMN confirmed_count INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE memories ADD COLUMN decay_rate REAL",
        ]:
            try:
                conn.execute(col_sql)
            except sqlite3.OperationalError:
                pass  # column already exists


def _row_to_memory(row: sqlite3.Row) -> Memory:
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


def insert(path: str, memory: Memory) -> None:
    embedding_blob = None
    if memory.embedding is not None:
        embedding_blob = memory.embedding.astype(EMBEDDING_DTYPE).tobytes()

    last_confirmed_iso = (
        memory.last_confirmed_at.isoformat() if memory.last_confirmed_at else None
    )

    with _connect(path) as conn:
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


def get_by_id(path: str, id: str) -> Optional[Memory]:
    with _connect(path) as conn:
        row = conn.execute("SELECT * FROM memories WHERE id = ?", (id,)).fetchone()
    return _row_to_memory(row) if row else None


def get_all_active(path: str) -> list[Memory]:
    with _connect(path) as conn:
        rows = conn.execute(
            "SELECT * FROM memories WHERE status = 'active'"
        ).fetchall()
    return [_row_to_memory(r) for r in rows]


def get_needing_decay(path: str) -> list[Memory]:
    """Fetch active memories without loading embedding blobs — for decay computation only."""
    with _connect(path) as conn:
        rows = conn.execute(
            """
            SELECT id, type, content, source, confidence, created_at, updated_at,
                   status, corrected_by, replaced_by,
                   last_confirmed_at, confirmed_count, decay_rate,
                   NULL as embedding
            FROM memories
            WHERE status = 'active'
            """
        ).fetchall()
    return [_row_to_memory(r) for r in rows]


def get_stale(path: str) -> list[Memory]:
    with _connect(path) as conn:
        rows = conn.execute(
            "SELECT * FROM memories WHERE status = 'stale'"
        ).fetchall()
    return [_row_to_memory(r) for r in rows]


def update_status(
    path: str,
    id: str,
    status: MemoryStatus,
    corrected_by: Optional[str] = None,
    replaced_by: Optional[str] = None,
) -> None:
    now = datetime.utcnow().isoformat()
    with _connect(path) as conn:
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
    with _connect(path) as conn:
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


def upsert_meta(path: str, key: str, value: str) -> None:
    with _connect(path) as conn:
        conn.execute(
            "INSERT INTO memory_meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def get_meta(path: str, key: str) -> Optional[str]:
    with _connect(path) as conn:
        row = conn.execute(
            "SELECT value FROM memory_meta WHERE key = ?", (key,)
        ).fetchone()
    return row["value"] if row else None
