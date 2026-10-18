# Clean Architecture practices, and when to use CQRS and a mediator

Date: 2026-10-18 · Status: **approved by the owner on 2026-10-18**, applied in 0.17.0.

The Clean Architecture rules had five lines (CLEAN-1 to CLEAN-5): the layers and their direction.
They said nothing about what keeps the code inside the layers readable, and the template never
asked whether a project should use CQRS or a mediator, which teams pick by habit.

## 1. New rules and their sources

| Rule | What it says | Sources | Disagreement |
| --- | --- | --- | --- |
| CLEAN-6 [tool] | Application never references ASP.NET Core; the caller comes through a port (`ICurrentUser`) | [Uncle Bob, The Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html) ("Independent of Frameworks"); [Jason Taylor's template](https://github.com/jasontaylordev/CleanArchitecture/tree/main/src/Application/Common/Interfaces) (`IUser`) | None |
| CLEAN-7 [review] | An entity with rules changes state only through methods that check its invariants | [Fowler, AnemicDomainModel](https://martinfowler.com/bliki/AnemicDomainModel.html); [Microsoft, domain model](https://learn.microsoft.com/en-us/dotnet/architecture/microservices/microservice-ddd-cqrs-patterns/microservice-domain-model) | The same Microsoft page accepts an anemic model for plain CRUD, hence "an entity with no rules may stay plain" |
| CLEAN-8 [review] | Change children through the aggregate root; refer to other aggregates by ID | Microsoft (same page): "only having the foreign key (FK) field"; Vernon, *Effective Aggregate Design* ("Reference Other Aggregates by Identity") | "One aggregate per transaction" is disputed (Bogard, Microsoft's domain-events page), so it is left out; CS-21 covers the transaction |
| CLEAN-9 [review] | Cross-cutting work runs once in a pipeline, decorator or filter | [van Deursen, the command side](https://blogs.cuttingedge.it/steven/posts/2011/meanwhile-on-the-command-side-of-my-architecture/); [Microsoft, application layer](https://learn.microsoft.com/en-us/dotnet/architecture/microservices/microservice-ddd-cqrs-patterns/microservice-application-layer-implementation-web-api) | None |
| CLEAN-10 [tool] | A use case never calls another use case or the mediator | [Bogard, duplication in MediatR handlers](https://lostechies.com/jimmybogard/2016/12/12/dealing-with-duplication-in-mediatr-handlers/) ("it gets quite confusing"); [Bogard 2022](https://jimmybogard.com/you-probably-dont-need-to-worry-about-mediatr/) (send only from the edges) | None |
| CLEAN-11 [review] | One data-access approach per project, written down; no repository per table, no generic `IRepository<T>` returning `IQueryable` | [Microsoft, persistence layer](https://learn.microsoft.com/en-us/dotnet/architecture/microservices/microservice-ddd-cqrs-patterns/infrastructure-persistence-layer-design) ("Repositories shouldn't be mandatory"); [EF Core testing strategy](https://learn.microsoft.com/en-us/ef/core/testing/choosing-a-testing-strategy); [Taylor ADR-001](https://github.com/jasontaylordev/CleanArchitecture/blob/main/docs/decisions/ADR-001-Use-EFCore-In-Application-Layer.md); [Ardalis design decisions](https://ardalis.github.io/CleanArchitecture/design-decisions/) | Real: Taylor uses the context, Ardalis repositories. So the rule asks for one choice, not a winner |
| CLEAN-12 [review] | Interfaces only at real boundaries | [Seemann, Interfaces are not abstractions](https://blog.ploeh.dk/2010/12/02/Interfacesarenotabstractions/); [Bogard, vertical slices](https://www.jimmybogard.com/vertical-slice-architecture/) | A mocking-heavy test style wants more interfaces; CS-12 already prefers a real database |
| CLEAN-13 [review] | Organize Application by feature, a folder per use case | [Bogard, vertical slices](https://www.jimmybogard.com/vertical-slice-architecture/) ("maximize coupling in a slice"); Taylor's and Ardalis's templates | Taylor nests `Commands/`/`Queries/` inside a feature, which the rule allows; folders by technical type across features are what it forbids |
| CLEAN-14 [review] | (CQRS styles) a request is a command or a query, one handler; one database | [Fowler, CommandQuerySeparation](https://martinfowler.com/bliki/CommandQuerySeparation.html); [Azure, CQRS pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/cqrs) | "Commands return nothing" is disputed ([Seemann](https://blog.ploeh.dk/2014/08/11/cqs-versus-server-generated-ids/)), so the rule doesn't require it |

Left out: domain events (optional until real cross-aggregate side effects exist, DES-4), strongly
typed IDs (contested; DES-3 covers the intent), Hexagonal and Onion as separate architectures
(Microsoft's [architecture guide](https://learn.microsoft.com/en-us/dotnet/architecture/modern-web-apps-azure/common-web-application-architectures)
names them as the same style as Clean).

## 2. CQRS and a mediator: the `use_cases` question

- **CQRS at its lightest** is two models where there was one, in one database
  ([CQRS Journey](https://learn.microsoft.com/en-us/previous-versions/msp-n-p/jj591573(v=pandp.10))).
  Separate stores and event sourcing add synchronization and eventual consistency, and suit only
  some bounded contexts ([Fowler, CQRS](https://martinfowler.com/bliki/CQRS.html): "for most
  systems CQRS adds risky complexity"; [Azure, CQRS pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/cqrs)).
- **A mediator** adds in-process dispatch and a pipeline for cross-cutting work
  ([MediatR](https://github.com/jbogard/MediatR)). Its cost is indirection that hides a handler's
  real dependencies ([Hannen](https://dev.to/scotthannen/no-mediatr-didnt-run-over-my-dog-3ngc);
  [Jovanović](https://www.milanjovanovic.tech/blog/stop-conflating-cqrs-and-mediatr)).
- **Licence:** MediatR 13.0 (July 2025) and later are RPL-1.5 or a Lucky Penny commercial licence;
  12.5.0 is the last Apache-2.0 release. The Community edition is free under $5M revenue but
  still needs a registered key ([Bogard](https://www.jimmybogard.com/automapper-and-mediatr-commercial-editions-launch-today/)).
  The template uses [Mediator](https://github.com/martinothamar/Mediator) (MIT, source-generated,
  3.0.2), which Ardalis's template moved to as well.

| Choice | Pick it when | Basis |
| --- | --- | --- |
| `plain` (default) | CRUD, simple rules, HTTP the only way in | Azure's "not suitable" list; Fowler |
| `handlers` | Cross-cutting work must also wrap jobs or consumers; Go-to-Definition; no licence | van Deursen; Jovanović |
| `mediator` | Many pipeline behaviors, or notifications with several handlers | Microsoft application layer; Bogard 2022 |
| Never a default | A separate read store, event sourcing | Fowler; Azure; CQRS Journey |

## 3. Template and enforcement

- `copier.yml` asks `use_cases` for dotnet `clean`. Each style renders its own example use case,
  `Features/Greetings/BuildGreeting/`, and its own wording of CLEAN-9, CLEAN-10 and CLEAN-13.
- `UseCaseIsolationTests` enforces CLEAN-10, plus "never send through the mediator" for
  `mediator`, and `DependencyDirectionTests` enforces CLEAN-6. `scripts/test-templates.sh` plants a
  call between two use cases, and a use case whose name starts with another's, in every clean style.
- NetArchTest's `ResideInNamespace` compares prefixes (`Order` takes in `Orders`). Both the new test
  and VSA-2's `FeatureIsolationTests` now match the namespace exactly.
- NetArchTest hasn't released since 1.3.2 (May 2021); [ArchUnitNET](https://www.nuget.org/packages/TngTech.ArchUnitNET)
  is active. Moving the architecture tests to it is a separate change.
