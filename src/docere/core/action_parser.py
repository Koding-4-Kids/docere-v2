"""Parse ```action blocks from LLM responses.

Supports action types: draft_email, create_doc, create_sheet,
lms_announcement, calendar_event.
"""

import json
import re

import structlog

logger = structlog.get_logger()

VALID_ACTION_TYPES = {
    "draft_email",
    "create_doc",
    "create_sheet",
    "create_excel",
    "lms_announcement",
    "calendar_event",
}


def extract_actions(response_text: str) -> tuple[str, list[dict]]:
    """Extract all ```action blocks from LLM response.

    Returns:
        (clean_text_without_action_blocks, list_of_action_dicts)
    """
    pattern = r"```action\s*\n(.*?)\n\s*```"
    actions: list[dict] = []
    clean = response_text

    for match in reversed(list(re.finditer(pattern, response_text, re.DOTALL))):
        try:
            raw = match.group(1).strip()
            action = json.loads(raw)
            if "type" not in action:
                logger.warning("Action block missing 'type' field")
                continue
            if action["type"] not in VALID_ACTION_TYPES:
                logger.warning("Unknown action type", type=action["type"])
                continue
            actions.insert(0, action)
            clean = clean[: match.start()] + clean[match.end() :]
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Failed to parse action block", error=str(e))

    return clean.strip(), actions
