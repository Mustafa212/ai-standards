# expect: E722, S110, T201, PGH004, PTH118
import os


def load(path: str) -> None:
    try:
        print(os.path.join(path, "x"))
    except:
        pass
    value = 1  # noqa
