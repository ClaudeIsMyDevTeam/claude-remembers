import math
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

from . import db, embeddings
from .types import (
    CONFIDENCE_FLOOR,
    CONFIRM_BUMP,
    CONFIRM_DECAY_MULTIPLIERS,
    HALF_LIVES,
    Memory,
    MemoryStatus,
    MemoryType,
)

_DB_PATH = os.environ.get(
    "CLAUDE_MEMORY_DB_PATH",
    os.path.join(os.path.dirname(__file__), "..", "memory.db"),
)
_DB_PATH = os.path.abspath(_DB_PATH)

# Initialize DB and run startup decay in a background thread so the MCP
# initialize handshake isn't blocked by the initial Turso sync (which can
# take >60 s on first run when building a fresh local replica).
_ready = threading.Event()


def _background_startup() -> None:
    db.init_db(_DB_PATH)
    _ready.set()
    embeddings.encode("warmup")  # Pre-warm model so first recall isn't slow
    decay_all()


threading.Thread(target=_background_startup, daemon=True).start()


def _wait_ready() -> None:
    """Block until DB init is complete. Called by every public function."""
    _ready.wait()


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def _half_life(memory: Memory) -> float:
    """Effective half-life in days for this memory."""
    if memory.decay_rate is not None:
        return math.log(2) / memory.decay_rate

    base = HALF_LIVES[memory.type]
    for min_count, multiplier in CONFIRM_DECAY_MULTIPLIERS:
        if memory.confirmed_count >= min_count:
            return base * multiplier
    return base


def effective_confidence(memory: Memory) -> float:
    """Compute current confidence given stored fields and current time.
    Pure function — no I/O.
    """
    anchor = memory.last_confirmed_at or memory.created_at
    # Make both timezone-aware for safe subtraction
    now = datetime.now(timezone.utc)
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=timezone.utc)
    elapsed_days = (now - anchor).total_seconds() / 86400.0
    half_life = _half_life(memory)
    decayed = memory.confidence * math.pow(2.0, -elapsed_days / half_life)
    return max(CONFIDENCE_FLOOR, decayed)


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def remember(
    content: str,
    type: MemoryType,
    source: str,
    confidence: float = 0.7,
    decay_rate: Optional[float] = None,
) -> str:
    """Store a new memory. Returns the new memory's id."""
    _wait_ready()
    confidence = max(0.0, min(1.0, confidence))
    now = datetime.utcnow()
    memory = Memory(
        id=str(uuid.uuid4()),
        type=type,
        content=content,
        source=source,
        confidence=confidence,
        created_at=now,
        updated_at=now,
        embedding=embeddings.encode(content),
        decay_rate=decay_rate,
    )
    db.insert(_DB_PATH, memory)
    return memory.id


def recall(query: str, top_k: int = 5) -> list[tuple[Memory, float]]:
    """Retrieve the top_k most relevant active memories for a query.
    Scores combine semantic similarity and effective confidence.
    Returns (Memory, score) tuples sorted by descending score.
    """
    _wait_ready()
    query_vec = embeddings.encode(query)
    candidates = db.get_all_active(_DB_PATH)
    if not candidates:
        return []

    scored = []
    for memory in candidates:
        if memory.embedding is not None:
            cosine = embeddings.cosine_similarity(query_vec, memory.embedding)
            score = cosine * effective_confidence(memory)
            scored.append((memory, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


def forget(id: str) -> None:
    """Mark a memory as forgotten. Row is retained for audit purposes."""
    _wait_ready()
    db.update_status(_DB_PATH, id, MemoryStatus.FORGOTTEN)


def update(id: str, new_content: str, source: Optional[str] = None) -> str:
    """Correct a memory. Marks the original as CORRECTED and inserts a new record.
    Returns the new memory's id.
    """
    _wait_ready()
    original = db.get_by_id(_DB_PATH, id)
    if original is None:
        raise ValueError(f"No memory found with id {id!r}")

    new_id = str(uuid.uuid4())

    db.update_status(_DB_PATH, id, MemoryStatus.CORRECTED, replaced_by=new_id)

    now = datetime.utcnow()
    replacement = Memory(
        id=new_id,
        type=original.type,
        content=new_content,
        source=source or original.source,
        confidence=original.confidence,
        created_at=now,
        updated_at=now,
        embedding=embeddings.encode(new_content),
        corrected_by=id,
        decay_rate=original.decay_rate,
    )
    db.insert(_DB_PATH, replacement)
    return new_id


def confirm(id: str) -> Memory:
    """Confirm a memory is still accurate.
    Resets decay timer, bumps confidence by 10%, increments confirmed_count.
    Returns the updated memory.
    """
    _wait_ready()
    memory = db.get_by_id(_DB_PATH, id)
    if memory is None:
        raise ValueError(f"No memory found with id {id!r}")

    now = datetime.utcnow()
    new_confidence = min(1.0, memory.confidence * CONFIRM_BUMP)

    db.update_confidence(
        _DB_PATH,
        id,
        confidence=new_confidence,
        last_confirmed_at=now,
        confirmed_count_delta=1,
    )

    memory.confidence = new_confidence
    memory.last_confirmed_at = now
    memory.confirmed_count += 1
    memory.updated_at = now
    return memory


def decay_all() -> int:
    """Apply time-based confidence decay to all active memories.
    Memories that fall to the confidence floor are marked STALE.
    Skips if run within the past hour. Returns count of updated rows.
    """
    last_run_iso = db.get_meta(_DB_PATH, "last_decay_run")
    if last_run_iso:
        last_run = datetime.fromisoformat(last_run_iso)
        elapsed_seconds = (datetime.utcnow() - last_run).total_seconds()
        if elapsed_seconds < 3600:
            return 0

    candidates = db.get_needing_decay(_DB_PATH)
    updated = 0

    for memory in candidates:
        new_conf = effective_confidence(memory)
        delta = abs(new_conf - memory.confidence)
        if delta < 0.01:
            continue  # not enough change to bother writing

        new_status = MemoryStatus.STALE if new_conf <= CONFIDENCE_FLOOR else None
        db.update_confidence(_DB_PATH, memory.id, confidence=new_conf, status=new_status)
        updated += 1

    db.upsert_meta(_DB_PATH, "last_decay_run", datetime.utcnow().isoformat())
    return updated


def get_stale() -> list[Memory]:
    """Return memories that have decayed below the confidence floor."""
    _wait_ready()
    return db.get_stale(_DB_PATH)
