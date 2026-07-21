from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from app.agent.tools.supabase import SupabaseTools


@pytest.fixture()
def mock_client() -> MagicMock:
    client = MagicMock()
    return client


@pytest.fixture()
def tools(mock_client: MagicMock) -> SupabaseTools:
    return SupabaseTools(mock_client)


@pytest.fixture()
def sample_state() -> dict[str, Any]:
    return {
        "run_id": "capture:cap-001",
        "user_id": "user-001",
        "entry_id": "entry-001",
        "capture_id": "cap-001",
        "trigger": "capture",
        "local_date": "2026-07-18",
        "capture_type": "text",
        "capture_ids": [],
        "user_preferences": {"id": "user-001", "display_name": "Test", "timezone": "UTC"},
        "active_activities": [
            {"id": "act-001", "title": "Build Week", "purpose": "Ship the app", "status": "active"}
        ],
        "source_text": "I worked on the capture flow today.",
        "transcript": None,
        "image_descriptions": [],
        "draft": None,
        "proposed_activity_update": None,
        "review_decision": None,
        "errors": [],
    }


@pytest.fixture()
def sample_draft() -> dict[str, Any]:
    return {
        "title": "Productive day",
        "body": "I built the capture flow and reviewed the architecture.",
        "mood": "focused",
        "tags": ["build-week"],
        "source_labels": ["user_written", "ai_generated"],
        "proposed_activity_update": {
            "activity_id": "act-001",
            "confidence": 0.85,
            "milestone": "Built capture flow",
            "reason": "User explicitly mentions this work.",
        },
        "reflection_prompt": "What is the smallest next step for authentication?",
    }
