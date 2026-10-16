# Break shapes: flutter stack rules

What a break of a `[review]` rule usually looks like, for the audit's rule auditors. Never rendered
into AGENTS.md.

## DART-7

- Search: `static final \w+ _?instance\b|static \w+ get instance\b`
- Break: `static final ApiClient instance = ApiClient._();`

## DART-8

- Search: `Widget _build\w*\(`
- Break: `Widget _buildHeader(BuildContext context) {`
