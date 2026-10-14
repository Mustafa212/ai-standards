{% import "config/settings.jinja" as cfg with context -%}
## Org: example-corp

- **EC-1 [tool]** HTTP calls go only through the internal client ({% if stack == "typescript" %}`@example-corp/http`{% elif stack == "dotnet" %}`ExampleCorp.Http`{% else %}`example_corp.http`{% endif %}). Direct imports of other HTTP libraries are banned by the linter — it gives retries, tracing and auth for free.
- **EC-2 [review]** Every service exposes `GET /healthz` and writes structured JSON logs that include a `request_id`.
- **EC-3 [review]** Any change to a persisted data model needs an ADR in `docs/adr/`.
- **EC-4 [tool]** Coverage target is {{ cfg.coverage_target }}% and complexity limit is {{ cfg.max_complexity }} (stricter than base).
