"""Markdown content cleanup helpers."""

from __future__ import annotations

import re

FIRST_HEADING = re.compile(r"(?m)^#{1,6}[ \t]+")


def remove_preamble(markdown: str) -> str:
    """Return Markdown beginning at its first ATX heading."""
    heading = FIRST_HEADING.search(markdown)
    if heading is None:
        return ""
    return markdown[heading.start() :].lstrip()
