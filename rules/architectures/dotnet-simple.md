## Architecture: simple

One Web API project and its tests. Right for small services; move to `clean` or `vertical-slice`
once the project has more than a handful of features.

- **API-1 [review]** Endpoints stay thin: they map HTTP to a service call, and the result to a response.
- **API-2 [review]** Business logic lives in services named for their domain (`InvoiceService`), in a folder per feature.
