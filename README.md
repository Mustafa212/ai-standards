# ai-standards

One repo that makes every project, every developer and every AI assistant write code the same way:
readable, typed, tested and secure. Rules are **enforced by tools**, not by memory, and they
**evolve** through PRs that reach every project automatically.

```
          base rules            (everyone)
              ▼
   stack: typescript │ python   (per technology)
              ▼
   org: personal │ example-corp │ …   (per organization: stricter limits, own rules)
              ▼
   project: docs/PROJECT.md     (per project, never overwritten)
```

## What a generated project gets

| Layer | What enforces it |
| --- | --- |
| Formatting | Prettier / Ruff format |
| Readability limits (function size, complexity, params, nesting, file size, magic numbers, naming) | ESLint / Ruff, thresholds from base or org |
| Types | TypeScript `strict` + type-checked lint / mypy `--strict` |
| Tests | Vitest / pytest with a coverage threshold |
| Secrets, commit format | pre-commit (gitleaks, Conventional Commits) |
| The gate | GitHub Actions CI running the same `check` command |
| AI while it writes | Claude Code hooks: lint every edited file and send errors back; block edits to managed files |
| AI instructions | `AGENTS.md` (+ `CLAUDE.md`, Cursor rules, Copilot instructions), composed from the layers |
| Staying current | Monthly workflow opens an "ai-standards update" PR |

## Quick start

### 1. Make it yours

1. Push this repo to GitHub (e.g. `your-user/ai-standards`).
2. Replace `YOUR_GITHUB_USER` in `copier.yml` and `plugin/.claude-plugin/plugin.json`.
3. Edit `orgs/`: keep `personal`, rename or delete `example-corp`, add your own.

### 2. Install the plugin (once per machine)

```bash
claude plugin marketplace add your-user/ai-standards
claude plugin install ai-standards@ai-standards
```

Set the template source when prompted (or later in `/config`). From now on, in any empty folder,
Claude is told at session start to scaffold through `ai-standards:init-project`. For a belt-and-braces
setup, append `user-level/CLAUDE.md` to `~/.claude/CLAUDE.md`.

For a company: put `extraKnownMarketplaces` + `enabledPlugins` in managed settings so the plugin is
installed on every machine and can't be disabled. Generated projects already include these keys in
`.claude/settings.json`, so anyone who clones one gets the plugin too.

### 3. Start a project

In Claude Code, in an empty folder: *"create a new TypeScript project called billing-api for
example-corp"*. Without Claude:

```bash
uvx copier copy --trust gh:your-user/ai-standards my-project
```

## Changing the rules

| I want to… | Edit |
| --- | --- |
| Change a threshold for everyone | `config/defaults.jinja` |
| Change a threshold for one org | `orgs/<org>/settings.jinja` |
| Add a rule for everyone | `rules/base.md` (+ lint config if a tool can check it) |
| Add a rule for one stack | `rules/stacks/<stack>.md` (+ that stack's lint config) |
| Add a rule for one org | `orgs/<org>/rules.md` (+ `settings.jinja`, e.g. banned imports) |
| Add an org | copy `orgs/personal/`, add it to `org` choices in `copier.yml` |
| Add a stack | `rules/stacks/<stack>.md`, template files named `{% if stack == '<stack>' %}…{% endif %}`, a choice in `copier.yml`, a branch in `scripts/test-templates.sh` |

Or just tell Claude what keeps going wrong; the `ai-standards:propose-rule` skill turns it into a
PR. Every PR runs `scripts/test-templates.sh`, which generates all stack × org projects, checks they
pass, and checks that every rule in `tests/violations/` still fires. See
[docs/EVOLVING.md](docs/EVOLVING.md) for the full loop and versioning.

## Repo layout

```
copier.yml                 questions (org, stack, name, AI tools)
config/                    default thresholds + resolution (org override → base default)
rules/                     base and per-stack rule text (becomes AGENTS.md)
orgs/<org>/                settings.jinja (overrides) + rules.md (extra rules)
partials/                  composes base + stack + org into one rules body
template/                  files rendered into each project
plugin/                    Claude Code plugin: skills + SessionStart hook
.claude-plugin/            marketplace manifest (this repo is installable as a marketplace)
tests/violations/          code that must be rejected, per stack and org
scripts/test-templates.sh  end-to-end test of every combination
user-level/CLAUDE.md       optional snippet for ~/.claude/CLAUDE.md
```

## Limits worth knowing

- Instructions to AI tools are guidance; the hard guarantee is pre-commit + CI. Protect `main` with
  required status checks so CI is actually a gate.
- Hooks run only in Claude Code. Other AI tools get the instruction files, and their output is
  stopped at pre-commit and CI.
- The managed-file guard stops the AI, not a human. Humans can run `AI_STANDARDS_UNLOCK=1 claude`;
  pair it with CODEOWNERS on config files if you need a hard rule for people.
