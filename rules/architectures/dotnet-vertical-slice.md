## Architecture: vertical slices

One project. Each use case is a folder, `Features/<Feature>/<UseCase>/`, that holds its endpoint,
request, handler and response.

- **VSA-1 [review]** Everything a use case needs lives in its folder: adding a use case adds a folder and touches nothing else.
- **VSA-2 [tool]** A feature never depends on another feature. The architecture tests fail the check otherwise.
- **VSA-3 [review]** Code moves to `Common/` only once three slices need it (DES-4), and each slice owns its data access, with no generic repository layer.
