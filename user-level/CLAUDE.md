<!--
Optional: append this to ~/.claude/CLAUDE.md so the rule applies in every session on your machine,
even before the ai-standards plugin is installed in a given project.
-->

## Project standards

- When I ask to create, init, bootstrap or scaffold a new project, or to register an existing one,
  always use the `ai-standards:onboard` skill (it registers the project, then scaffolds or audits
  it). Never hand-write lint, formatter, type-checker, test or CI configuration for a new project.
- In projects that have `AGENTS.md`, follow it. Run the project's check command before saying a
  task is done.
- Never weaken lint, type or coverage settings to make checks pass. If a rule seems wrong, say so
  and offer the `ai-standards:propose-rule` skill.
