from __future__ import annotations

import logging
import os
from datetime import date
from typing import Any, Callable
from urllib.parse import quote, urlsplit, urlunsplit

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph

from app.agent.state import DayForaAgentState

log = logging.getLogger(__name__)

_saver_context: Any | None = None
_saver: BaseCheckpointSaver | None = None

_SOURCE_KEYS = {"id", "local_date", "title", "body", "mood"}
_FILTER_KEYS = {"query", "date_from", "date_to", "mood", "media_type", "entry_ids"}


def build_memory_graph(
    synthesize: Callable[[DayForaAgentState], dict[str, Any]],
    checkpointer: BaseCheckpointSaver | None = None,
) -> Any:
    """Build the two explicitly-invoked v1 workflows.

    Retrieval is completed and ownership-validated by FastAPI before this graph
    receives state.  No media paths, URLs, binary content, or history outside
    that verified source set can enter the graph.
    """

    def validate(state: DayForaAgentState) -> dict[str, Any]:
        if state.get("trigger") not in {"ask_diary", "recap"}:
            return {"errors": ["Unsupported memory workflow"]}
        if not state.get("user_id"):
            return {"errors": ["Missing authenticated user"]}
        if not state.get("run_id"):
            return {"errors": ["Missing idempotent run ID"]}
        if state.get("trigger") == "ask_diary" and not str(state.get("query") or "").strip():
            return {"errors": ["Ask-your-diary requires a question"]}
        if state.get("trigger") == "recap":
            period = state.get("period") or {}
            try:
                if not period.get("start") or not period.get("end"):
                    raise ValueError
                if date.fromisoformat(period["start"]) > date.fromisoformat(period["end"]):
                    raise ValueError
            except (TypeError, ValueError):
                return {"errors": ["Recap requires an ordered visible date period"]}
        return {}

    def resolve_query_to_visible_filters(state: DayForaAgentState) -> dict[str, Any]:
        """Keep only user-visible filter fields in checkpointed graph state."""

        filters = {
            key: value
            for key, value in (state.get("filters") or {}).items()
            if key in _FILTER_KEYS and value not in (None, "", [])
        }
        return {"filters": filters}

    def retrieve_verified_matching_entries(state: DayForaAgentState) -> dict[str, Any]:
        """Accept the FastAPI ownership-verified scope and strip unsafe fields.

        Database retrieval intentionally happens before graph invocation.  This
        keeps the graph free of a service-role client and ensures media paths,
        signed URLs, and binary content cannot reach model synthesis.
        """

        entries: list[dict[str, Any]] = []
        for row in state.get("source_entries") or []:
            if not isinstance(row, dict) or not _SOURCE_KEYS.issuperset(row.keys()):
                return {"errors": ["Invalid diary source scope"]}
            entry_id = str(row.get("id") or "")
            local_date = str(row.get("local_date") or "")
            title = str(row.get("title") or "").strip()
            try:
                date.fromisoformat(local_date)
            except ValueError:
                return {"errors": ["Invalid diary source date"]}
            if not entry_id or not title:
                return {"errors": ["Invalid diary source scope"]}
            entries.append(
                {
                    "id": entry_id,
                    "local_date": local_date,
                    "title": title,
                    "body": (str(row["body"]) if row.get("body") is not None else None),
                    "mood": (str(row["mood"]) if row.get("mood") is not None else None),
                }
            )
        if not entries or (state.get("trigger") == "recap" and len(entries) < 2):
            if state.get("trigger") == "recap":
                return {"result": {"status": "insufficient_material"}, "source_entries": []}
            return {"errors": ["No verified source entries"]}
        return {"source_entries": entries[:20]}

    def synthesize_structured(state: DayForaAgentState) -> dict[str, Any]:
        return {"result": synthesize(state)}

    def validate_sources(state: DayForaAgentState) -> dict[str, Any]:
        result = state.get("result") or {}
        if result.get("status") == "insufficient_material":
            return {}
        allowed = {str(entry["id"]) for entry in state.get("source_entries", [])}
        returned = {str(entry_id) for entry_id in result.get("source_entry_ids", [])}
        if not returned or not returned.issubset(allowed):
            return {"errors": ["Agent returned an unverified source"]}
        highlight_ids = {
            str(highlight.get("entry_id"))
            for highlight in result.get("highlights", [])
            if isinstance(highlight, dict)
        }
        if not highlight_ids.issubset(returned):
            return {"errors": ["Agent returned an unverified highlight source"]}
        return {}

    graph = StateGraph(DayForaAgentState)
    graph.add_node("validate_request", validate)
    graph.add_node("resolve_query_to_visible_filters", resolve_query_to_visible_filters)
    graph.add_node("retrieve_verified_matching_entries", retrieve_verified_matching_entries)
    graph.add_node("synthesize_structured_answer", synthesize_structured)
    graph.add_node("validate_returned_source_ids", validate_sources)

    graph.add_edge(START, "validate_request")
    graph.add_conditional_edges(
        "validate_request",
        lambda state: END if state.get("errors") else "resolve_query_to_visible_filters",
    )
    graph.add_edge("resolve_query_to_visible_filters", "retrieve_verified_matching_entries")
    graph.add_conditional_edges(
        "retrieve_verified_matching_entries",
        lambda state: (
            END
            if state.get("errors")
            or (state.get("result") or {}).get("status") == "insufficient_material"
            else "synthesize_structured_answer"
        ),
    )
    graph.add_edge("synthesize_structured_answer", "validate_returned_source_ids")
    graph.add_edge("validate_returned_source_ids", END)
    
    return graph.compile(checkpointer=checkpointer or configured_checkpointer())


def configured_checkpointer() -> BaseCheckpointSaver | None:
    """Lazily initialize the deployed PostgreSQL checkpoint store.

    A missing or temporarily unreachable checkpoint database must not make a
    user's read-only Ask/recap request fail. The workflow still validates its
    sources and remains request-scoped; deployed environments with a valid
    ``LANGGRAPH_DATABASE_URL`` get durable recovery automatically.
    """

    global _saver, _saver_context
    if _saver is not None:
        return _saver
    connection_strings = _checkpoint_connection_strings()
    if not connection_strings:
        return None
    for connection_string in connection_strings:
        context: Any | None = None
        try:
            context = PostgresSaver.from_conn_string(connection_string)
            saver = context.__enter__()
            saver.setup()
            _saver_context = context
            _saver = saver
            return saver
        except Exception as error:
            log.warning("LangGraph checkpoint store unavailable (%s)", type(error).__name__)
            if context is not None:
                try:
                    context.__exit__(None, None, None)
                except Exception:
                    pass
    _saver_context = None
    _saver = None
    return None


def _checkpoint_connection_strings() -> list[str]:
    """Build backend-only checkpoint URLs, preferring explicit configuration.

    Supabase projects can expose a direct database hostname that is not
    reachable from an IPv4-only network.  The optional pooler variables in
    ``.env`` provide a safe fallback without changing the mobile contract.
    """

    direct = os.getenv("LANGGRAPH_DATABASE_URL", "").strip()
    urls = [direct] if direct else []
    pooler_host = os.getenv("LANGGRAPH_SUPABASE_POOLER_HOST", "").strip()
    if not (direct and pooler_host):
        return urls
    parsed = urlsplit(direct)
    if not parsed.username or parsed.password is None:
        return urls
    pooler_port = os.getenv("LANGGRAPH_SUPABASE_POOLER_PORT", "5432").strip()
    pooler_netloc = (
        f"{quote(parsed.username)}:{quote(parsed.password, safe='')}@{pooler_host}:{pooler_port}"
    )
    pooler_url = urlunsplit((parsed.scheme, pooler_netloc, parsed.path or "/postgres", "", ""))
    if pooler_url != direct:
        urls.append(pooler_url)
    return urls


def close_checkpointer() -> None:
    """Close the lazily-created durable saver during FastAPI shutdown."""

    global _saver, _saver_context
    if _saver_context is not None:
        try:
            _saver_context.__exit__(None, None, None)
        except Exception:
            pass
    _saver_context = None
    _saver = None


def build_graph(*_args: Any, **_kwargs: Any) -> Any:
    """Retired capture graph guard.

    Kept only so an old import fails safely rather than processing private media.
    The v1 API uses ``build_memory_graph`` exclusively.
    """
    raise RuntimeError("Capture-to-draft processing is retired in diary-first v1")
