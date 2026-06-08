"""Strategy validation framework for ensuring generated strategies are robust."""

import json
import re
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator
import structlog

logger = structlog.get_logger()


class StrategySchema(BaseModel):
    """Pydantic schema for validating generated strategies."""

    name: str = Field(..., min_length=5, max_length=100)
    description: str = Field(..., min_length=10, max_length=500)
    prompt_template: str = Field(..., min_length=50, max_length=2000)

    @validator("name")
    def validate_name(cls, v):
        if not re.match(r"^[a-zA-Z0-9\s\-_()]+$", v):
            raise ValueError("Strategy name contains invalid characters")
        return v

    @validator("prompt_template")
    def validate_prompt_template(cls, v):
        # Check for basic pedagogical structure
        required_elements = ["student", "learn", "understand", "explain"]
        if not any(element in v.lower() for element in required_elements):
            raise ValueError("Prompt template lacks pedagogical language")

        # Check for reasonable length and structure
        if len(v.split(".")) < 3:
            raise ValueError("Prompt template too simple - needs more structure")

        return v


class StrategyValidator:
    """Validates generated strategies before activation."""

    def __init__(self):
        self.validation_rules = [
            self._validate_schema,
            self._validate_pedagogical_coherence,
            self._validate_prompt_structure,
            self._validate_safety,
        ]

    async def validate_strategy(self, strategy_data: Dict[str, Any]) -> tuple[bool, List[str]]:
        """Validate a strategy and return (is_valid, error_messages)."""
        errors = []

        for rule in self.validation_rules:
            try:
                is_valid, error = await rule(strategy_data)
                if not is_valid:
                    errors.append(error)
            except Exception as e:
                errors.append(f"Validation error: {str(e)}")

        is_valid = len(errors) == 0
        return is_valid, errors

    async def _validate_schema(self, strategy_data: Dict[str, Any]) -> tuple[bool, str]:
        """Validate against Pydantic schema."""
        try:
            StrategySchema(**strategy_data)
            return True, ""
        except Exception as e:
            return False, f"Schema validation failed: {str(e)}"

    async def _validate_pedagogical_coherence(
        self, strategy_data: Dict[str, Any]
    ) -> tuple[bool, str]:
        """Check if strategy has pedagogical coherence."""
        template = strategy_data.get("prompt_template", "").lower()

        # Check for student-centered language
        student_indicators = ["student", "learner", "you are learning"]
        if not any(indicator in template for indicator in student_indicators):
            return False, "Strategy lacks student-centered language"

        # Check for teaching verbs
        teaching_verbs = ["explain", "teach", "guide", "help", "clarify", "demonstrate"]
        if not any(verb in template for verb in teaching_verbs):
            return False, "Strategy lacks teaching-oriented verbs"

        return True, ""

    async def _validate_prompt_structure(self, strategy_data: Dict[str, Any]) -> tuple[bool, str]:
        """Check prompt template structure."""
        template = strategy_data.get("prompt_template", "")

        # Check for reasonable sentence structure
        sentences = template.split(".")
        if len(sentences) < 2:
            return False, "Prompt template lacks proper sentence structure"

        # Check for instruction clarity
        if not any(word in template.lower() for word in ["should", "must", "will", "always"]):
            return False, "Prompt template lacks clear instructions"

        return True, ""

    async def _validate_safety(self, strategy_data: Dict[str, Any]) -> tuple[bool, str]:
        """Check for safety and appropriateness."""
        template = strategy_data.get("prompt_template", "").lower()

        # Check for inappropriate content patterns
        inappropriate_patterns = [
            "give answers",
            "provide solutions",
            "tell them the answer",
            "just say",
            "ignore",
            "harmful",
        ]

        for pattern in inappropriate_patterns:
            if pattern in template:
                return False, f"Strategy contains inappropriate pattern: '{pattern}'"

        return True, ""


class RobustJSONExtractor:
    """Robust JSON extraction from LLM responses."""

    @staticmethod
    def extract_json(text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from text with multiple fallback methods."""
        methods = [
            RobustJSONExtractor._extract_with_markers,
            RobustJSONExtractor._extract_with_regex,
            RobustJSONExtractor._extract_first_complete_object,
        ]

        for method in methods:
            try:
                result = method(text)
                if result:
                    return result
            except Exception:
                continue

        return None

    @staticmethod
    def _extract_with_markers(text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON using start/end markers."""
        # Remove markdown code fences
        text = re.sub(r"```json\n?", "", text)
        text = re.sub(r"```\n?", "", text)

        # Find JSON object boundaries
        json_start = text.find("{")
        if json_start == -1:
            return None

        # Find matching closing brace
        brace_count = 0
        for i, char in enumerate(text[json_start:], json_start):
            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0:
                    json_text = text[json_start : i + 1]
                    return json.loads(json_text)

        return None

    @staticmethod
    def _extract_with_regex(text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON using regex patterns."""
        # Pattern for JSON object
        pattern = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
        matches = re.findall(pattern, text, re.DOTALL)

        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue

        return None

    @staticmethod
    def _extract_first_complete_object(text: str) -> Optional[Dict[str, Any]]:
        """Extract first complete JSON object."""
        # Find all potential JSON starts
        for start_pos in range(len(text)):
            if text[start_pos] == "{":
                # Try to parse from this position
                for end_pos in range(start_pos + 1, len(text) + 1):
                    try:
                        candidate = text[start_pos:end_pos]
                        result = json.loads(candidate)
                        if isinstance(result, dict):
                            return result
                    except json.JSONDecodeError:
                        continue

        return None
