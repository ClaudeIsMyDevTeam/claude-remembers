"""
MCP server wrapping the claude-remembers memory store.

Claude for Desktop config (~/.config/claude/claude_desktop_config.json on Mac):

{
  "mcpServers": {
    "memory": {
      "command": "/home/rhrad/projects/claude-remembers/.venv/bin/python",
      "args": ["/home/rhrad/projects/claude-remembers/mcp_server.py"]
    }
  }
}
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from mcp.server.fastmcp import FastMCP
from memory import remember, recall, forget, update, confirm, get_stale, effective_confidence
from memory.types import MemoryType

mcp = FastMCP("claude-memory")

_VALID_TYPES = {t.value for t in MemoryType}
_TYPE_HELP = "One of: user, feedback, project, reference"


def _format_memory(mem, score: float | None = None) -> str:
    lines = []
    if score is not None:
        lines.append(f"[score={score:.3f}]")
    lines.append(f"id: {mem.id}")
    lines.append(f"type: {mem.type.value}")
    lines.append(f"content: {mem.content}")
    lines.append(f"source: {mem.source}")
    conf = effective_confidence(mem)
    lines.append(f"confidence: {conf:.2f} (stored: {mem.confidence:.2f})")
    lines.append(f"status: {mem.status.value}")
    lines.append(f"confirmed_count: {mem.confirmed_count}")
    if mem.last_confirmed_at:
        lines.append(f"last_confirmed_at: {mem.last_confirmed_at.isoformat()}")
    if mem.corrected_by:
        lines.append(f"corrected_by: {mem.corrected_by}")
    return "\n".join(lines)


@mcp.tool()
def memory_remember(
    content: str,
    type: str,
    source: str,
    confidence: float = 0.7,
) -> str:
    """Store a new memory.

    Args:
        content: The fact or information to remember.
        type: Memory type — one of: user, feedback, project, reference.
        source: Where this came from (e.g. "conversation", "user statement", "code observation").
        confidence: How confident you are (0.0–1.0). Default 0.7.
    """
    if type not in _VALID_TYPES:
        return f"Error: invalid type {type!r}. {_TYPE_HELP}"
    id = remember(content, MemoryType(type), source=source, confidence=confidence)
    return f"Stored memory {id}"


@mcp.tool()
def memory_recall(query: str, top_k: int = 5) -> str:
    """Retrieve the most relevant memories for a query.

    Args:
        query: Natural language query describing what you want to recall.
        top_k: How many results to return (default 5).
    """
    results = recall(query, top_k=top_k)
    if not results:
        return "No memories found."
    parts = []
    for i, (mem, score) in enumerate(results, 1):
        parts.append(f"--- Memory {i} ---\n{_format_memory(mem, score)}")
    return "\n\n".join(parts)


@mcp.tool()
def memory_forget(id: str) -> str:
    """Mark a memory as forgotten. The record is kept for audit purposes but excluded from recall.

    Args:
        id: The memory ID to forget (from memory_recall results).
    """
    forget(id)
    return f"Memory {id} marked as forgotten."


@mcp.tool()
def memory_update(id: str, new_content: str, source: str | None = None) -> str:
    """Correct a memory. Marks the original as corrected and creates a new record.
    Use this when a stored memory is wrong or outdated.

    Args:
        id: The memory ID to correct (from memory_recall results).
        new_content: The corrected content.
        source: Optional new source; inherits original source if omitted.
    """
    new_id = update(id, new_content, source=source)
    return f"Memory {id} corrected. New memory: {new_id}"


@mcp.tool()
def memory_confirm(id: str) -> str:
    """Confirm that a memory is still accurate. Resets its decay timer and bumps confidence.
    Call this when you act on a memory and it turns out to be correct.

    Args:
        id: The memory ID to confirm (from memory_recall results).
    """
    mem = confirm(id)
    return (
        f"Memory {id} confirmed.\n"
        f"confidence: {mem.confidence:.2f}\n"
        f"confirmed_count: {mem.confirmed_count}"
    )


@mcp.tool()
def memory_get_stale() -> str:
    """Return memories that have decayed below the confidence floor and need human review.
    Use this to periodically audit and either confirm or forget old memories.
    """
    stale = get_stale()
    if not stale:
        return "No stale memories."
    parts = []
    for mem in stale:
        parts.append(_format_memory(mem))
    return f"{len(stale)} stale memory/memories:\n\n" + "\n\n---\n\n".join(parts)


if __name__ == "__main__":
    mcp.run(transport="stdio")
