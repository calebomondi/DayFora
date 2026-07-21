import pytest
from pydantic import ValidationError

from app.agent.schemas import DraftOutput
from app.schemas import DraftReview


def test_draft_requires_valid_provenance() -> None:
    draft = DraftOutput(title="Today", body="I wrote a note.", source_labels=["user_written"])

    assert draft.source_labels == ["user_written"]


def test_draft_rejects_unknown_provenance() -> None:
    with pytest.raises(ValidationError):
        DraftOutput(title="Today", body="I wrote a note.", source_labels=["unknown"])


def test_edit_review_requires_replacement_entry() -> None:
    with pytest.raises(ValidationError):
        DraftReview(action="edit")
