"""Shared test fixtures."""

import pytest


@pytest.fixture
def sample_student_message() -> str:
    """Sample student message for testing."""
    return "I don't understand how recursion works. Can you explain it?"


@pytest.fixture
def sample_course_id() -> str:
    """Sample course ID for testing."""
    return "test-course-001"
