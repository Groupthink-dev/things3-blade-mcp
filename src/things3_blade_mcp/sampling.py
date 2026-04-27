"""Random sampling helpers for token-efficient LLM workflows.

Instead of dumping hundreds of tasks, sample a manageable batch.
This is the recommended first call for most list views.
"""

from __future__ import annotations

import random


def random_sample(items: list[dict], count: int = 5) -> list[dict]:
    """Return a random sample of items, or all items if fewer than count."""
    if count <= 0:
        return []
    if len(items) <= count:
        return items
    return random.sample(items, count)  # noqa: S311
