"""One-time migration: copy all rows from local memory.db to Turso."""
import os
import sys
import sqlite3

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import libsql_experimental as libsql

LOCAL_DB = os.path.join(os.path.dirname(__file__), "memory.db")
TURSO_URL = os.environ["TURSO_URL"]
TURSO_TOKEN = os.environ["TURSO_TOKEN"]
REPLICA = os.path.join(os.path.dirname(__file__), "memory_migration_replica.db")

# Read from local sqlite
src = sqlite3.connect(LOCAL_DB)
src.row_factory = sqlite3.Row
memories = src.execute("SELECT * FROM memories").fetchall()
meta = src.execute("SELECT * FROM memory_meta").fetchall()
src.close()
print(f"Read {len(memories)} memories and {len(meta)} meta rows from local DB")

# Connect to Turso and initialize schema
dst = libsql.connect(REPLICA, sync_url=TURSO_URL, auth_token=TURSO_TOKEN)
dst.sync()

dst.execute("""
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
dst.execute("""
    CREATE TABLE IF NOT EXISTS memory_meta (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
""")

# Insert memories
for row in memories:
    dst.execute(
        """
        INSERT OR IGNORE INTO memories
            (id, type, content, source, confidence, created_at, updated_at,
             status, embedding, corrected_by, replaced_by,
             last_confirmed_at, confirmed_count, decay_rate)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["id"], row["type"], row["content"], row["source"],
            row["confidence"], row["created_at"], row["updated_at"],
            row["status"], row["embedding"], row["corrected_by"],
            row["replaced_by"], row["last_confirmed_at"],
            row["confirmed_count"] or 0, row["decay_rate"],
        ),
    )
    print(f"  migrated [{row['status']}] {row['type']}: {row['content'][:60]}")

for row in meta:
    dst.execute(
        "INSERT OR IGNORE INTO memory_meta (key, value) VALUES (?, ?)",
        (row["key"], row["value"]),
    )

dst.commit()
dst.sync()
dst.close()
os.remove(REPLICA)
print(f"\nDone. {len(memories)} memories migrated to Turso.")
