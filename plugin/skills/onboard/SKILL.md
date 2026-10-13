---
name: onboard
description: Use when a project isn't registered with ai-standards yet (new folder or existing code), when the user asks which org a project belongs to or to register or onboard it, and to refresh or re-analyze a registered project's rules. Asks the org (existing or new), registers the project in the user's private copy of ai-standards, scaffolds or adopts it, proposes project rules from the code for approval, and moves a rule shared by two projects up to the org.
---

# Onboard a project, and keep its rules current

Two promises hold on every step:

- **Nothing changes without a clear yes.** Show the user what would be saved, committed or pushed,
  and wait.
- **Org and project rules are private.** They live only in the user's private copy of ai-standards,
  never in the public repo. General rules go to the public repo as a PR (step 8).

The private copy is recorded in `~/.claude/ai-standards/config.md`:

```
Source: gh:<owner>/<repo>
Clone: <absolute path of the local clone>
```

Below, `<clone>` and `<source>` mean those two values. For Python scripts use `python3`, or
`python` where `python3` is the Windows Store alias (it prints "Python was not found").

**Mode.** If the project has `.copier-answers.yml` and its `AGENTS.md` has a
`rules analyzed:` line, go to step 7 (refresh). Otherwise run steps 1–6.

## 1. The private copy (once per machine)

If `config.md` exists, `<clone>` exists, and `git -C <clone> remote get-url upstream` works (a
private copy keeps the public repo as `upstream`): run `git -C <clone> pull`, then go to step 2.

Otherwise explain in two lines that the public repo is shared with everyone, so the user's orgs and
project rules need a private copy. Then ask whether they already have one.

- **They have one:** clone it into `~/.claude/ai-standards/<repo>` and write `config.md`.
- **Create one:**
  1. Clone the public repo (`${user_config.standards_source}`, as an https URL) into
     `~/.claude/ai-standards/ai-standards-<name>`.
  2. `git -C <clone> remote rename origin upstream`.
  3. Publish it as **private**. With `gh`, and after asking:
     `gh repo create <owner>/ai-standards-<name> --private --source <clone> --push`. Without `gh`, the
     user does it in GitHub Desktop: File → Add local repository → `<clone>` → Publish repository,
     with "Keep this code private" checked. Wait until they confirm, then check that
     `git -C <clone> remote get-url origin` works.
  4. Write `config.md`.

New public releases reach the private copy with `git -C <clone> pull upstream main --tags`. Offer
that when the public repo has a newer tag than the private copy, and always ask first.

## 2. Which org?

Read the `org` choices in `<clone>/orgs/orgs.yml`. Ask with AskUserQuestion: "Which org does
<project> belong to?", listing every org plus "New org".

For a **new org**, ask its name (kebab-case) and its rule prefix (2–6 capital letters, e.g. `ACME`).
Then create:

- `orgs/<org>/rules.md`: `## Org: <org>`, then `<!-- prefix: <PREFIX> -->`.
- `orgs/<org>/settings.jinja`: a copy of `orgs/personal/settings.jinja`, which means base defaults.
- a `<org>: <org>` line under `choices` in `orgs/orgs.yml`.

## 3. Register the project

1. Ask whether the project's repo is private. If it's public, stop and say why: its `AGENTS.md`
   would publish the org's rules.
2. Ask for the project's rule prefix (suggest the first 4 letters of the slug, in capitals).
3. Create `orgs/<org>/projects/<slug>.md`:

```markdown
## Project: <project name>

<!-- prefix: <PREFIX> · repo: <git remote URL> · stack: <stack> · rules analyzed: <today> (<HEAD short sha, or none>) -->
```

## 4. Scaffold or adopt

- **Empty folder:** run the `init-project` skill with this org and `<source>`. Then go to step 6.
- **Existing code:** run the `adopt-project` skill with this org and `<source>`, keeping all its
  gates. Then go to step 5.

## 5. Propose project rules from the code

Read the project the way a new senior teammate would: the folder structure, two or three main flows
end to end, and a sample from each layer. Look for what the code does **consistently** that no rule
in base, stack, the org or another project of the org already covers:

- layering: where business logic, data access and UI live
- how errors travel: exceptions or result types, and where they're caught
- one library per concern: HTTP, dates, money, logging, validation, state
- naming beyond the linter: file names, suffixes such as `Service` or `Dto`
- tests: where they live, how they're named, how they mock

A pattern most of the code follows is a candidate; a one-off is not. Present one table:

| # | Proposed rule (one plain sentence) | Evidence | Enforcement |
|---|---|---|---|
| 1 | Database access goes through repositories, never from controllers. | 14 of 14 controllers; `OrdersController.cs:22`, `InvoicesController.cs:18` | `[review]` |

`[tool]` only when an existing lint rule can check it (name the rule; it is configured in the org's
`settings.jinja`, for example banned imports). Otherwise use `[review]`. For each rule the user
picks keep, edit or drop.

## 6. No duplicates, then save

For every kept rule, in order:

1. **Already covered** by base, stack or the org (same meaning)? Drop it, and say which rule covers it.
2. **Same meaning as a rule in another project of this org?** Offer to move it up: "BILL-4 and
   PORT-3 say the same thing. Move it to the org as ACME-n and remove it from both projects?" On yes,
   add `- **ACME-n [level]** <text>` to `orgs/<org>/rules.md`. In each project file, remove the rule
   and leave `<!-- moved to org: PORT-3 → ACME-n -->` in its place.
3. **Otherwise** add `- **<PREFIX>-n [level]** <text>` to the project file. `n` is the highest
   number ever used in that file plus one, counting the `moved to org` lines too. IDs are never
   reused.

Then:

1. Run `python3 <clone>/scripts/check_rules.py <clone>`. It must print nothing.
2. Show `git -C <clone> diff`, ask, commit (`feat(<org>): rules for <project>`), and push.
3. Bring the rules into the project. A new project already has them from step 4. For an existing
   project, run `uvx copier update --trust --defaults --conflict rej` on a clean tree and offer the
   commit `chore: ai-standards rules for <project>`.
4. If a rule moved to the org, name the other projects: they get it on their next `copier update`.

## 7. Refresh mode

This runs when SessionStart offers it (30 days and 10 commits since the last analysis), or when the
user asks.

1. Read the date and sha from the marker. Look at `git log --stat <sha>..HEAD`; use all commits when
   the sha is `none` or no longer in history.
2. Look only at what changed. New consistent patterns become proposals (the step 5 table). Project
   rules the new code keeps breaking are shown with the evidence: keep, edit or delete? A rule the
   team stopped following may be out of date.
3. Run step 6 on the result, checking the org's other projects again for rules to move up.
4. Set the marker to today and `HEAD`, even when nothing else changed, so the next offer waits
   another 30 days. Ask before saving, as for every change.

## 8. General rules go to the public repo

When a proposal isn't specific to this org, because it would help any project on this stack or
every project, say so. Offer it as a **pull request to the public repo** with the `propose-rule`
skill, instead of adding it to the org. Never push org or project data to the public repo.
