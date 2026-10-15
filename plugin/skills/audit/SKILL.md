---
name: audit
description: Use when the user asks whether a project follows its rules or standards, wants a standards report or audit, asks what to fix first, or right after onboarding. Works for any registered project on any stack (typescript, python, angular, dotnet, flutter), adopted or not. Read-only on the project: the real analyzers run in a temporary worktree, AI agents check the [review] rules, and a prioritized report is written on this machine only.
---

# Audit a project against its rules

**Read-only on the project.** Nothing is written, committed or changed in the project's repository.
The tools run in a temporary git worktree that is removed afterwards, and the report lives on this
machine.

Paths:
- `~/.claude/ai-standards/config.md` holds `Source:` and `Clone:` (the private copy, `<clone>`), and
  optionally `Audit model: opus | sonnet` (default `opus`).
- The report folder is `~/.claude/ai-standards/reports/<org>/<slug>/`, called `<out>` below.

For Python scripts use `python3`, or `python` where `python3` is the Windows Store alias.
`<clone>/scripts/audit.py` missing means the private copy predates 0.9.0: offer
`git -C <clone> pull upstream main --tags` (ask first), then go on.

## 1. Find the registration

Compare `git remote get-url origin` with the `repo:` value in each `<clone>/orgs/*/projects/*.md`
header, ignoring a `user@` part and a trailing `.git`. The match gives `<org>` (the folder),
`<slug>` (the file name), the stack, and for dotnet the architecture (`architecture:`, else
`simple`). No match: say the project isn't registered, offer `/ai-standards:onboard`, and stop. With
uncommitted changes, say the audit covers the last commit (`git rev-parse --short HEAD`) and go on.

## 2. Render the rules and configs

```bash
uvx copier copy --trust --defaults --quiet --vcs-ref HEAD \
  --data org=<org> --data stack=<stack> --data project_name="<slug>" --data project_slug=<slug> \
  --data 'ai_tools=["claude"]' "<clone>" <tmp>/rendered
```

For dotnet add `--data architecture=<architecture>`. `--vcs-ref HEAD` includes rules kept in this
session that aren't committed yet. `<tmp>/rendered/AGENTS.md` now holds every rule in effect for this
project.

## 3. Run the tools

```bash
python3 <clone>/scripts/audit.py tools <project> --stack <stack> --org <org> \
  --render <tmp>/rendered --out <out>
```

- **Exit 3:** show the candidate solutions with AskUserQuestion, and run again with
  `--solution <choice>`.
- **Status** in `<out>/tool-findings.json`: `ran`, `skipped` or `failed`. When it isn't `ran`, the
  `[tool]` rules go to the auditors too (step 4), and the report says why.

## 4. Check the rules with the auditors

Take the bullets from `<tmp>/rendered/AGENTS.md`: rules `- **ID [level]** text`, and exceptions
`- **ID [exception] → TARGET** text`. `[ai]` rules are guidance and aren't audited. Group the
`[review]` rules (and the `[tool]` rules when the tools didn't run) by ID:

1. **Design and architecture:** DES, API, CLEAN, VSA, TS-3, TS-4, PY-3, CS-9, CS-10, CS-11, NG-5,
   DART-5, DART-6, DART-7.
2. **Errors and security:** ERR, CS-8, NG-10.
3. **Readability:** RDB, READ-4, CS-13, CS-14, NG-6, NG-7, NG-8, NG-9, DART-8.
4. **Tests:** TST, DONE-2, TS-5, PY-4, CS-12, DART-10.
5. **Everything else:** the stack's other rules, and the org's and the project's rules.

Dispatch one `ai-standards:rule-auditor` per non-empty group, all in one message, with the config's
`Audit model`. The brief:

```
## Rules (verbatim)
<the group's rule bullets>

## Exceptions (not breaks)
<the exception bullets, or "none">

## Project
Path: <project>   Stack: <stack>
Skip: bin/, obj/, node_modules/, .dart_tool/, build/, dist/, migrations folders, generated files
(*.g.dart, *.freezed.dart, *.Designer.cs)

## Already found by the linters (don't repeat)
<per rule: rule and count, from tool-findings.json; or "the tools didn't run: <status>">
```

Write `<out>/review.json`:
- Take each auditor's JSON object, from inside a ```json fence if it put one there.
- Concatenate every auditor's `rules`, `not_checked` and `instructions`.
- An auditor that fails or returns invalid JSON puts its rules under `not_checked`, with the reason
  "auditor failed".
- Inconsistencies from onboarding (onboard step 4) are added to `rules` with
  `"kind": "inconsistency"`.

## 5. Write the report

```bash
python3 <clone>/scripts/audit.py report <out> --project-name "<project name>" --org <org> \
  --stack <stack> --sha <short HEAD> --review <out>/review.json \
  --exceptions <clone>/orgs/<org>/projects/<slug>.md --agents <n> --model <model>
```

Remove `<tmp>`.

## 6. Tell the user

In a few lines:
- the totals per priority, and the top 3;
- what wasn't checked, and why;
- the change since the last audit;
- any instructions found in the code;
- the report's path (`<out>/STANDARDS-DEBT.md`).

The report stays on this machine and never goes into the repository.
