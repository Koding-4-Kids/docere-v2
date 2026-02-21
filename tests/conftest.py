"""Shared test fixtures: mock clients, fake DB helpers, sample data."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest


# ── Sample Data ──

@pytest.fixture
def student_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def course_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def conversation_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def sample_student_message() -> str:
    return "I don't understand how recursion works. Can you explain it?"


# ── Mock ClaudeClient ──

class MockClaudeClient:
    """Fake Claude client that returns canned responses."""

    default_model = "mock-claude"

    def __init__(self, chat_response: str = "Here's how recursion works..."):
        self.chat_response = chat_response
        self.judge_response = '{"helpfulness": 0.8, "clarity": 0.7, "engagement": 0.6, "understanding_delta": 0.3}'
        self.chat_calls: list[dict] = []
        self.judge_calls: list[str] = []

    async def chat(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        self.chat_calls.append({
            "system_prompt": system_prompt,
            "messages": messages,
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
        })
        return self.chat_response

    async def judge(self, prompt: str, max_tokens: int = 500) -> str:
        self.judge_calls.append(prompt)
        return self.judge_response


@pytest.fixture
def mock_claude():
    return MockClaudeClient()


# ── Mock QdrantStore ──

class MockQdrantStore:
    """Fake Qdrant that stores vectors in memory."""

    def __init__(self):
        self.collections: dict[str, list[dict]] = {}
        self.search_results: list[dict] = []

    async def ensure_collection(self, collection_name: str) -> None:
        self.collections.setdefault(collection_name, [])

    async def upsert(
        self,
        collection_name: str,
        point_id: str,
        vector: list[float],
        payload: dict,
    ) -> None:
        self.collections.setdefault(collection_name, [])
        self.collections[collection_name].append({
            "id": point_id,
            "vector": vector,
            "payload": payload,
        })

    async def search(
        self,
        collection_name: str,
        query_vector: list[float],
        top_k: int = 5,
        score_threshold: float = 0.6,
        filter_conditions: dict | None = None,
        with_vectors: bool = False,
    ) -> list[dict]:
        return self.search_results[:top_k]

    async def scroll(
        self,
        collection_name: str,
        limit: int = 100,
        with_payload: bool = True,
        with_vectors: bool = False,
    ) -> list[dict]:
        return self.collections.get(collection_name, [])[:limit]

    async def delete_by_ids(self, collection_name: str, point_ids: list[str]) -> None:
        if collection_name in self.collections:
            self.collections[collection_name] = [
                p for p in self.collections[collection_name]
                if p["id"] not in point_ids
            ]

    async def delete(self, collection_name: str, filter_conditions: dict) -> None:
        pass


@pytest.fixture
def mock_qdrant():
    return MockQdrantStore()


# ── Mock AsyncSession (SQLAlchemy) ──

class FakeScalarResult:
    """Mimics the result of a scalar query."""

    def __init__(self, value=None):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalar_one(self):
        if self._value is None:
            raise Exception("No result")
        return self._value

    def scalar(self):
        return self._value

    def scalars(self):
        return self

    def all(self):
        if isinstance(self._value, list):
            return self._value
        return [self._value] if self._value else []

    def first(self):
        return self._value


class MockAsyncSession:
    """Minimal mock of SQLAlchemy AsyncSession for unit tests."""

    def __init__(self):
        self.added: list = []
        self.flushed = False
        self.committed = False
        self._execute_results: list = []
        self._execute_index = 0

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flushed = True

    async def commit(self):
        self.committed = True

    async def get(self, model_class, pk):
        return None

    async def execute(self, stmt):
        if self._execute_index < len(self._execute_results):
            result = self._execute_results[self._execute_index]
            self._execute_index += 1
            return result
        return FakeScalarResult(None)

    def queue_result(self, value):
        """Queue a result for the next execute() call."""
        self._execute_results.append(FakeScalarResult(value))


@pytest.fixture
def mock_db():
    return MockAsyncSession()
