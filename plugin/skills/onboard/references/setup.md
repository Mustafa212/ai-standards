# Onboard: one-time setup

`<clone>`, `<source>` and `config.md` mean what they mean in the onboard skill.

## Private copy (once per machine, and once per client whose rules stay apart)

Explain in two lines that the public repo is shared with everyone, so the user's orgs and project
rules need a private copy. Then ask whether they already have one.

- **They have one:** clone it into `~/.claude/ai-standards/<repo>` and add its pair to `config.md`.
- **Create one:**
  1. Clone the public repo (the skill's pointer to this file names it; use its https URL) into
     `~/.claude/ai-standards/ai-standards-<name>`.
  2. `git -C <clone> remote rename origin upstream`.
  3. Publish it as **private**. With `gh`, and after asking:
     `gh repo create <owner>/ai-standards-<name> --private --source <clone> --push`. Without `gh`, the
     user does it in GitHub Desktop: File → Add local repository → `<clone>` → Publish repository,
     with "Keep this code private" checked. Wait until they confirm, then check that
     `git -C <clone> remote get-url origin` works.
  4. Add its `Source:` and `Clone:` pair to `config.md`, below any pairs already there.

## New org (once per org)

Ask its name (kebab-case) and its rule prefix (2–6 capital letters, e.g. `ACME`). Then create:

- `orgs/<org>/rules.md`: `## Org: <org>`, then `<!-- prefix: <PREFIX> -->`.
- `orgs/<org>/settings.jinja`: a copy of `orgs/personal/settings.jinja`, which means base defaults.
- a `<org>: <org>` line under `choices` in `orgs/orgs.yml`.

Commit the new org's files in the private copy and push them, after the user's yes, before anything
renders from the remote (step 7's `init-project` does). Rendering from a remote that doesn't have the
org yet fails.
