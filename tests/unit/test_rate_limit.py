"""Tests for rate limiting middleware utilities."""

import pytest

from docere.middleware.rate_limit import (
    TIER_AUTH,
    TIER_LLM,
    TIER_READ,
    _classify_tier,
    path_tier,
)


class TestClassifyTier:
    def test_chat_endpoint_is_llm_tier(self):
        assert _classify_tier("/api/v1/chat/send") == TIER_LLM

    def test_instructor_query_is_llm_tier(self):
        assert _classify_tier("/api/v1/instructor/dashboard/123/query") == TIER_LLM

    def test_auth_endpoint_is_auth_tier(self):
        assert _classify_tier("/api/v1/auth/login") == TIER_AUTH
        assert _classify_tier("/api/v1/auth/lti/callback") == TIER_AUTH

    def test_courses_is_read_tier(self):
        assert _classify_tier("/api/v1/courses/") == TIER_READ

    def test_students_is_read_tier(self):
        assert _classify_tier("/api/v1/students/profile") == TIER_READ

    def test_instructor_dashboard_is_read_tier(self):
        # Dashboard summary is a read, not an LLM call
        assert _classify_tier("/api/v1/instructor/dashboard/123/summary") == TIER_READ

    def test_health_is_read_tier(self):
        # Health check gets read tier (but middleware skips it anyway)
        assert _classify_tier("/health") == TIER_READ


class TestPathTier:
    def test_llm_tier_name(self):
        assert path_tier("/api/v1/chat/send") == "llm"

    def test_auth_tier_name(self):
        assert path_tier("/api/v1/auth/login") == "auth"

    def test_read_tier_name(self):
        assert path_tier("/api/v1/courses/") == "read"


class TestTierLimits:
    def test_llm_tier_is_strictest_for_requests(self):
        llm_limit, _ = TIER_LLM
        read_limit, _ = TIER_READ
        assert llm_limit < read_limit

    def test_auth_tier_is_strictest(self):
        auth_limit, _ = TIER_AUTH
        llm_limit, _ = TIER_LLM
        assert auth_limit < llm_limit
