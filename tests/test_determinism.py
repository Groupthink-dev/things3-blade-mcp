"""DD-338 C W4 determinism harness — envelope-only byte-equal across N=3 invocations.

The Things3 backend is ``deterministic_ordering: unstable`` per the catalog
declaration (the AppleScript bridge does not guarantee a stable inner-list
order; the SQLite-direct rewrite that would enable a ``stable`` declaration is
explicitly out of phasing per DD-338 plan §"Out of phasing — Things3
SQLite-direct rewrite").

What the audit-trail envelope DOES guarantee is byte-equality of the
``_meta`` block across N=3 invocations against the same mocked input.
``filtered_by`` content is computed entirely from tool arguments (no
order-of-iteration sensitivity); ``matched_total`` and ``returned`` are
integer counts; ``latency_ms`` is wall-clock-derived and is therefore
explicitly excluded from the byte-equal comparison.

OQ-8 architect ratification (a): scope determinism harness to the ``_meta``
envelope only. The honest ``unstable`` declaration on the payload remains
the truth-source for body ordering.

OQ-8 also adds a negative-regression test guarding against accidental payload
promotion drift — if a future commit accidentally introduces inner-list
sorting in one of the W4 tools, the existing ``unstable`` declaration would
become a stale lie. The negative test asserts that the W4 tools do NOT
emit a ``sorted_by=`` token in ``filtered_by`` (Things3 has no sort
substrate; mastodon W4 always includes one).
"""

from __future__ import annotations

import json
import re
from unittest.mock import patch

import pytest

from things3_blade_mcp.server import (
    get_random_anytime as _get_random_anytime,
)
from things3_blade_mcp.server import (
    get_random_inbox as _get_random_inbox,
)
from things3_blade_mcp.server import (
    get_random_today as _get_random_today,
)
from things3_blade_mcp.server import (
    get_random_todos as _get_random_todos,
)
from things3_blade_mcp.server import (
    search_advanced as _search_advanced,
)
from things3_blade_mcp.server import (
    search_todos as _search_todos,
)

_META_RE = re.compile(r"\n\n_meta: (\{.*\})$")


def _extract_meta(result: str) -> dict:
    m = _META_RE.search(result)
    assert m is not None, f"no _meta block in:\n{result}"
    return json.loads(m.group(1))


def _strip_latency(meta: dict) -> dict:
    """Drop the wall-clock-derived `latency_ms` field for byte-equal comparison."""
    out = dict(meta)
    out.pop("latency_ms", None)
    return out


# ---------------------------------------------------------------------------
# N=3 envelope-only byte-equal across invocations
# ---------------------------------------------------------------------------


class TestEnvelopeDeterminism:
    """For each W4 tool, assert the _meta envelope (minus latency_ms) is byte-equal across N=3 runs."""

    @patch("things3_blade_mcp.server.things")
    def test_get_random_inbox_envelope_deterministic(self, mock_things):
        mock_things.inbox.return_value = [
            {"uuid": f"id-{i}", "title": f"T{i}", "status": "incomplete"} for i in range(20)
        ]
        mock_things.projects.return_value = []
        envelopes = [_strip_latency(_extract_meta(_get_random_inbox(count=5))) for _ in range(3)]
        assert all(e == envelopes[0] for e in envelopes)

    @patch("things3_blade_mcp.server.get_someday_context", return_value=(set(), {}))
    @patch("things3_blade_mcp.server.things")
    def test_get_random_today_envelope_deterministic(self, mock_things, _mock_ctx):
        mock_things.today.return_value = [
            {"uuid": f"id-{i}", "title": f"T{i}", "status": "incomplete"} for i in range(12)
        ]
        mock_things.projects.return_value = []
        envelopes = [_strip_latency(_extract_meta(_get_random_today(count=3))) for _ in range(3)]
        assert all(e == envelopes[0] for e in envelopes)

    @patch("things3_blade_mcp.server.get_someday_context", return_value=(set(), {}))
    @patch("things3_blade_mcp.server.things")
    def test_get_random_anytime_envelope_deterministic(self, mock_things, _mock_ctx):
        mock_things.anytime.return_value = [
            {"uuid": f"id-{i}", "title": f"T{i}", "status": "incomplete"} for i in range(15)
        ]
        mock_things.projects.return_value = []
        envelopes = [_strip_latency(_extract_meta(_get_random_anytime(count=4))) for _ in range(3)]
        assert all(e == envelopes[0] for e in envelopes)

    @patch("things3_blade_mcp.server.things")
    def test_get_random_todos_envelope_deterministic(self, mock_things):
        mock_things.todos.return_value = [
            {"uuid": f"id-{i}", "title": f"T{i}", "status": "incomplete"} for i in range(8)
        ]
        mock_things.projects.return_value = []
        envelopes = [_strip_latency(_extract_meta(_get_random_todos(project_uuid="p-1", count=3))) for _ in range(3)]
        assert all(e == envelopes[0] for e in envelopes)

    @patch("things3_blade_mcp.server.things")
    def test_search_todos_envelope_deterministic(self, mock_things):
        mock_things.search.return_value = [
            {"uuid": f"id-{i}", "title": f"T{i}", "status": "incomplete"} for i in range(7)
        ]
        mock_things.projects.return_value = []
        envelopes = [_strip_latency(_extract_meta(_search_todos(query="alpha", limit=5))) for _ in range(3)]
        assert all(e == envelopes[0] for e in envelopes)

    @patch("things3_blade_mcp.server.things")
    def test_search_advanced_envelope_deterministic(self, mock_things):
        mock_things.todos.return_value = [
            {"uuid": f"id-{i}", "title": f"T{i}", "status": "incomplete"} for i in range(20)
        ]
        mock_things.projects.return_value = []
        envelopes = [
            _strip_latency(_extract_meta(_search_advanced(status="incomplete", tag="urgent", limit=10)))
            for _ in range(3)
        ]
        assert all(e == envelopes[0] for e in envelopes)


# ---------------------------------------------------------------------------
# Negative-regression: catalog declares deterministic_ordering: unstable for
# things3 W4 tools, so they MUST NOT advertise a `sorted_by=` token (would lie
# about ordering stability). Mastodon W4 always emits one; if a future
# Things3 sweep accidentally copies that pattern it would create stale-lie
# drift between catalog declaration and payload behaviour.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tool_call",
    [
        lambda things, projects: _get_random_inbox(count=3),
        lambda things, projects: _get_random_todos(count=3),
        lambda things, projects: _search_todos(query="x", limit=5),
        lambda things, projects: _search_advanced(status="incomplete", limit=5),
    ],
)
@patch("things3_blade_mcp.server.things")
def test_no_sorted_by_token_emitted(mock_things, tool_call):
    """Negative regression: things3 catalog declares unstable, must NOT lie via sorted_by token."""
    mock_things.inbox.return_value = []
    mock_things.todos.return_value = []
    mock_things.search.return_value = []
    mock_things.projects.return_value = []
    result = tool_call(mock_things, [])
    meta = _extract_meta(result)
    assert not any(f.startswith("sorted_by=") for f in meta["filtered_by"]), (
        f"things3 W4 tool emitted sorted_by= token (would lie about ordering stability): {meta['filtered_by']}"
    )
