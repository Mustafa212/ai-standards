## Architecture: modular monolith

One deployable, `<App>.Host`, that composes modules. Each module is two projects:
`<App>.Modules.<Module>`, its implementation, and `<App>.Modules.<Module>.Contracts`, what other
modules may use (a facade interface, its DTOs, integration events). Pick this when the product has
several bounded contexts or teams in one deployable; extracting a service later starts from a module.

- **MOD-1 [tool]** A module uses another module only through that module's `Contracts` project, and a `Contracts` project uses no module's implementation. The architecture tests fail the check otherwise.
- **MOD-2 [tool]** A module's types are `internal`, except its `<Module>Module` class, through which the host registers the module's services and maps its endpoints. The architecture tests fail the check otherwise.
- **MOD-3 [review]** Each module owns its data: its own `DbContext`, database schema (`HasDefaultSchema("<module>")`) and migrations history table, and no query on another module's tables.
- **MOD-4 [review]** No transaction spans two modules. A change another module must react to is an integration event, declared in the publisher's `Contracts` and delivered through an outbox, so the reaction runs after the publisher's commit.
- **MOD-5 [review]** Data from another module comes through its `Contracts` facade, or from a local read model that its integration events keep current, never by joining its tables.
- **MOD-6 [review]** Inside a module, each use case is a folder, `Features/<Feature>/<UseCase>/`, holding its endpoint, request, handler and response, and a feature never depends on another feature of the module.
- **MOD-7 [review]** A module becomes a separate service only when a measured need asks for it (scaling, a separate team, security or availability). Being extractable is not a reason.
