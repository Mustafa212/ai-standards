## Architecture: vertical slices

One project. Each use case is a folder, `Features/<Feature>/<UseCase>/`, that holds its endpoint,
request, handler and response. Entities and value objects live in `Domain/`, which every feature uses.

- **VSA-1 [review]** Everything a use case needs lives in its folder: adding a use case adds a folder and touches nothing else.
- **VSA-2 [tool]** A feature never depends on another feature. The architecture tests fail the check otherwise.
- **VSA-3 [review]** Code that two slices of one feature share goes in `Features/<Feature>/Shared/`; it leaves the feature only when it is technical (paging, persistence) or a third feature needs it (DES-4), into a folder named for its job (RDB-10). Requests and responses are never shared between slices, and each slice owns its data access, with no generic repository layer.
- **VSA-4 [review]** A slice starts as plain procedural code in its handler. When the same business rule shows up in a second slice, or a handler works mostly on one entity's data, move that behaviour onto the entity or a value object; a domain service is only for logic across aggregates or an outside call, never a shared service class per feature.
- **VSA-5 [review]** Each slice maps its own endpoint from its folder, onto its feature's route group, and the route group (prefix, authorization, tags) is defined once per feature.
- **VSA-6 [review]** A slice that needs another feature's data reads it with its own query and projection; a side effect in another feature runs through an event that feature handles. A slice never calls another feature's handler (VSA-2).
- **VSA-7 [tool]** `Domain/` never depends on `Features/`. The architecture tests fail the check otherwise.
- **VSA-8 [review]** Each slice is tested end to end through its HTTP endpoint (`WebApplicationFactory`), against a real database once it has one (CS-12). Fake only what the project doesn't own, such as a payment gateway or an e-mail server.
