"""
Tests of skills/openpages-tutorial/scripts/tutorial.py (offline: no OpenPages server needed).
  python3 -m unittest tests/test_tutorial.py -v      (from the project root)
"""
import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TUT = ROOT / "skills" / "openpages-tutorial"
sys.path.insert(0, str(ROOT / "skills" / "openpages-solutions" / "scripts"))
sys.path.insert(0, str(TUT / "scripts"))

import yaml  # noqa: E402

import qr_score  # noqa: E402
import spec as spec_mod  # noqa: E402
import tutorial  # noqa: E402

ENVS = """environments:
  shared-dev:
    base_url: https://shared-dev.example
    tier: dev
    allow_writes: true
    auth: basic
  prod:
    base_url: https://prod.example
    tier: prod
    auth: basic
"""


class TutorialTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "config").mkdir()
        (self.tmp / "config" / "environments.yaml").write_text(ENVS)
        self.env = mock.patch.dict(os.environ, {"OP_CONFIG": str(self.tmp / "config" / "environments.yaml")})
        self.env.start()
        os.environ.pop("OP_TUTORIAL_CODE", None)

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_tut(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            try:
                rc = tutorial.main(list(argv))
            except SystemExit as e:
                rc = e.code if isinstance(e.code, int) else 1
                out.write(str(e.code))
        return rc, out.getvalue()

    def start(self, code="ZZ"):
        rc, out = self.run_tut("start", "--code", code, "--owner", "learner")
        self.assertEqual(rc, 0, out)
        return yaml.safe_load((self.tmp / "specs" / f"px{code.lower()}.yaml").read_text(encoding="utf-8"))

    # ---------------------------------------------------------------- start
    def test_start_renders_a_clean_spec(self):
        spec = self.start()
        self.assertEqual(spec["solution"]["key"], "PXZZ")
        self.assertEqual(spec_mod.lint_spec(spec), [])
        self.assertEqual(tutorial.naming_issues(spec, "ZZ"), [])
        self.assertEqual(spec["tests"]["fixtures"]["process"], "SOXProcess:ZZ Tutorial Process")
        self.assertEqual(spec["workflows"][0]["stages"][2]["assignee"], "user:learner")
        prog = yaml.safe_load((self.tmp / "runs" / "tutorial" / "ZZ" / "progress.yaml").read_text())
        self.assertEqual((prog["key"], prog["env"], prog["spec"]), ("PXZZ", "shared-dev", "specs/pxzz.yaml"))

    def test_start_writes_parseable_filters(self):
        self.start()
        d = self.tmp / "build" / "PXZZ" / "template"
        names = sorted(p.name for p in d.iterdir())
        self.assertEqual(names, ["ObjectManagerExportFilters-PXZZ-reference.xml",
                                 "ObjectManagerExportFilters-SOXIssue.xml", "ObjectManagerExportFilters-SOXTask.xml"])
        ref = ET.parse(d / "ObjectManagerExportFilters-PXZZ-reference.xml").getroot()
        self.assertEqual(sorted(e.get("name") for e in ref.iter("contentType")), ["PXZZControl", "PXZZException"])
        self.assertEqual(sorted(e.get("name") for e in ref.iter("bundleType")), ["PXZZ-Ctl", "PXZZ-Exc"])
        self.assertEqual([e.get("name") for e in ref.iter("objectProfile")], ["OpenPages Modules Master"])
        tpl = ET.parse(d / "ObjectManagerExportFilters-SOXIssue.xml").getroot()
        self.assertEqual(tpl.find("jspBasedContentTypes/contentType").get("name"), "SOXIssue")

    def test_start_refuses_bad_code_and_overwrite(self):
        rc, out = self.run_tut("start", "--code", "K1", "--owner", "learner")
        self.assertNotEqual(rc, 0)
        self.assertIn("2-4 letters", out)
        self.start()
        rc, out = self.run_tut("start", "--code", "ZZ", "--owner", "learner")
        self.assertNotEqual(rc, 0)
        self.assertIn("exists", out)

    def test_questionnaire_expectations_hold(self):
        self.start()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = qr_score.main([str(self.tmp / "specs" / "pxzz.yaml")])
        self.assertEqual(rc or 0, 0, buf.getvalue())
        self.assertEqual(buf.getvalue().count("PASS"), 3)

    # ---------------------------------------------------------------- naming rule
    def test_naming_rule_catches_unprefixed_names(self):
        spec = self.start()
        spec["object_types"][0]["name"] = "PolicyException"
        spec["object_types"][1]["label"] = "Compensating Control"
        spec["filters"][0]["name"] = "Open Exceptions"
        spec["tests"]["scenarios"][0]["create"][0]["name"] = "TEST {run}"
        spec["workflow_changes"] = [{"workflow": "Questionnaire Assessment Workflow"}]
        issues = "\n".join(tutorial.naming_issues(spec, "ZZ"))
        for needle in ("object type 'PolicyException'", "label 'Compensating Control'", "filter 'Open Exceptions'",
                       "test object 'TEST {run}'", "workflow_changes"):
            self.assertIn(needle, issues)

    # ---------------------------------------------------------------- checkpoints
    def test_checkpoints_grow_with_the_lessons(self):
        spec = self.start()
        cp4 = tutorial.checkpoint_spec(spec, 4)
        self.assertTrue(all("field_groups" not in t for t in cp4["object_types"]))
        self.assertTrue(all(t.get("parents") for t in cp4["object_types"]))
        self.assertNotIn("workflows", cp4)
        self.assertEqual(spec_mod.lint_spec(cp4), [])
        cp5 = tutorial.checkpoint_spec(spec, 5)
        self.assertIn("field_groups", cp5["object_types"][0])
        self.assertNotIn("calculations", cp5)
        cp8 = tutorial.checkpoint_spec(spec, 8)
        self.assertIn("workflows", cp8)
        self.assertNotIn("questionnaires", cp8)
        self.assertEqual(spec_mod.lint_spec(cp8), [])
        cp10 = tutorial.checkpoint_spec(spec, 10)
        self.assertIn("questionnaires", cp10)
        self.assertEqual(spec_mod.lint_spec(cp10), [])
        self.assertIsNot(cp5["object_types"], spec["object_types"])          # deep copy: spec untouched
        self.assertIn("field_groups", spec["object_types"][0])

    # ---------------------------------------------------------------- checks that need no server
    def test_junit_check(self):
        self.start()
        rc, out = self.run_tut("check", "9")
        self.assertEqual(rc, 1)
        self.assertIn("no test report", out)
        j = self.tmp / "runs" / "tutorial" / "ZZ" / "junit.xml"
        j.write_text('<testsuites><testsuite name="t" tests="6" failures="1" errors="0"/></testsuites>')
        self.assertEqual(self.run_tut("check", "9")[0], 1)
        j.write_text('<testsuite name="t" tests="6" failures="0" errors="0"/>')
        rc, out = self.run_tut("check", "9")
        self.assertEqual(rc, 0, out)
        prog = yaml.safe_load((self.tmp / "runs" / "tutorial" / "ZZ" / "progress.yaml").read_text())
        self.assertEqual(prog["lessons"][9]["status"], "passed")

    def test_self_check_needs_confirm(self):
        self.start()
        with mock.patch.object(sys.stdin, "isatty", return_value=False):
            rc, out = self.run_tut("check", "6")
        self.assertEqual(rc, 1)
        self.assertIn("PXZZException-Task", out)
        rc, out = self.run_tut("check", "6", "--confirm")
        self.assertEqual(rc, 0, out)

    def test_package_check_and_next(self):
        self.start()
        self.assertEqual(self.run_tut("check", "12")[0], 1)
        (self.tmp / "build" / "PXZZ" / "PACKAGE.md").write_text("# package")
        self.assertEqual(self.run_tut("check", "12")[0], 0)
        rc, out = self.run_tut("next")
        self.assertIn("Lesson 00", out)
        rc, out = self.run_tut("status")
        self.assertIn("[x] 12", out)

    def test_prod_env_refused(self):
        self.start()
        prog_p = self.tmp / "runs" / "tutorial" / "ZZ" / "progress.yaml"
        prog = yaml.safe_load(prog_p.read_text())
        prog["env"] = "prod"
        prog_p.write_text(yaml.safe_dump(prog))
        rc, out = self.run_tut("check", "0")
        self.assertEqual(rc, 1)
        self.assertIn("never runs against a prod-tier", out)

    def test_every_lesson_file_exists_with_sections(self):
        for n, stem, title, kind in tutorial.LESSONS:
            p = tutorial.lesson_file(n)
            self.assertTrue(p.exists(), p)
            text = p.read_text(encoding="utf-8")
            for h in ("## Objectives", "## Concepts", "## Do", "## Check", "## Recap"):
                self.assertIn(h, text, f"{p.name}: {h}")
            self.assertIn(f"tutorial check {n}", text, p.name)


if __name__ == "__main__":
    unittest.main()
