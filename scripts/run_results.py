"""Read a test run's results from the file its runner wrote, or from the runner's summary line.

Every parser returns {"executed", "passed", "failed", "skipped", "tests", "source"}: `executed` is
passed + failed, `tests` maps a test id to "passed", "failed" or "skipped" (empty for a summary
line), and `source` is "file" or "summary". XML with a DOCTYPE is refused (no entity expansion), and
files over MAX_BYTES aren't read. Standard library only.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Callable
from pathlib import Path

MAX_BYTES = 64 * 1024 * 1024
TRX = "{http://microsoft.com/schemas/VisualStudio/TeamTest/2010}"


class Unreadable(Exception):
    """The result can't be used: missing, too big, malformed, unsafe or without a summary."""


def _result(tests: dict[str, str]) -> dict:
    counts = Counter(tests.values())
    return {"executed": counts["passed"] + counts["failed"], "passed": counts["passed"],
            "failed": counts["failed"], "skipped": counts["skipped"], "tests": tests, "source": "file"}


def _summary(passed: int, failed: int, skipped: int) -> dict:
    return {"executed": passed + failed, "passed": passed, "failed": failed, "skipped": skipped,
            "tests": {}, "source": "summary"}


def _xml(text: str) -> ET.Element:
    if "<!DOCTYPE" in text or "<!ENTITY" in text:
        raise Unreadable("XML with a DOCTYPE is refused")
    try:
        return ET.fromstring(text)
    except ET.ParseError as error:
        raise Unreadable(f"malformed XML: {error}") from error


def _unique(tests: dict[str, str], name: str) -> str:
    """A repeated id (a parameterized test) becomes name#2, name#3 …, so no run is lost."""
    if name not in tests:
        return name
    n = 2
    while f"{name}#{n}" in tests:
        n += 1
    return f"{name}#{n}"


def merge(results: list[dict]) -> dict:
    """One result from the several files of one run (dotnet writes a TRX per test project)."""
    tests: dict[str, str] = {}
    for result in results:
        for name, outcome in result["tests"].items():
            tests[_unique(tests, name)] = outcome
    return _result(tests)


def parse_junit(text: str) -> dict:
    tests: dict[str, str] = {}
    for case in _xml(text).iter("testcase"):
        if case.find("skipped") is not None:
            outcome = "skipped"
        elif case.find("failure") is not None or case.find("error") is not None:
            outcome = "failed"
        else:
            outcome = "passed"
        tests[_unique(tests, f"{case.get('classname', '')}::{case.get('name', '')}")] = outcome
    return _result(tests)


def parse_trx(text: str) -> dict:
    root = _xml(text)
    names = {}
    for unit in root.iter(f"{TRX}UnitTest"):
        method = unit.find(f"{TRX}TestMethod")
        names[unit.get("id")] = f"{method.get('className', '') if method is not None else ''}::{unit.get('name', '')}"
    tests: dict[str, str] = {}
    for result in root.iter(f"{TRX}UnitTestResult"):
        # Inconclusive, Timeout, Aborted and the rest count as failed: they didn't pass.
        outcome = {"Passed": "passed", "NotExecuted": "skipped"}.get(result.get("outcome", ""), "failed")
        tests[_unique(tests, names.get(result.get("testId"), result.get("testName", "")))] = outcome
    return _result(tests)


def parse_jest(text: str) -> dict:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise Unreadable(f"malformed JSON: {error}") from error
    tests: dict[str, str] = {}
    for suite in data.get("testResults", []):
        for case in suite.get("assertionResults", []):
            status = case.get("status")
            outcome = "passed" if status == "passed" else "failed" if status == "failed" else "skipped"
            tests[_unique(tests, f"{suite.get('name', '')}::{case.get('fullName', '')}")] = outcome
    return _result(tests)


def parse_flutter(text: str) -> dict:
    names: dict[object, str] = {}
    tests: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip().startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "testStart":
            names[event["test"]["id"]] = event["test"].get("name", "")
        elif event.get("type") == "testDone" and not event.get("hidden"):
            outcome = ("skipped" if event.get("skipped")
                       else "passed" if event.get("result") == "success" else "failed")
            tests[_unique(tests, names.get(event.get("testID"), str(event.get("testID"))))] = outcome
    if not names:
        raise Unreadable("no flutter test events")
    return _result(tests)


def _numbers(text: str, words: tuple[str, ...]) -> dict[str, int]:
    return {word: int(n) for n, word in re.findall(rf"(\d+) ({'|'.join(words)})\b", text)}


def _vstest(text: str) -> tuple[int, int, int] | None:
    found = re.findall(r"(?:Passed|Failed)!\s+-\s+Failed:\s+(\d+),\s+Passed:\s+(\d+),\s+Skipped:\s+(\d+)", text)
    if not found:
        return None
    return (sum(int(p) for _, p, _ in found), sum(int(f) for f, _, _ in found), sum(int(s) for _, _, s in found))


def _pytest(text: str) -> tuple[int, int, int] | None:
    lines = re.findall(r"^=+ (.+?) in [\d.]+s(?: \(.*\))? =+$", text, re.MULTILINE)
    if not lines:
        return None
    n = _numbers(lines[-1], ("passed", "failed", "skipped", "error", "errors"))
    return n.get("passed", 0), n.get("failed", 0) + n.get("error", 0) + n.get("errors", 0), n.get("skipped", 0)


def _vitest(text: str) -> tuple[int, int, int] | None:
    lines = re.findall(r"^\s*Tests\s+(.+?)\(\d+\)\s*$", text, re.MULTILINE)
    if not lines:
        return None
    n = _numbers(lines[-1], ("passed", "failed", "skipped", "todo"))
    return n.get("passed", 0), n.get("failed", 0), n.get("skipped", 0) + n.get("todo", 0)


def _jest(text: str) -> tuple[int, int, int] | None:
    lines = re.findall(r"^Tests:\s+(.+?)\d+ total\s*$", text, re.MULTILINE)
    if not lines:
        return None
    n = _numbers(lines[-1], ("passed", "failed", "skipped", "todo"))
    return n.get("passed", 0), n.get("failed", 0), n.get("skipped", 0) + n.get("todo", 0)


def _karma(text: str) -> tuple[int, int, int] | None:
    found = re.findall(r"Executed (\d+) of \d+(?: \((\d+) FAILED\))?(?: \(skipped (\d+)\))?", text)
    if not found:
        return None
    ran, failed, skipped = found[-1]
    return int(ran) - int(failed or 0), int(failed or 0), int(skipped or 0)


def _unittest(text: str) -> tuple[int, int, int] | None:
    ran = re.findall(r"^Ran (\d+) tests? in", text, re.MULTILINE)
    end = re.findall(r"^(OK|FAILED)(?: \((.*?)\))?\s*$", text, re.MULTILINE)
    if not ran or not end:
        return None
    n = {key: int(value) for key, value in re.findall(r"(failures|errors|skipped)=(\d+)", end[-1][1] or "")}
    failed, skipped = n.get("failures", 0) + n.get("errors", 0), n.get("skipped", 0)
    return int(ran[-1]) - failed - skipped, failed, skipped


def _flutter_line(text: str) -> tuple[int, int, int] | None:
    found = re.findall(r"\+(\d+)(?: ~(\d+))?(?: -(\d+))?: (?:All tests passed!|Some tests failed\.)", text)
    if not found:
        return None
    passed, skipped, failed = found[-1]
    return int(passed), int(failed or 0), int(skipped or 0)


def parse_summary(text: str) -> dict:
    for parse in (_vstest, _pytest, _vitest, _jest, _karma, _unittest, _flutter_line):
        counts = parse(text)
        if counts is not None:
            return _summary(*counts)
    raise Unreadable("no test summary line found")


PARSERS: dict[str, Callable[[str], dict]] = {
    "trx": parse_trx, "junit": parse_junit, "jest": parse_jest, "flutter": parse_flutter, "summary": parse_summary,
}


def read(path: Path, kind: str) -> dict:
    if not path.is_file():
        raise Unreadable(f"no result file at {path}")
    if path.stat().st_size > MAX_BYTES:
        raise Unreadable(f"result file over {MAX_BYTES} bytes")
    return PARSERS[kind](path.read_text(encoding="utf-8", errors="replace"))
