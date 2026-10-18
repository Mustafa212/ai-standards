# expect: D102
"""A public method needs its own docstring (RDB-8)."""


class Invoices:
    """The class has its docstring; its public method doesn't."""

    def add(self, total: int) -> None:
        self.total = total
