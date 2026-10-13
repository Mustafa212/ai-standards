# expect: PLW1514, B006
from pathlib import Path


def read_lines(path: Path, seen: list[str] = []) -> list[str]:
    with open(path) as handle:
        seen.extend(handle)
    return seen
