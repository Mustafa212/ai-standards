## Architecture: Clean Architecture

Projects: `Domain` ← `Application` ← `Infrastructure` and `Api` (each arrow points at what a project
may depend on).

- **CLEAN-1 [tool]** Dependencies point inward: Domain depends on nothing, Application only on Domain, Infrastructure and Api on Application. The architecture tests fail the check otherwise.
- **CLEAN-2 [review]** Domain holds entities, value objects and business rules, with no EF Core, HTTP or framework attributes.
- **CLEAN-3 [review]** Application holds one class per use case, plus the interfaces that Infrastructure implements (repositories, clock, email).
- **CLEAN-4 [review]** Infrastructure implements those interfaces (EF Core, external services); only the Api's composition root references it.
- **CLEAN-5 [review]** The Api is thin: it maps HTTP to use cases, and results to responses.
