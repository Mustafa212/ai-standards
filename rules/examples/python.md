# Break shapes: python stack rules

What a break of a `[review]` rule usually looks like, for the audit's rule auditors. Never rendered
into AGENTS.md.

## PY-3

- Search: `@dataclass\b`, then keep the lines without `frozen=True`
- Break: `@dataclass` above `class Invoice:`
