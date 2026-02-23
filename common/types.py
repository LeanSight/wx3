"""
Shared types for wx4 modules.
"""

from typing import Literal, Optional, Tuple

try:
    from typing import TypedDict
except ImportError:
    from typing_extensions import TypedDict


class Chunk(TypedDict):
    text: str
    timestamp: Tuple[float, float]
    speaker: Optional[str]


GroupingMode = Literal["sentences", "speaker-only"]
