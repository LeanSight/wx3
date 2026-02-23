"""
Parse speaker name mappings from CLI string format.
"""

from typing import Dict


def parse_speakers_map(raw) -> Dict[str, str]:
    """
    Parse 'A=Marcel,B=Agustin' -> {'A': 'Marcel', 'B': 'Agustin'}.
    Uses partition so values may contain '='. Tokens without '=' are skipped.
    Returns empty dict for None or empty input.
    """
    if not raw:
        return {}

    result: Dict[str, str] = {}
    for token in raw.split(","):
        key, sep, value = token.strip().partition("=")
        if sep:
            result[key.strip()] = value.strip()

    return result
