from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import numpy as np


class MemoryType(str, Enum):
    USER = "user"
    FEEDBACK = "feedback"
    PROJECT = "project"
    REFERENCE = "reference"


class MemoryStatus(str, Enum):
    ACTIVE = "active"
    CORRECTED = "corrected"
    FORGOTTEN = "forgotten"
    STALE = "stale"  # decayed below confidence floor, pending human review


# Default half-lives in days by memory type
HALF_LIVES: dict[MemoryType, float] = {
    MemoryType.USER: 60.0,
    MemoryType.FEEDBACK: 21.0,
    MemoryType.PROJECT: 30.0,
    MemoryType.REFERENCE: 90.0,
}

# Multiplier on half-life based on confirmed_count (step function)
CONFIRM_DECAY_MULTIPLIERS = [
    (10, 2.0),  # 10+ confirmations → 2× half-life
    (3,  1.5),  # 3–9 confirmations → 1.5× half-life
    (0,  1.0),  # 0–2 confirmations → base half-life
]

CONFIDENCE_FLOOR = 0.1
CONFIRM_BUMP = 1.1  # 10% boost per confirmation, capped at 1.0


@dataclass
class Memory:
    id: str
    type: MemoryType
    content: str
    source: str
    confidence: float
    created_at: datetime
    updated_at: datetime
    status: MemoryStatus = MemoryStatus.ACTIVE
    embedding: Optional[np.ndarray] = field(default=None, repr=False)
    corrected_by: Optional[str] = None    # id of record that corrected this one
    replaced_by: Optional[str] = None     # id of new record replacing this one
    last_confirmed_at: Optional[datetime] = None
    confirmed_count: int = 0
    decay_rate: Optional[float] = None    # per-record override; None = use type default
