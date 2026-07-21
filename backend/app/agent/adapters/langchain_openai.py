from langchain_groq import ChatGroq

from app.agent.schemas import (
    ActivityRecapOutput,
    DiaryRecapOutput,
    DiaryStoryAnswer,
    DraftOutput,
    SearchRecapOutput,
)

# GOOGLE_MODELS = [
#     "gemini-3.5-flash",
#     "gemini-2.5-flash"
# ]

GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-120b",
    # "openai/gpt-oss-20b"
]


def _memory_model() -> ChatGroq:
    """Return the only model used by the diary-first memory guide.

    Credentials are resolved by LangChain from backend-only environment
    configuration.  This module is never imported by the Expo application.
    """

    return ChatGroq(model="llama-3.3-70b-versatile", temperature=1.0)


def structured_story_answer_model() -> ChatGroq:
    # llama-3.3-70b-versatile supports Groq tool/function calling, while its
    # native json_schema response format is not available on every Groq model.
    return _memory_model().with_structured_output(DiaryStoryAnswer, method="function_calling")


def structured_diary_recap_model() -> ChatGroq:
    return _memory_model().with_structured_output(DiaryRecapOutput, method="function_calling")


def structured_draft_model() -> ChatGroq:
    return ChatGroq(model="llama-3.3-70b-versatile", temperature=1.0).with_structured_output(
        DraftOutput,
        method="json_schema",
    )


def structured_search_recap_model() -> ChatGroq:
    return ChatGroq(model="llama-3.3-70b-versatile", temperature=1.0).with_structured_output(
        SearchRecapOutput,
        method="json_schema",
    )


def structured_activity_recap_model() -> ChatGroq:
    return ChatGroq(model="llama-3.3-70b-versatile", temperature=1.0).with_structured_output(
        ActivityRecapOutput,
        method="json_schema",
    )
