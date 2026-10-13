#!/usr/bin/env bash
# Managed by ai-standards.
# Blocks AI edits to files owned by ai-standards so rules can't be weakened to "get green".
# A human can bypass for one session with:  AI_STANDARDS_UNLOCK=1 claude
set -euo pipefail

[[ "${AI_STANDARDS_UNLOCK:-0}" == "1" ]] && exit 0

input="$(cat)"
file_path="$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null || true)"
[[ -z "$file_path" ]] && exit 0

project_dir="${CLAUDE_PROJECT_DIR:-$(pwd)}"
relative="${file_path#"$project_dir"/}"
managed_list="$project_dir/.claude/managed-files.txt"
[[ -f "$managed_list" ]] || exit 0

while IFS= read -r pattern; do
  [[ -z "$pattern" || "$pattern" == \#* ]] && continue
  # shellcheck disable=SC2053  # glob match is intended
  if [[ "$relative" == $pattern ]]; then
    {
      echo "Blocked: '$relative' is managed by ai-standards (rule SUP-2)."
      echo "Fix the code instead of changing the rules. If the rule itself is wrong,"
      echo "tell the user and suggest /ai-standards:propose-rule."
    } >&2
    exit 2
  fi
done < "$managed_list"

exit 0
