"""Tests for fix_debt.py. Run: python3 -m unittest discover -s scripts -p 'test_*.py'"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fix_debt  # noqa: E402

PRIORITIES = {"default": "P3", "prefixes": {"ERR": "P1"}, "ids": {"RDB-6": "P4"}, "tool_ids": {}}


def tool(rule: str, file: str, tool_id: str = "x", line: int = 1) -> dict:
    return {"rule": rule, "tool_id": tool_id, "file": file, "line": line, "message": "m", "source": "tool"}


class ItemsTest(unittest.TestCase):
    def test_items_per_rule_and_folder_p1_apart_review_items_kept_done_skipped(self) -> None:
        findings = {"rules": [
            {"rule": "RDB-1", "priority": "P3", "kind": "violation", "count": 3, "sources": ["tool"],
             "areas": {"src": 2, "lib": 1}},
            {"rule": "ERR-1", "priority": "P1", "kind": "violation", "count": 1, "sources": ["tool"],
             "areas": {"src": 1}},
            {"rule": "DES-1", "priority": "P3", "kind": "violation", "count": 4, "sources": ["review"],
             "areas": {"src": 4}},
            {"rule": "RDB-3", "priority": "P3", "kind": "inconsistency", "count": 2, "sources": ["review"],
             "areas": {"src": 2}},
        ]}
        tools = [tool("RDB-1", "src/a.py"), tool("RDB-1", "src/b.py"), tool("RDB-1", "lib/c.py"),
                 tool("ERR-1", "src/a.py")]
        result = fix_debt.build_items(findings, tools, PRIORITIES, done={"RDB-1@lib"})
        self.assertEqual([item["id"] for item in result["items"]], ["DES-1@src", "RDB-1@src"])
        self.assertEqual(result["items"][1]["files"], ["src/a.py", "src/b.py"])
        self.assertEqual(result["items"][0]["kind"], "review")
        self.assertEqual([item["id"] for item in result["p1"]], ["ERR-1@src"])
        self.assertEqual(result["p1"][0]["behavior"], "changes")

    def test_a_large_item_splits_by_the_next_folder(self) -> None:
        findings = {"rules": [{"rule": "RDB-1", "priority": "P3", "kind": "violation", "count": 40,
                               "sources": ["tool"], "areas": {"src": 40}}]}
        tools = [tool("RDB-1", f"src/billing/f{n}.py") for n in range(25)]
        tools += [tool("RDB-1", f"src/orders/f{n}.py") for n in range(15)]
        result = fix_debt.build_items(findings, tools, PRIORITIES, done=set())
        self.assertEqual({item["id"]: item["count"] for item in result["items"]},
                         {"RDB-1@src/billing": 25, "RDB-1@src/orders": 15})

    def test_a_rule_split_by_tool_priority_keeps_its_tool_ids_apart(self) -> None:
        priorities = {**PRIORITIES, "ids": {"DART-3": "P1"}, "tool_ids": {"prefer_const_constructors": "P4"}}
        findings = {"rules": [
            {"rule": "DART-3", "priority": "P1", "kind": "violation", "count": 1, "sources": ["tool"], "areas": {"lib": 1}},
            {"rule": "DART-3", "priority": "P4", "kind": "violation", "count": 2, "sources": ["tool"], "areas": {"lib": 2}},
        ]}
        tools = [tool("DART-3", "lib/a.dart", "use_build_context_synchronously"),
                 tool("DART-3", "lib/b.dart", "prefer_const_constructors"),
                 tool("DART-3", "lib/c.dart", "prefer_const_constructors")]
        result = fix_debt.build_items(findings, tools, priorities, done=set())
        self.assertEqual(result["items"][0]["id"], "DART-3@lib#P4")
        self.assertEqual(result["items"][0]["tool_ids"], ["prefer_const_constructors"])
        self.assertEqual(result["p1"][0]["files"], ["lib/a.dart"])

    def test_in_area_and_root(self) -> None:
        self.assertTrue(fix_debt.in_area("src/billing/a.py", "src/billing"))
        self.assertFalse(fix_debt.in_area("src/billing2/a.py", "src/billing"))
        self.assertTrue(fix_debt.in_area("setup.py", "(root)"))
        self.assertFalse(fix_debt.in_area("src/a.py", "(root)"))

    def test_items_cli_writes_items_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "findings.json").write_text(json.dumps({"rules": [
                {"rule": "RDB-1", "priority": "P3", "kind": "violation", "count": 1, "sources": ["tool"],
                 "areas": {"src": 1}}]}), encoding="utf-8")
            (out / "tool-findings.json").write_text(json.dumps({"status": "ran", "notes": [],
                                                                "findings": [tool("RDB-1", "src/a.py")]}), encoding="utf-8")
            self.assertEqual(fix_debt.main(["items", str(out), "--org", "personal"]), 0)
            data = json.loads((out / "fix-debt" / "items.json").read_text(encoding="utf-8"))
            self.assertEqual(data["items"][0]["id"], "RDB-1@src")


if __name__ == "__main__":
    unittest.main()
