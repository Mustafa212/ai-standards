# .NET stack (new projects): design

Date: 2026-10-14 · Status: approved by the owner · Target release: 0.6.0 (adopting existing .NET
projects is 0.7.0, a separate design)

## Goal

`stack=dotnet` scaffolds a .NET 10 solution in one of three architectures. Every approved rule is
in `AGENTS.md`, and every `[tool]` rule is enforced by the build, so the fresh scaffold passes
`bash .ai-standards/check.sh` with zero warnings.

## Layers

`base → stack → architecture → org → project`. The architecture is a new layer:
`rules/architectures/<stack>-<architecture>.md`, chosen with the copier question `architecture`
(dotnet only: `simple`, `clean`, `vertical-slice`; default `simple`). `check_rules.py` includes
architecture files in every org's scope, so architecture IDs use their own prefixes: `API-n`,
`CLEAN-n`, `VSA-n`.

| Architecture | Projects | Rules enforced by a tool |
| --- | --- | --- |
| simple | `src/<Name>` (Web API), `tests/<Name>.Tests` | none beyond the stack |
| clean | `src/<Name>.Domain`, `.Application`, `.Infrastructure`, `.Api`; `tests/<Name>.UnitTests`, `tests/<Name>.ArchitectureTests` | CLEAN-1: dependencies point inward (NetArchTest) |
| vertical-slice | `src/<Name>` with `Features/<Feature>/<UseCase>/`; `tests/<Name>.Tests`, `tests/<Name>.ArchitectureTests` | VSA-2: no slice depends on another feature (NetArchTest) |

## Stack rules and their tools

`rules/stacks/dotnet.md` holds CS-1..CS-12 as approved in the research, plus **CS-13 [review]**
(one public type per file, named after it; this was the review half of CS-2).

- Managed `Directory.Build.props`: `net10.0` (org `dotnet_version`), `Nullable`,
  `ImplicitUsings`, `TreatWarningsAsErrors`, `AnalysisLevel=latest-Recommended`,
  `EnforceCodeStyleInBuild`, `GenerateDocumentationFile` (test projects exempt from CS1591),
  `SonarAnalyzer.CSharp`, and coverlet for test projects with the coverage threshold.
- **SonarAnalyzer.CSharp** (LGPL, free) is what makes the base readability rules `[tool]` in .NET:
  S107 parameters, S138 method length, S1541 complexity, S134 nesting, S104 file length, S109 magic
  numbers, S125 commented-out code. Thresholds come from `config/defaults.jinja` and the org
  settings, through a managed `.ai-standards/SonarLint.xml`.
- `.editorconfig` gains a `[*.cs]` section: the CS-2/CS-3 code-style rules as warnings, plus CA1031,
  CA1852 and CA1507 raised to warning.
- `global.json` pins the SDK feature band (`10.0.100`, `rollForward: latestFeature`).
- Project files (`*.csproj`, `<Name>.slnx`) are project-owned (`_skip_if_exists`), like
  `package.json`. Everything that changes between standards versions lives in the managed files.
- Check: managed `.ai-standards/check.sh` runs `dotnet format --verify-no-changes`, `dotnet build`,
  then `dotnet test` (with the coverage threshold). It is bash, which exists wherever Claude Code
  runs (Git Bash on Windows).

## Claude hooks (bash, no jq)

- `protect-managed-files.sh`: reads `tool_input.file_path` from the hook JSON with `sed`, then
  matches it against `.claude/managed-files.txt`.
- `check-edited-file.sh`: runs `dotnet format whitespace --folder --include <file>` on edited `.cs`
  files. It's fast because it loads no MSBuild workspace. Analyzer findings come from the build in
  the check command (DONE-1); running analyzers on every edit would take seconds per edit.

## Tests

`test-templates.sh` loops every architecture × org for dotnet: render, run `check.sh`, check that
the violation files fire their rule IDs (parsed from the build output), run the hook tests, and plant
a cross-feature reference in vertical-slice so the architecture test must fail. CI adds `dotnet` to
the stack matrix with `actions/setup-dotnet`.

## Out of scope

Adopting existing .NET projects (0.7.0). Org-specific architectures, such as the user's company
architecture, live in the private copy.
