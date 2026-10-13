# .NET Stack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** `stack=dotnet` with three architectures, every approved rule in `AGENTS.md`, every `[tool]` rule enforced by the build. Release 0.6.0.

**Spec:** `docs/superpowers/specs/2026-10-14-dotnet-stack-design.md`

**Tech Stack:** .NET 10 SDK, xunit.v3 4.0.2 + xunit.runner.visualstudio 4.0.1 + Microsoft.NET.Test.Sdk 18.11.0, coverlet.msbuild 10.1.0, NetArchTest.Rules 1.3.2, SonarAnalyzer.CSharp 10.35.0.4138, Microsoft.AspNetCore.OpenApi 10.0.13.

## Global Constraints

- The fresh scaffold of every architecture × org passes `bash .ai-standards/check.sh` with zero warnings.
- Thresholds come from `cfg` (RDB-1, RDB-2, RDB-4, TST-1). Nothing is hard-coded in the template.
- `*.csproj` and `<Name>.slnx` are project-owned; the standards live in the managed files.
- Hooks: bash and sed only (no jq, node or python).

## Review Focus

- The hook JSON on Windows carries `C:\\Users\\…` with escaped backslashes: the hooks must unescape it and match relative paths.
- A file path with spaces (`Ai Standard Plugin`) in hooks and in `check.sh`.
- An org that sets `dotnet_version` must reach `Directory.Build.props` and `global.json`.
- Test projects are exempt from CS1591 (doc comments) and the Sonar magic-number rule, as tests are elsewhere.
- Coverage counts production code only (no `Program.cs`, no test assemblies).

### Task 1: Questions, settings and layer wiring
`copier.yml` (stack choice `dotnet`, `architecture` and `dotnet_name` questions), `config/defaults.jinja` and `config/settings.jinja` (`dotnet_version`, `check_cmd`), `partials/agents-body.md.jinja` (architecture include), `scripts/check_rules.py` (architecture files in scope). Test: rendering `stack=dotnet architecture=clean` gives an `AGENTS.md` with CS-1 and CLEAN-1; `check_rules.py` stays clean.

### Task 2: Rule files
`rules/stacks/dotnet.md` (CS-1..CS-13), `rules/architectures/dotnet-{simple,clean,vertical-slice}.md`, and per-stack text in `rules/base.md` (RDB-1, RDB-8, DES-5, DES-7) so dotnet never gets Python wording.

### Task 3: Managed build files and sample code per architecture
`global.json`, `Directory.Build.props`, `.editorconfig.jinja` (`[*.cs]`), `.ai-standards/SonarLint.xml`, `.ai-standards/check.sh`, `<Name>.slnx`, the projects and sample code of each architecture (a greeting use case with tests), and the architecture tests. Verify: `check.sh` passes for all 3 × 2 renders locally.

### Task 4: Hooks
`protect-managed-files.sh` and `check-edited-file.sh` (dotnet), the `settings.json` commands, the `managed-files.txt` dotnet section, `.gitignore`, `.pre-commit-config`, and the `ci.yml` dotnet job. Test: a dotnet branch in `test-hooks.sh` (block a managed file, allow a source file, format an edited file).

### Task 5: Proof in CI
`tests/violations/dotnet/*.cs` (CA1031, S107, S109, CS1591, IDE0161 …), a dotnet loop in `test-templates.sh` (architectures × orgs, violation IDs from the build output, a planted cross-feature reference that must fail VSA-2), and the CI matrix with `actions/setup-dotnet`.

### Task 6: Skills, docs, release
`init-project`/`onboard` (dotnet + architecture), README, CHANGELOG 0.6.0, plugin 0.6.0, Renovate regex for `PackageReference` in `*.jinja`. PR, CI green, merge, tag.
