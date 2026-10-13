DEFAULT_NAME = "world"


def build_greeting(name: str) -> str:
    trimmed_name = name.strip()
    return f"Hello, {trimmed_name or DEFAULT_NAME}!"
