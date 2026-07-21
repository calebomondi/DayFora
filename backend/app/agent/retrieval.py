"""Bounded hybrid retrieval helpers for diary title/body search.

The first retrieval stage is deliberately local and deterministic: exact token
matches are combined with character-similarity matches.  This makes natural
queries useful immediately (for example, ``hackathon`` can retrieve a saved
``buildathon`` entry) without sending a user's diary to an LLM.  A semantic
provider can contribute additional candidates through ``semantic_scores``;
ownership, approval, and visible filters are still applied by the caller.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Iterable, Mapping

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)?", re.IGNORECASE)

# Query framing words should not prevent a relevant diary match.  This is not
# used to rewrite or infer the user's question; it only removes grammatical
# glue before matching visible title/body text.
_STOPWORDS = frozenset(
    "a an and are about as at be been can did do does for from had has have how i in is it me my of on or that the this to was what when where which who why with you your".split()
)


def retrieval_tokens(value: str | None) -> list[str]:
    """Return stable lowercase search tokens, excluding query stopwords."""

    return [
        token.casefold()
        for token in _TOKEN_RE.findall(value or "")
        if token.casefold() not in _STOPWORDS and len(token) > 1
    ]


def _token_similarity(query_token: str, document_token: str) -> float:
    if query_token == document_token:
        return 1.0
    if query_token.startswith(document_token) or document_token.startswith(query_token):
        return 0.88
    if len(query_token) < 4 or len(document_token) < 4:
        return 0.0
    return SequenceMatcher(None, query_token, document_token).ratio()


def hybrid_text_score(query: str, text: str) -> float:
    """Score exact and close token matches in ``text`` from 0.0 to 1.0."""

    query_tokens = retrieval_tokens(query)
    if not query_tokens:
        return 0.0
    document_tokens = retrieval_tokens(text)
    if not document_tokens:
        return 0.0
    matched = [
        max((_token_similarity(query_token, token) for token in document_tokens), default=0.0)
        for query_token in query_tokens
    ]
    # Requiring a meaningful match for at least one token avoids returning an
    # unrelated entry when a user asks about a term absent from their diary.
    strongest = max(matched, default=0.0)
    if strongest < 0.5:
        return 0.0
    return sum(matched) / len(matched)


def hybrid_entry_score(entry: Mapping[str, Any], query: str, *, title_only: bool = False) -> float:
    """Combine title/body lexical scores with a small title relevance boost."""

    title_score = hybrid_text_score(query, str(entry.get("title") or ""))
    if title_only:
        return title_score
    body_score = hybrid_text_score(query, str(entry.get("body") or ""))
    if not title_score and not body_score:
        return 0.0
    if title_score and body_score:
        return min(1.0, title_score * 0.65 + body_score * 0.35)
    return title_score or body_score * 0.75


def rank_hybrid_entries(
    rows: Iterable[Mapping[str, Any]],
    query: str | None,
    *,
    title_only: bool = False,
    semantic_scores: Mapping[str, float] | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Rank already-authorized rows using lexical and optional semantic scores.

    ``semantic_scores`` is keyed by entry id and is intentionally only a score
    contribution.  It cannot introduce records that were not already returned
    by the ownership/status/date/mood query.
    """

    materialized = [dict(row) for row in rows]
    if query is None:
        return materialized[:limit]
    if not retrieval_tokens(query):
        return []
    semantic = semantic_scores or {}
    ranked: list[tuple[float, int, dict[str, Any]]] = []
    for index, row in enumerate(materialized):
        lexical = hybrid_entry_score(row, query, title_only=title_only)
        semantic_score = max(0.0, min(1.0, float(semantic.get(str(row.get("id")), 0.0))))
        # Exact/close lexical evidence remains the primary signal.  Semantic
        # candidates can rescue vocabulary mismatches but cannot overpower a
        # clearly unrelated result.
        score = lexical * 0.6 + semantic_score * 0.4
        if score >= 0.32:
            ranked.append((score, index, row))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [row for _, _, row in ranked[:limit]]
