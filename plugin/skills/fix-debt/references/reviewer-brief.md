# Reviewer brief for a debt item

*fix-debt reference. Fill it in for `senior-dev:reviewer` in step 10. Give the reviewer this and
nothing else: no reasoning, no hint of where to look.*

```
## User story (the source of truth, verbatim)
<story>
Pay the <rule> debt in <area>: <the rule's text, verbatim from the rendered AGENTS.md>.
Behavior must not change.        (P1 item: replace this line with the behavior change the user approved)
</story>

## Acceptance criteria
- AC-1: the analyzer (or rule auditor) finds no <rule> finding left in <area>.
- AC-2: the fix adds no finding to the files it touched.
- AC-3: every test that passed before still passes; none was removed or skipped.
- AC-4: no suppression, baseline entry or severity change was added.

## Planned proof per AC
The script's verdict (below) proves AC-1 to AC-4. Judge whether the change itself is right:
behavior kept, the rule really followed (not just silenced in another way), nothing else changed.

## The change
`<dir>/change.diff` (`git diff <start>..HEAD` in <project path>). Read it from that file.

## The verdict
<the contents of verdict.md>

## Project docs and rules
<the rendered AGENTS.md path>
```
