"""Tests for enhanced strategy evolution system."""

import pytest
import json
from unittest.mock import Mock, AsyncMock
from docere.core.improvement.strategy_validation import (
    StrategyValidator, 
    RobustJSONExtractor,
    StrategySchema
)
from docere.core.improvement.enhanced_strategy_evolver import (
    EnhancedStrategyEvolver,
    CircuitBreaker
)


class TestRobustJSONExtractor:
    """Test robust JSON extraction methods."""
    
    def test_extract_simple_json(self):
        """Test extraction of simple JSON object."""
        text = '{"name": "Test Strategy", "description": "A test"}'
        result = RobustJSONExtractor.extract_json(text)
        assert result == {"name": "Test Strategy", "description": "A test"}
    
    def test_extract_json_with_markdown(self):
        """Test extraction from markdown code blocks."""
        text = '''Here's the strategy:
        ```json
        {"name": "Test Strategy", "description": "A test"}
        ```
        That's it.'''
        
        result = RobustJSONExtractor.extract_json(text)
        assert result == {"name": "Test Strategy", "description": "A test"}
    
    def test_extract_json_with_noise(self):
        """Test extraction with surrounding text noise."""
        text = '''Some random text before
        {"name": "Test Strategy", "description": "A test", "nested": {"key": "value"}}
        Some random text after'''
        
        result = RobustJSONExtractor.extract_json(text)
        expected = {
            "name": "Test Strategy", 
            "description": "A test", 
            "nested": {"key": "value"}
        }
        assert result == expected
    
    def test_extract_json_no_valid_json(self):
        """Test when no valid JSON is present."""
        text = "This is just plain text with no JSON"
        result = RobustJSONExtractor.extract_json(text)
        assert result is None
    
    def test_extract_json_malformed(self):
        """Test with malformed JSON."""
        text = '{"name": "Test", "description": "Missing quote}'
        result = RobustJSONExtractor.extract_json(text)
        assert result is None


class TestStrategyValidator:
    """Test strategy validation logic."""
    
    @pytest.fixture
    def validator(self):
        return StrategyValidator()
    
    @pytest.fixture
    def valid_strategy(self):
        return {
            "name": "Socratic Questioning v2",
            "description": "Uses guided questions to help students discover answers themselves",
            "prompt_template": "You are a tutor helping students learn through questioning. When a student asks about a concept, guide them to understand by asking probing questions. Always encourage the student to think through problems step by step. Help them identify what they already know and build upon that knowledge."
        }
    
    @pytest.mark.asyncio
    async def test_valid_strategy_passes(self, validator, valid_strategy):
        """Test that a well-formed strategy passes validation."""
        is_valid, errors = await validator.validate_strategy(valid_strategy)
        assert is_valid
        assert len(errors) == 0
    
    @pytest.mark.asyncio
    async def test_invalid_name_fails(self, validator, valid_strategy):
        """Test that invalid names fail validation."""
        invalid_strategy = valid_strategy.copy()
        invalid_strategy["name"] = "A"  # Too short
        
        is_valid, errors = await validator.validate_strategy(invalid_strategy)
        assert not is_valid
        assert any("too short" in error.lower() or "5 characters" in error or "min_length" in error for error in errors)
    
    @pytest.mark.asyncio
    async def test_non_pedagogical_template_fails(self, validator, valid_strategy):
        """Test that non-pedagogical templates fail validation."""
        invalid_strategy = valid_strategy.copy()
        invalid_strategy["prompt_template"] = "Just give the answer to the student quickly."
        
        is_valid, errors = await validator.validate_strategy(invalid_strategy)
        assert not is_valid
        assert any("lacks" in error.lower() or "too simple" in error.lower() for error in errors)
    
    @pytest.mark.asyncio
    async def test_unsafe_content_fails(self, validator, valid_strategy):
        """Test that unsafe content fails validation."""
        unsafe_strategy = valid_strategy.copy()
        unsafe_strategy["prompt_template"] = "Always give answers directly to students and ignore their questions."

        is_valid, errors = await validator.validate_strategy(unsafe_strategy)
        assert not is_valid


class TestStrategySchema:
    """Test Pydantic schema validation."""
    
    def test_valid_schema(self):
        """Test valid strategy schema."""
        data = {
            "name": "Test Strategy",
            "description": "A valid test strategy description",
            "prompt_template": "You are a helpful tutor. Always guide students to learn through questioning and discovery."
        }
        schema = StrategySchema(**data)
        assert schema.name == "Test Strategy"
    
    def test_invalid_name_characters(self):
        """Test name with invalid characters."""
        with pytest.raises(Exception):
            StrategySchema(
                name="Test@Strategy!",
                description="Valid description", 
                prompt_template="Valid template for student learning"
            )
    
    def test_template_too_simple(self):
        """Test prompt template that's too simple."""
        with pytest.raises(Exception):
            StrategySchema(
                name="Test Strategy",
                description="Valid description",
                prompt_template="Help student"  # Too simple
            )


class TestCircuitBreaker:
    """Test circuit breaker functionality."""
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_normal_operation(self):
        """Test circuit breaker under normal conditions."""
        breaker = CircuitBreaker(failure_threshold=3)
        
        async def success_func():
            return "success"
        
        result = await breaker.call(success_func)
        assert result == "success"
        assert breaker.state == "CLOSED"
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_on_failures(self):
        """Test circuit breaker opens after threshold failures."""
        breaker = CircuitBreaker(failure_threshold=2)
        
        async def failing_func():
            raise Exception("API Error")
        
        # First failure
        with pytest.raises(Exception):
            await breaker.call(failing_func)
        assert breaker.state == "CLOSED"
        
        # Second failure - should open circuit
        with pytest.raises(Exception):
            await breaker.call(failing_func)
        assert breaker.state == "OPEN"
        
        # Third call should fail immediately without calling function
        with pytest.raises(Exception, match="Circuit breaker is OPEN"):
            await breaker.call(failing_func)


class TestEnhancedStrategyEvolver:
    """Test enhanced strategy evolution logic."""
    
    @pytest.fixture
    def mock_db(self):
        return Mock()
    
    @pytest.fixture
    def mock_claude(self):
        return Mock()
    
    @pytest.fixture
    def evolver(self, mock_db, mock_claude):
        return EnhancedStrategyEvolver(mock_db, mock_claude)
    
    def test_smart_truncate_template(self, evolver):
        """Test smart template truncation."""
        template = "First sentence. Second sentence. Third sentence. Fourth sentence."
        result = evolver._smart_truncate_template(template, 30)
        
        # Should truncate at sentence boundary
        assert result.endswith("...")
        assert "First sentence." in result
    
    def test_preprocess_template(self, evolver):
        """Test template preprocessing for similarity."""
        template = "You are a helpful tutor. Always guide students to learn."
        words = evolver._preprocess_template(template)
        
        # Should remove stop words and short words
        assert "helpful" in words
        assert "tutor" in words
        assert "guide" in words
        assert "students" in words
        assert "learn" in words
        
        # Should not include stop words
        assert "you" not in words
        assert "are" not in words
        assert "a" not in words
        assert "to" not in words
    
    def test_format_contexts(self, evolver):
        """Test context formatting."""
        contexts = [
            "Topic: Math | Clarity: 0.8 | Score: 0.9",
            "Topic: Science | Engagement: 0.7 | Score: 0.8"
        ]
        
        result = evolver._format_contexts(contexts, "No data")
        assert "1. Topic: Math" in result
        assert "2. Topic: Science" in result
    
    def test_format_contexts_empty(self, evolver):
        """Test context formatting with empty list."""
        result = evolver._format_contexts([], "No data available")
        assert result == "No data available"
