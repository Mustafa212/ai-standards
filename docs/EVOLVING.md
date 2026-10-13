# How the standards evolve

Rules are code. They change through pull requests, get tested, get versioned, and reach every
project automatically.

## The loop

```
 signal ──► propose-rule ──► PR to ai-standards ──► test-templates.sh ──► tag vX.Y.Z
   ▲                                                                          │
   │                                                                          ▼
 projects ◄── monthly "ai-standards update" PR in each project (copier update) ◄┘
```

### 1. Signals: where new rules come from

- The same code-review comment twice.
- An AI tool making the same mistake twice (wrong library, duplicated helper, swallowed error).
- An incident or bug whose root cause a check could have caught.
- A managed file blocking a change a project genuinely needs (the rule may be wrong).

When any of these happens, run the `propose-rule` skill (or open a PR by hand).

### 2. Rule lifecycle: always push rules toward tools

```
[ai] guidance  ──►  [review] checklist  ──►  [tool] enforced
```

A rule usually starts as prose. Every rule that *can* be checked mechanically should be promoted to
`[tool]`: a lint rule, a config flag, a CI step or a hook. Prose rules cost context in every AI
session and can be ignored; tool rules cannot. Review the `[ai]` and `[review]` rules each quarter
and ask of each one: can a tool check this now?

Removing a rule is also evolution. If a rule is constantly suppressed with good reasons, or nobody
can say what problem it prevents, delete it.

### 3. Proof: rules have tests

`scripts/test-templates.sh` generates every stack × org combination and fails if:

- a fresh scaffold does not pass its own checks, or
- a rule listed in `tests/violations/` no longer fires.

The second point matters more than it looks: tool upgrades rename, move or silently disable rules.
CI runs this weekly, not only on PRs, to catch upstream changes.

### 4. Release: semver from the project's point of view

See `CHANGELOG.md` for what counts as MAJOR, MINOR and PATCH. Release by moving `## Unreleased`
under a version heading and pushing a `vX.Y.Z` tag.

### 5. Distribution

- **Projects**: the `ai-standards update` workflow in every generated project runs `copier update`
  monthly and opens a PR. Copier does a three-way merge, so project-owned content survives.
- **Tooling versions**: Renovate opens PRs in this repo when ESLint, Ruff, pre-commit hooks, etc.
  release. They go through the same template tests before merging.
- **The plugin**: Claude Code auto-updates it from this repo's marketplace.
- **Private copies**: `git pull upstream main --tags` brings a public release into a private copy
  (the plugin offers it and asks first); its projects then update from the private copy.
- **Project rules**: SessionStart offers a refresh once 30 days and 10 commits have passed since the
  last analysis, so new conventions become proposals and rules the code stopped following get
  reviewed.

## Layers and ownership

| Layer | Lives in | Who changes it |
| --- | --- | --- |
| base | `rules/base.md`, `config/defaults.jinja`, `template/` | Everyone's agreement; changes affect all orgs |
| stack | `rules/stacks/<stack>.md`, stack template files | People who own that stack |
| org | `orgs/<org>/` in the user's private copy | That org |
| project | `orgs/<org>/projects/<project>.md` in the private copy (rules), `docs/PROJECT.md` in the project (notes) | That project |

Org and project data never goes into the public repo. A rule two projects of an org share moves up
to the org (the `onboard` skill offers it; `scripts/check_rules.py` fails CI on exact duplicates).
A rule that would help every project of a stack, or every project, goes to the public repo as a PR.
Nothing changes in a project or a standards repo without the user's yes.

An org can tighten any threshold. If an org needs to *loosen* a base rule, that is a signal the base
rule may be wrong: discuss it in a PR to base rather than adding an org exception.
