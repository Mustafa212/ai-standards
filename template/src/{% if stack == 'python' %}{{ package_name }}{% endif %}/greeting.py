DEFAULT_NAME = "world"


def build_greeting(name: str) -> str:
    """Build the greeting shown to the user; a blank name falls back to "world"."""
    trimmed_name = name.strip()
    return f"Hello, {trimmed_name or DEFAULT_NAME}!"
