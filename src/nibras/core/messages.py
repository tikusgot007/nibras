"""Canonical message format (D-15).

The Agent Core only knows this format. Adapters translate it to the
provider's own format and declare the model's capabilities explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

VALID_ROLES = ("system", "user", "assistant", "tool")


@dataclass
class CanonicalMessage:
    role: str
    content: str
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.role not in VALID_ROLES:
            raise ValueError(f"role tidak dikenal: {self.role!r}")
        if not isinstance(self.content, str):
            raise TypeError("content harus str")


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars per token). Used only for the
    context-window trim; it never leaves the app and is not billed."""
    return max(1, len(text) // 4)
