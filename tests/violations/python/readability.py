# expect: PLR0913, PLR2004, PLR1702, ANN001, ANN201, ERA001, D103, FBT001
def process_order(a, b, c, d, e):
    if a > 0:
        for item in range(b):
            if c > 0:
                while d > 0:
                    if e > 86400:
                        return item
    # old_value = process_order(1, 2, 3, 4, 5)
    return 0


def notify(user: str, urgent: bool) -> None:
    ...
