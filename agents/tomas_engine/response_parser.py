import json
import re
from typing import Dict, Optional, Any


def extract_action_from_response(response_text: str) -> Optional[Dict[str, Any]]:
    """Extract action JSON from Cerebras response. Handles all possible formats.

    Cerebras can respond in various formats:
    1. Pure JSON: {"selected_action": "left", ...} or {"action_sequence": ["up", "left"], ...}
    2. JSON in code block: ```json\n{"action_sequence": ["up", "left"], ...}\n```
    3. JSON with text: "Here's my decision:\n{"action_sequence": ["up", "left"], ...}"
    4. Just code block: ```\n{"selected_action": "left", ...}\n```

    Args:
        response_text: Raw string response from Cerebras

    Returns:
        Dictionary with parsed action or None if parsing fails
    """
    if not response_text:
        return None

    response_clean = response_text.strip()

    # Method 1: Try direct JSON parsing first (fastest when it works)
    try:
        parsed = json.loads(response_clean)
        if isinstance(parsed, dict) and (
            "selected_action" in parsed or "action_sequence" in parsed
        ):
            return parsed
    except json.JSONDecodeError:
        pass

    # Method 2: Look for JSON in code blocks (multiple patterns)
    code_block_patterns = [
        r"```json\s*(.*?)\s*```",  # ```json ... ```
        r"```\s*(.*?)\s*```",  # ``` ... ```
        r"`(.*?)`",  # ` ... ` (single backticks)
    ]

    for pattern in code_block_patterns:
        json_match = re.search(pattern, response_text, re.DOTALL)
        if json_match:
            try:
                json_str = json_match.group(1).strip()
                parsed = json.loads(json_str)
                if isinstance(parsed, dict) and (
                    "selected_action" in parsed or "action_sequence" in parsed
                ):
                    return parsed
            except json.JSONDecodeError:
                continue

    # Method 3: Smart JSON object extraction (handles nested braces properly)
    json_candidates = []
    brace_count = 0
    start_pos = -1

    for i, char in enumerate(response_text):
        if char == "{":
            if brace_count == 0:
                start_pos = i
            brace_count += 1
        elif char == "}":
            brace_count -= 1
            if brace_count == 0 and start_pos != -1:
                candidate = response_text[start_pos : i + 1]
                json_candidates.append(candidate)
                start_pos = -1

    # Try each candidate, prefer the one with selected_action or action_sequence
    for candidate in json_candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict) and (
                "selected_action" in parsed or "action_sequence" in parsed
            ):
                return parsed
        except json.JSONDecodeError:
            continue

    # Method 4: Regex patterns as last resort
    action_patterns = [
        r'"selected_action":\s*"([^"]+)"',
        r'"action":\s*"([^"]+)"',
        r'selected_action["\']?\s*:\s*["\']?([^"\'",\s]+)["\']?',
    ]

    for pattern in action_patterns:
        match = re.search(pattern, response_text, re.IGNORECASE)
        if match:
            action_value = match.group(1).lower().strip()
            valid_actions = ["up", "down", "left", "right", "space", "click"]
            if action_value in valid_actions:
                return {"selected_action": action_value}

    # Try to extract action_sequence as fallback
    sequence_pattern = r'"action_sequence":\s*\[(.*?)\]'
    sequence_match = re.search(
        sequence_pattern, response_text, re.IGNORECASE | re.DOTALL
    )
    if sequence_match:
        actions_str = sequence_match.group(1)

        # Try to parse as complex actions with coordinates first
        try:
            # Look for objects with action and coordinates
            complex_pattern = r'\{\s*"action":\s*"([^"]+)",\s*"coordinates":\s*\[(\d+),\s*(\d+)\]\s*\}'
            complex_matches = re.findall(complex_pattern, actions_str)
            if complex_matches:
                action_sequence = []
                for action, x, y in complex_matches:
                    valid_actions = ["up", "down", "left", "right", "space", "click"]
                    if action.lower() in valid_actions:
                        action_sequence.append(
                            {"action": action.lower(), "coordinates": [int(x), int(y)]}
                        )
                if action_sequence and len(action_sequence) <= 5:
                    return {"action_sequence": action_sequence}
        except:
            pass

        # Fallback to simple string actions
        action_matches = re.findall(r'"([^"]+)"', actions_str)
        valid_actions = ["up", "down", "left", "right", "space", "click"]
        filtered_actions = [
            action for action in action_matches if action.lower() in valid_actions
        ]
        if filtered_actions and len(filtered_actions) <= 5:
            return {"action_sequence": [action.lower() for action in filtered_actions]}

    return None


def extract_json_from_response(
    response_text: str, fallback_fields: Optional[Dict] = None
) -> Dict[str, Any]:
    """Extract any JSON from response text with fallback options.

    Args:
        response_text: Raw string response from the LLM
        fallback_fields: Default fields to include if parsing fails

    Returns:
        Dictionary with parsed data or fallback fields
    """
    fallback_fields = fallback_fields or {}

    # Try to extract JSON
    extracted = extract_action_from_response(response_text)
    if extracted:
        return extracted

    # If no JSON found, try to extract key information from text
    result = fallback_fields.copy()

    # Look for common patterns
    patterns = {
        "reasoning": r"reasoning:?\s*(.+?)(?:\n|$)",
        "explanation": r"explanation:?\s*(.+?)(?:\n|$)",
        "decision": r"decision:?\s*(.+?)(?:\n|$)",
        "analysis": r"analysis:?\s*(.+?)(?:\n|$)",
    }

    for field, pattern in patterns.items():
        match = re.search(pattern, response_text, re.IGNORECASE | re.MULTILINE)
        if match:
            result[field] = match.group(1).strip()

    # Add the full response if nothing else worked
    if not result:
        result["raw_response"] = response_text.strip()

    return result


def validate_action_response(response_dict: Dict[str, Any]) -> bool:
    """Validate if the response contains a valid action.

    Args:
        response_dict: Parsed response dictionary

    Returns:
        True if response contains valid action data
    """
    if not isinstance(response_dict, dict):
        return False

    # Check for action fields
    action_fields = ["action", "action_id", "id", "command", "type"]
    has_action_field = any(field in response_dict for field in action_fields)

    if not has_action_field:
        return False

    # Validate action value is not empty
    for field in action_fields:
        if field in response_dict:
            value = response_dict[field]
            if value is None or (isinstance(value, str) and not value.strip()):
                return False

    return True


# Example usage and test function
def test_parser():
    """Test the parser with various response formats."""
    test_cases = [
        # JSON in code block
        '```json\n{"action": "up", "confidence": 0.8}\n```',
        # Plain JSON object
        'Based on the analysis, I choose: {"action_id": 2, "reasoning": "best option"}',
        # Text with action
        "After careful consideration, I select action: up",
        # Action number
        "The best action is action 3",
        # Complex text
        'Looking at the patterns, action: "right" seems most appropriate because...',
    ]

    for i, test in enumerate(test_cases):
        print(f"\nTest {i+1}: {test}")
        result = extract_action_from_response(test)
        print(f"Result: {result}")
        print(f"Valid: {validate_action_response(result) if result else False}")


if __name__ == "__main__":
    test_parser()
