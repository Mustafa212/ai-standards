"""Tests for run_results.py. Run: python3 -m unittest discover -s scripts -p 'test_*.py'"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_results  # noqa: E402

JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="t">
  <testcase classname="tests.test_calc" name="test_add"/>
  <testcase classname="tests.test_calc" name="test_sub"><failure message="boom"/></testcase>
  <testcase classname="tests.test_calc" name="test_skip"><skipped/></testcase>
  <testcase classname="tests.test_calc" name="test_param"/>
  <testcase classname="tests.test_calc" name="test_param"/>
  <testcase classname="tests.test_calc" name="test_err"><error message="x"/></testcase>
</testsuite></testsuites>"""

TRX = """<?xml version="1.0" encoding="utf-8"?>
<TestRun xmlns="http://microsoft.com/schemas/VisualStudio/TeamTest/2010">
  <TestDefinitions>
    <UnitTest name="Adds" id="a"><TestMethod className="Shop.Tests.CalcTests" name="Adds"/></UnitTest>
    <UnitTest name="Subtracts" id="b"><TestMethod className="Shop.Tests.CalcTests" name="Subtracts"/></UnitTest>
    <UnitTest name="Later" id="c"><TestMethod className="Shop.Tests.CalcTests" name="Later"/></UnitTest>
  </TestDefinitions>
  <Results>
    <UnitTestResult testId="a" testName="Adds" outcome="Passed"/>
    <UnitTestResult testId="b" testName="Subtracts" outcome="Failed"/>
    <UnitTestResult testId="c" testName="Later" outcome="NotExecuted"/>
  </Results>
</TestRun>"""

JEST = """{"testResults": [{"name": "/p/src/calc.test.ts", "assertionResults": [
  {"fullName": "calc adds", "status": "passed"},
  {"fullName": "calc subtracts", "status": "failed"},
  {"fullName": "calc later", "status": "pending"}]}]}"""

FLUTTER = "\n".join([
    '{"type":"start"}',
    '{"type":"testStart","test":{"id":1,"name":"loading test/calc_test.dart"}}',
    '{"type":"testDone","testID":1,"result":"success","skipped":false,"hidden":true}',
    '{"type":"testStart","test":{"id":2,"name":"calc adds"}}',
    '{"type":"testDone","testID":2,"result":"success","skipped":false,"hidden":false}',
    '{"type":"testStart","test":{"id":3,"name":"calc subtracts"}}',
    '{"type":"testDone","testID":3,"result":"failure","skipped":false,"hidden":false}',
    '{"type":"testStart","test":{"id":4,"name":"calc later"}}',
    '{"type":"testDone","testID":4,"result":"success","skipped":true,"hidden":false}',
])


class ParserTest(unittest.TestCase):
    def test_junit_counts_failures_errors_skips_and_repeated_names(self) -> None:
        result = run_results.parse_junit(JUNIT)
        self.assertEqual((result["executed"], result["passed"], result["failed"], result["skipped"]), (5, 3, 2, 1))
        self.assertEqual(result["tests"]["tests.test_calc::test_param#2"], "passed")
        self.assertEqual(result["tests"]["tests.test_calc::test_err"], "failed")
        self.assertEqual(result["source"], "file")

    def test_trx(self) -> None:
        result = run_results.parse_trx(TRX)
        self.assertEqual(result["tests"], {"Shop.Tests.CalcTests::Adds": "passed",
                                           "Shop.Tests.CalcTests::Subtracts": "failed",
                                           "Shop.Tests.CalcTests::Later": "skipped"})

    def test_jest(self) -> None:
        result = run_results.parse_jest(JEST)
        self.assertEqual((result["passed"], result["failed"], result["skipped"]), (1, 1, 1))
        self.assertIn("/p/src/calc.test.ts::calc adds", result["tests"])

    def test_flutter_ignores_hidden_loading_tests(self) -> None:
        result = run_results.parse_flutter(FLUTTER)
        self.assertEqual(result["tests"], {"calc adds": "passed", "calc subtracts": "failed", "calc later": "skipped"})

    def test_summary_lines(self) -> None:
        cases = {
            "Failed!  - Failed:     1, Passed:     4, Skipped:     2, Total:     7": (4, 1, 2),
            "=========== 3 passed, 1 failed, 2 skipped in 0.12s ===========": (3, 1, 2),
            " Tests  5 passed | 1 failed (6)": (5, 1, 0),
            "Tests:       1 failed, 3 passed, 4 total": (3, 1, 0),
            "Chrome Headless 120 (Linux): Executed 4 of 5 (1 FAILED) (skipped 1) (0.1 secs / 0.08 secs)": (3, 1, 1),
            "Ran 6 tests in 0.010s\n\nFAILED (failures=1, errors=1, skipped=1)": (3, 2, 1),
            "00:02 +7 ~1 -2: Some tests failed.": (7, 2, 1),
        }
        for line, (passed, failed, skipped) in cases.items():
            with self.subTest(line=line):
                result = run_results.parse_summary(line)
                self.assertEqual((result["passed"], result["failed"], result["skipped"]), (passed, failed, skipped))
                self.assertEqual((result["source"], result["tests"]), ("summary", {}))

    def test_summary_without_a_known_line_is_unreadable(self) -> None:
        with self.assertRaises(run_results.Unreadable):
            run_results.parse_summary("build succeeded\n")


class SafetyTest(unittest.TestCase):
    def test_xml_with_a_doctype_is_refused(self) -> None:
        evil = '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><testsuite><testcase name="&a;"/></testsuite>'
        with self.assertRaises(run_results.Unreadable):
            run_results.parse_junit(evil)

    def test_malformed_xml_is_unreadable(self) -> None:
        with self.assertRaises(run_results.Unreadable):
            run_results.parse_junit("<testsuite><testcase")

    def test_missing_and_oversized_files_are_unreadable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(run_results.Unreadable):
                run_results.read(Path(tmp) / "none.xml", "junit")
            big = Path(tmp) / "big.xml"
            big.write_text("<testsuite/>", encoding="utf-8")
            saved, run_results.MAX_BYTES = run_results.MAX_BYTES, 5
            try:
                with self.assertRaises(run_results.Unreadable):
                    run_results.read(big, "junit")
            finally:
                run_results.MAX_BYTES = saved


if __name__ == "__main__":
    unittest.main()
