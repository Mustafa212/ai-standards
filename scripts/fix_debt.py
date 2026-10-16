"""Pay standards debt in rounds, with proof a script computes instead of the agent's word.

  fix_debt.py items <out> --org <org> [--max 10]
  fix_debt.py start <project> <batch-dir> --item <id> --items <items.json> [--allow <path>]...
                    [--formatter-only]
  fix_debt.py test <project> --command <cmd> --format trx|junit|jest|flutter|summary --out <json>
  fix_debt.py canary <project> --file <path> --line <n> --replace <text> --command <cmd>
                     --format <f> --clean <json> --out <json>
  fix_debt.py verify <project> --item-dir <dir> --stack <s> --org <o> --render <dir>
                     --before <tool-findings.json> [--solution <sln>]
  fix_debt.py verify-review --item-dir <dir> --review <auditor json>
  fix_debt.py baseline <project> --stack typescript|python --out <json>
  fix_debt.py verify-adopted <project> --item-dir <dir> --stack typescript|python --before <json>
                             --check <cmd>
  fix_debt.py verdict <project> --item-dir <dir>

Evidence lives in the item's folder (<out>/fix-debt/<batch>/<item>/), never in the project.
In --command, {result} and {dir} become quoted paths and {name} the result file's bare name.
Standard library only; Windows and Linux.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit import area  # noqa: E402
from rule_data import load_priorities, priority  # noqa: E402

SPLIT_AT = 30
ITEMS, DONE = "items.json", "done.json"


def in_area(file: str, where: str) -> bool:
    """Whether a project-relative file belongs to an item's folder; "(root)" is the top level."""
    if where == "(root)":
        return "/" not in file
    return file == where or file.startswith(where.rstrip("/") + "/")


def safe_name(item_id: str) -> str:
    """A folder name for an item id: RDB-1@src/billing#P4 → RDB-1@src_billing_P4."""
    return re.sub(r"[^A-Za-z0-9@._-]", "_", item_id)


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def read_json(path: Path, default: object = None) -> object:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def git(project: Path, *args: str) -> str:
    return subprocess.run(  # noqa: S603  # fixed argument list, no shell
        ["git", "-C", str(project), *args], capture_output=True, text=True, encoding="utf-8",
        errors="replace", check=True).stdout


def _sub_area(file: str, top: str) -> str:
    parts = file.split("/")
    return "/".join(parts[:2]) if top != "(root)" and len(parts) > 2 else top


def build_items(findings: dict, tool_findings: list[dict], priorities: dict, done: set[str]) -> dict:
    """Debt items, one per rule, priority and folder (split by the next folder past SPLIT_AT)."""
    repeated = {rule["rule"] for rule in findings["rules"]
                if sum(r["rule"] == rule["rule"] for r in findings["rules"]) > 1}
    items: list[dict] = []
    for rule in findings["rules"]:
        if rule["kind"] != "violation":
            continue  # inconsistencies are settled in onboarding before they become debt
        mine = [f for f in tool_findings if f["rule"] == rule["rule"]
                and priority(f["rule"], priorities, f["tool_id"]) == rule["priority"]]
        suffix = f"#{rule['priority']}" if rule["rule"] in repeated else ""
        for top, count in rule["areas"].items():
            in_top = [f for f in mine if area(f["file"]) == top]
            groups: dict[str, list[dict]] = {top: in_top}
            if len(in_top) > SPLIT_AT:
                groups = {}
                for finding in in_top:
                    groups.setdefault(_sub_area(finding["file"], top), []).append(finding)
            for where, group in groups.items():
                item_id = f"{rule['rule']}@{where}{suffix}"
                if item_id in done:
                    continue
                items.append({
                    "id": item_id, "rule": rule["rule"], "area": where, "priority": rule["priority"],
                    "count": len(group) if group else int(count),
                    "kind": "tool" if group else "review",
                    "tool_ids": sorted({str(f["tool_id"]) for f in group}),
                    "files": sorted({str(f["file"]) for f in group}),
                    "behavior": "changes" if rule["priority"] == "P1" else "preserves",
                })
    items.sort(key=lambda item: (item["priority"], -item["count"], item["id"]))
    return {"items": [i for i in items if i["behavior"] == "preserves"],
            "p1": [i for i in items if i["behavior"] == "changes"]}


def cmd_items(args: argparse.Namespace) -> int:
    out = args.out.resolve()
    findings = read_json(out / "findings.json")
    tool = read_json(out / "tool-findings.json", {"findings": []})
    if findings is None:
        sys.stderr.write(f"no findings.json in {out}: run /ai-standards:audit first\n")
        return 2
    done = set(read_json(out / "fix-debt" / DONE, []))
    result = build_items(findings, tool["findings"], load_priorities(args.org), done)
    write_json(out / "fix-debt" / ITEMS, result)
    for item in result["items"][: args.max]:
        print(f"{item['id']}  {item['priority']}  {item['count']}  {item['kind']}")
    for item in result["p1"]:
        print(f"{item['id']}  P1 (changes behavior)  {item['count']}  {item['kind']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    items = commands.add_parser("items", help="debt items for the next round")
    items.add_argument("out", type=Path)
    items.add_argument("--org", required=True)
    items.add_argument("--max", type=int, default=10)
    args = parser.parse_args(argv)
    return {"items": cmd_items}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
