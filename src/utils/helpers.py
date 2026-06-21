import json
from typing import Any

def parse_input_to_dict(node_input: Any) -> dict:
    """Parses node_input (dict, str, or types.Content) into a dict."""
    if isinstance(node_input, dict):
        return node_input
    if isinstance(node_input, str):
        try:
            return json.loads(node_input)
        except Exception:
            return {}
            
    # Handle google.genai.types.Content or similar
    if hasattr(node_input, "parts") and node_input.parts:
        text = ""
        for part in node_input.parts:
            if hasattr(part, "text") and part.text:
                text += part.text
        try:
            return json.loads(text)
        except Exception:
            pass
            
    return {}
