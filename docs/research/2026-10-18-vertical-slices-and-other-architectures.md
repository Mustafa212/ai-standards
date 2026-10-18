# Vertical slice practices, and which other architectures to offer

Date: 2026-10-18 · Status: **approved by the owner on 2026-10-18**. The rules are applied in 0.18.0;
the modular monolith and the move to ArchUnitNET come as their own changes.

## 1. Vertical slice rules and their sources

| Rule | What it says | Sources | Disagreement |
| --- | --- | --- | --- |
| VSA-3 (amended) | Two slices of one feature share through `Features/<Feature>/Shared/`; code leaves the feature only when technical or at the third feature, into a folder named for its job; requests and responses are never shared | [Jovanović, where shared logic lives](https://milanjovanovic.tech/blog/vertical-slice-architecture-where-does-the-shared-logic-live) ("A `Common` project inevitably becomes a junk drawer"); [Steve Smith, feature slices](https://learn.microsoft.com/en-us/archive/msdn-magazine/2016/september/asp-net-core-feature-slices-for-asp-net-core-mvc) | None |
| VSA-4 | Start as a transaction script; push a rule that repeats, or feature envy, onto the entity; a domain service only across aggregates or for an outside call | [Bogard, vertical slices](https://www.jimmybogard.com/vertical-slice-architecture/); [Bogard, pushing behavior down](https://jimmybogard.com/domain-driven-refactoring-defactoring-and-pushing-behavior-down); [Bogard, domain services](https://jimmybogard.com/domain-driven-refactoring-extracting-domain-services/); Jovanović (above) | Bogard warns it needs a team that refactors |
| VSA-5 | Each slice maps its own endpoint onto its feature's route group, defined once | [Microsoft, route groups](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/minimal-apis/route-handlers); [REPR pattern](https://deviq.com/design-patterns/repr-design-pattern); [Jovanović, IEndpoint](https://www.milanjovanovic.tech/blog/automatically-register-minimal-apis-in-aspnetcore) | The mechanism (explicit, scanning, Carter, FastEndpoints) varies; the rule names none |
| VSA-6 | Read another feature's data with your own query; react to it through an event; never call its handler | Jovanović (above); [Comartin, coupling per feature](https://codeopinion.com/?p=10468) | Comartin: events remove temporal coupling, not coupling, so events stay for real side effects |
| VSA-7 [tool] | `Domain/` never depends on `Features/` | Jovanović (above): slices "can share the same domain model"; Smith (above) | None |
| VSA-8 | Test each slice through its endpoint, against a real database; fake only what you don't own | [Jovanović, testing vertical slices](https://milanjovanovic.tech/blog/testing-vertical-slices-dotnet); [EF Core, testing strategy](https://learn.microsoft.com/en-us/ef/core/testing/choosing-a-testing-strategy); [ASP.NET Core integration tests](https://learn.microsoft.com/en-us/aspnet/core/test/integration-tests) | Wolverine prefers pure handler unit tests; the EF team calls the in-memory provider "highly discouraged" |
| RDB-12 (base) | Name use cases and endpoints for the business intent, not the data change | [Azure, CQRS pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/cqrs) ("Book hotel room", not "Set ReservationStatus to Reserved"); [Uncle Bob, Screaming Architecture](https://blog.cleancoder.com/uncle-bob/2011/09/30/Screaming-Architecture.html) | "A feature per business capability, not per entity" is contested (Smith and Jovanović group by entity), so it is left out |

RDB-12 went to the base rules: the same text in two architecture files would be a duplicate, and it
holds for every architecture.

Left out: "no mediator by default". Bogard still uses MediatR at the edges of vertical slices
([2022](https://www.jimmybogard.com/you-probably-dont-need-to-worry-about-mediatr/)), so it is
contested; CLEAN-10's idea (handlers never call each other) is already VSA-2 and VSA-6 here.

## 2. Other architectures

| Architecture | Verdict | Why |
| --- | --- | --- |
| Modular monolith | **Add**, as its own template | The only one that adds something new: module boundaries and data ownership above whatever each module does inside. [Kamil Grzybek](https://github.com/kgrzybek/modular-monolith-with-ddd), [Jovanović](https://milanjovanovic.tech/blog/modular-monolith-architecture-dotnet), [Ardalis.Modulith](https://www.nuget.org/packages/Ardalis.Modulith). Its rules: a `DbContext` and schema per module; only a `Contracts` assembly is public; no transaction across modules (integration events with an outbox); cross-module reads through the public API or a local read model; architecture tests on module references; extract a module into a service only under measured pressure |
| Hexagonal, Onion | Reject, one line in the clean rules | [Microsoft's architecture guide](https://learn.microsoft.com/en-us/dotnet/architecture/modern-web-apps-azure/common-web-application-architectures) names them as the same style as Clean; [Palermo](https://jeffreypalermo.com/2008/07/the-onion-architecture-part-1/) says Onion shares Hexagonal's premise |
| Microservices | Reject as a template | A deployment topology, not a code structure; each service is a simple, clean or sliced app. [Fowler, MonolithFirst](https://martinfowler.com/bliki/MonolithFirst.html), [Microservice Premium](https://martinfowler.com/bliki/MicroservicePremium.html); [Azure, microservices style](https://learn.microsoft.com/en-us/azure/architecture/guide/architecture-styles/microservices). The usual path is to extract a module of a modular monolith |
| CQRS with event sourcing | Reject as a top-level template | A pattern for part of a system: [Fowler, CQRS](https://martinfowler.com/bliki/CQRS.html); [Azure, event sourcing](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing) ("For most systems … traditional data management is sufficient") |

## 3. Tooling

NetArchTest.Rules hasn't released since 1.3.2 (May 2021);
[ArchUnitNET](https://www.nuget.org/packages/TngTech.ArchUnitNET) is active. The architecture tests
moved to it in 0.20.0, before the modular monolith template, which needs module rules.
