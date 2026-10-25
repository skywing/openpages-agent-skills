"""
End-to-end tests of the skill scripts against mock_openpages.py.
  python3 -m unittest tests/test_scripts.py -v      (from the project root)
"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SKILL = next(p for p in (ROOT / ".claude" / "skills" / "openpages-solutions", ROOT / "skills" / "openpages-solutions") if (p / "SKILL.md").exists())
sys.path.insert(0, str(SKILL / "scripts"))
sys.path.insert(0, str(HERE))

import mock_openpages  # noqa: E402


def run(mod_name, argv):
    mod = __import__(mod_name)
    buf, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
        try:
            rc = mod.main(argv)
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
            err.write(str(e.code))
    return rc or 0, buf.getvalue(), err.getvalue()


class ScriptsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = mock_openpages.start()
        cls.url = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        cls.tmp = Path(tempfile.mkdtemp())
        (cls.tmp / "config").mkdir()
        (cls.tmp / "specs").mkdir()
        (cls.tmp / "config" / "environments.json").write_text(json.dumps({"environments": {
            "local": {"base_url": cls.url, "tier": "dev", "allow_writes": True, "auth": "basic"},
            "prod": {"base_url": cls.url, "tier": "prod", "allow_writes": True, "auth": "basic"},
        }}))
        shutil.copy(SKILL / "templates" / "solution-spec.example.yaml", cls.tmp / "specs" / "tpr.yaml")
        cls.spec = str(cls.tmp / "specs" / "tpr.yaml")
        os.environ.update(OP_USER="tester", OP_PASSWORD="pw", OP_ENV="local")
        cls.cwd = os.getcwd()
        os.chdir(cls.tmp)

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls.cwd)
        cls.srv.shutdown()
        shutil.rmtree(cls.tmp)

    def test_01_lint(self):
        rc, out, _ = run("verify_spec", [self.spec, "--lint-only"])
        self.assertEqual(rc, 0, out)
        from spec import lint_spec
        bad = {"solution": {"key": "TPR"}, "object_types": [{"name": "Bad Name", "field_groups": [{"name": "g", "fields": [{"name": "Tags", "type": "enum"}]}]}],
               "workflows": [{"name": "w", "object_type": "Nope", "stages": [{"name": "A", "actions": [{"name": "x", "to": "Z"}]}]}]}
        errs = "\n".join(lint_spec(bad))
        for needle in ["system name", "solution key", "no parents", "enum without values", "FastMap", "targets unknown stage", "no start stage", "not in spec"]:
            self.assertIn(needle, errs)

    def test_02_ping_types(self):
        rc, out, err = run("op", ["ping"])
        self.assertEqual(rc, 0, err)
        self.assertIn("object_types=5", out)
        rc, out, _ = run("op", ["types", "--grep", "TPR"])
        self.assertIn("TPRRemediation", out)
        self.assertNotIn("SOXIssue", out)
        rc, out, _ = run("op", ["wf", "--type", "TPRRemediation"])
        self.assertIn("action 'Rework' -> 'Draft'", out)

    def test_03_query_paging(self):
        from opclient import OpenPagesClient, load_env
        c = OpenPagesClient(load_env("local"))
        rows = list(c.query("SELECT [Resource ID],[Name] FROM [SOXIssue]", page_size=1))
        self.assertGreaterEqual(len(rows), 1)
        self.assertIn("Resource ID", rows[0])

    def test_04_dump_and_verify(self):
        rc, out, err = run("dump_schema", ["--only", "TPR,QuestionnaireAssessment,SOXIssue,Vendor"])
        self.assertEqual(rc, 0, err)
        d = self.tmp / "schema" / "local"
        self.assertTrue((d / "types" / "TPRRemediation.json").exists())
        self.assertIn("TPR-Rem:Status", (d / "SCHEMA.md").read_text())
        rc, out, _ = run("verify_spec", [self.spec])
        self.assertEqual(rc, 0, out)
        self.assertIn("0 errors", out)
        self.assertNotIn("unconfirmed", out)  # all spec data types are now confirmed against a live 9.2.1 server
        rc2, out2, _ = run("verify_spec", [self.spec, "--from-dump", str(d)])
        self.assertEqual(rc2, 0, out2)

    def test_05_verify_detects_drift(self):
        t = mock_openpages.S.types["TPRRemediation"]
        saved = json.dumps(t)
        t["field_definitions"][1]["enum_values"].pop()  # drop 'Closed'
        mock_openpages.S.assoc["TPRMilestone"][0]["is_enabled"] = False
        mock_openpages.S.wf[0]["activities"][2]["transitions"][1]["target"] = "Start"
        try:
            rc, out, _ = run("verify_spec", [self.spec])
            self.assertEqual(rc, 1)
            self.assertIn("missing enum values: ['Closed']", out)
            self.assertIn("parent relationship to TPRRemediation exists but is disabled", out)
            self.assertIn("goes to 'Start'", out)
        finally:
            mock_openpages.S.types["TPRRemediation"] = json.loads(saved)
            mock_openpages.S.assoc["TPRMilestone"][0]["is_enabled"] = True
            mock_openpages.S.wf[0]["activities"][2]["transitions"][1]["target"] = "Draft"

    def test_06_dry_run_writes_nothing(self):
        before = len(mock_openpages.S.writes)
        rc, out, err = run("test_run", [self.spec])
        self.assertEqual(rc, 0, out + err)
        self.assertIn("[dry-run] POST /opgrc/api/v2/contents", out)
        self.assertEqual(len(mock_openpages.S.writes) - before, 0, "dry run must not write (query POSTs excluded)")

    def test_07_apply_scenarios_and_cleanup(self):
        rc, out, err = run("test_run", [self.spec, "--apply", "--cleanup", "--junit", "runs/junit.xml"])
        self.assertEqual(rc, 0, out + err)
        self.assertIn("3/3 scenarios passed, 0 failed, 0 need a manual UI check", out)
        self.assertIn("rejected as expected", out)
        j = ET.parse(self.tmp / "runs" / "junit.xml").getroot()
        self.assertEqual(j.get("failures"), "0")
        created = [o for o in mock_openpages.S.objects if o != "7000"]
        self.assertEqual(created, [], "cleanup should soft-delete created objects")
        audit = (self.tmp / "runs" / "audit.jsonl").read_text().splitlines()
        self.assertTrue(any('"method": "DELETE"' in a for a in audit))
        self.assertTrue(all('"password"' not in a.lower() for a in audit))

    def test_07b_manual_step_reported_not_failed(self):
        spec = json.loads(json.dumps(__import__("spec").load_spec(self.spec)))
        spec["tests"]["scenarios"] = [spec["tests"]["scenarios"][1]]
        spec["tests"]["scenarios"][0]["workflow"]["steps"][1].update(manual=True, manual_reason="comment required")
        p = self.tmp / "specs" / "manual.json"
        p.write_text(json.dumps(spec))
        rc, out, _ = run("test_run", [str(p), "--apply", "--cleanup", "--junit", "runs/junit-manual.xml"])
        self.assertEqual(rc, 0, out)
        self.assertIn("MANUAL: 'Rework' must be checked in the UI", out)
        self.assertIn("0/1 scenarios passed, 0 failed, 1 need a manual UI check", out)
        j = ET.parse(self.tmp / "runs" / "junit-manual.xml").getroot()
        self.assertEqual(len(j.findall("testcase/skipped")), 1)

    def test_08_failing_expectation_reported(self):
        spec = json.loads(json.dumps(__import__("spec").load_spec(self.spec)))
        spec["tests"]["scenarios"] = [spec["tests"]["scenarios"][1]]
        spec["tests"]["scenarios"][0]["workflow"]["steps"][0]["expect_stage"] = "Approved"   # Submit really lands in Review
        p = self.tmp / "specs" / "bad.json"
        p.write_text(json.dumps(spec))
        rc, out, _ = run("test_run", [str(p), "--apply", "--cleanup"])
        self.assertEqual(rc, 1)
        self.assertIn("expected 'Approved'", out)

    def test_09_prod_writes_blocked(self):
        from opclient import OpenPagesClient, WriteRefused, load_env
        env = load_env("prod")
        self.assertFalse(env.allow_writes)
        c = OpenPagesClient(env, apply=True)
        with self.assertRaises(WriteRefused):
            c.create_object("TPRRemediation", "x")
        rc, out, err = run("test_run", [self.spec, "--apply", "--env", "prod"])
        self.assertNotEqual(rc, 0)

    def test_10_plans(self):
        rc, out, err = run("plan", ["build", self.spec])
        self.assertEqual(rc, 0, err)
        b = (self.tmp / "build" / "TPR" / "BUILD.md").read_text()
        for needle in ["Enable System Admin Mode", "`TPR-Rem`", "Action **Rework**", "Sync"]:
            self.assertIn(needle, b)
        rc, out, err = run("plan", ["package", self.spec])
        self.assertEqual(rc, 0, err)
        x = ET.parse(self.tmp / "build" / "TPR" / "ObjectManagerExportFilters.xml").getroot()
        names = {e.get("name") for e in x.iter() if e.get("name")}
        self.assertTrue({"TPRRemediation", "TPR-Rem", "TPRRemediation-Task", "OpenPages Platform 3"} <= names)
        pk = (self.tmp / "build" / "TPR" / "PACKAGE.md").read_text()
        self.assertIn("`TPR Reviewers`", pk)
        self.assertIn("same OpenPages version and patch level", pk)

    def test_12_field_typo_caught(self):
        from opclient import OpenPagesClient, load_env
        c = OpenPagesClient(load_env("local"))
        with self.assertRaises(ValueError) as cm:
            c.shape_fields("TPRRemediation", {"TPR-Rem:Statsu": "Draft"})
        self.assertIn("not on type", str(cm.exception))
        shaped = c.shape_fields("TPRRemediation", {"TPR-Rem:Status": "Draft", "TPR-Rem:Remediation Owner": ["jdoe"], "TPR-Rem:Plan Summary": "x"})
        self.assertEqual(shaped[0]["value"], {"name": "Draft"})
        self.assertEqual(shaped[1]["value"], "jdoe")
        self.assertEqual(shaped[2]["value"], "x")

    def test_13_derive_type(self):
        dump = self.tmp / "soxissue-op-config.xml"
        dump.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<openpagesConfiguration xmlFormatVersion="1.31">
  <bundleTypes>
    <bundleType name="OPSS-Iss" type="Content Type"><propertyType name="Status" dataType="Enumerated String"/></bundleType>
    <bundleType name="System Fields" type="Content Type"/>
  </bundleTypes>
  <jspBasedContentTypes>
    <contentType name="SOXIssue" label="Issue" pluralLabel="Issues" description="OpenPages Issue" rootFolder="/_op_sox/Project/Default/Issue" id="6">
      <bundleTypeRef name="OPSS-Iss"/>
      <bundleTypeRef name="System Fields"/>
    </contentType>
    <contentType name="SOXTask" label="Issue Action Item"/>
  </jspBasedContentTypes>
  <contentTypeRelationships>
    <contentTypeRelationship parent="SOXBusEntity" child="SOXIssue"/>
  </contentTypeRelationships>
  <objectStrings>
    <objectString contentType="SOXIssue" key="singular" value="Issue"/>
  </objectStrings>
</openpagesConfiguration>""")
        out = self.tmp / "build" / "TPR" / "types" / "tprremediation-op-config.xml"
        rc, o, e = run("derive_type", ["--dump", str(dump), "--baseline", "SOXIssue", "--type", "TPRRemediation", "--spec", self.spec, "--out", str(out)])
        self.assertEqual(rc, 1, o + e)  # warns on the numeric id attribute
        x = ET.parse(out).getroot()
        self.assertEqual(x.get("xmlFormatVersion"), "1.31")
        cts = [c for c in x.iter("contentType")]
        self.assertEqual([c.get("name") for c in cts], ["TPRRemediation"])
        c = cts[0]
        self.assertEqual(c.get("label"), "Remediation"); self.assertEqual(c.get("pluralLabel"), "Remediations")
        self.assertEqual(c.get("rootFolder"), "/_op_sox/Project/Default/TPRRemediation")
        self.assertEqual(c.get("allowOverride"), "true")
        refs = [r.get("name") for r in c]
        self.assertEqual(refs, ["System Fields"])            # OPSS-Iss dropped
        self.assertEqual(list(x.iter("contentTypeRelationship")), [])  # relationships not copied
        self.assertEqual([s.get("contentType") for s in x.iter("objectString")], ["TPRRemediation"])
        self.assertEqual(next(x.iter("objectString")).get("value"), "Issue")  # non-label attr left, flagged
        rep = out.with_name("tprremediation-derive-report.md").read_text()
        self.assertIn("numeric id-like attribute", rep)
        self.assertIn("leftover reference", rep)
        self.assertIn("NOT copied", rep)

    def test_14_questionnaire_lint_and_scoring(self):
        import copy as _c
        from spec import lint_questionnaires, load_file
        from qr_score import compute, question_score
        spec = load_file(self.spec)
        self.assertEqual(lint_questionnaires(spec, set()), [])
        # IBM worked example: multiple choice A10 B2 C1 D0, choose B+C, weight 1 -> 2.31
        q = {"id": "x", "type": "multiple", "answers": [{"text": "A", "score": 10}, {"text": "B", "score": 2}, {"text": "C", "score": 1}, {"text": "D", "score": 0}]}
        self.assertAlmostEqual(question_score(q, ["B", "C"]), 2.3077, places=3)
        # weighted average: subsection weights change the result, compliance stays within 0..100
        qn = _c.deepcopy(spec["questionnaires"][0]); qn["scoring"] = "weighted_average"
        qn["sections"][1]["subsections"][0]["weight"] = 3
        r = compute(qn, {"q1": "Yes", "q2": "x", "q3": ["MFA"], "q4": "Never"})
        self.assertTrue(0 <= r["compliance"] <= 100)
        self.assertAlmostEqual(r["compliance"], 17.5, places=2)   # SS1=(10+4)/2=7 of 10; SS2=3*0 of 30 -> 7/40
        # advanced logic incl. IBM's "1 not (2)" form
        qn2 = _c.deepcopy(spec["questionnaires"][0])
        qn2["sections"][0]["subsections"][0]["questions"][1]["show_when"] = {"conditions": [{"question": "q1", "in": ["Yes"]}, {"question": "q3", "in": ["None of the above"]}], "logic": "1 not (2)"}
        self.assertTrue(compute(qn2, {"q1": "Yes", "q3": ["MFA"]})["detail"][1]["visible"])
        self.assertFalse(compute(qn2, {"q1": "Yes", "q3": ["None of the above"]})["detail"][1]["visible"])
        # lint negatives
        bad = _c.deepcopy(spec)
        b = bad["questionnaires"][0]
        b["lifecycle"] = "5 Stage"; b["asset_types"] = ["SOXRisk"]
        qs = b["sections"][0]["subsections"][0]["questions"]
        qs[0]["show_when"] = {"conditions": [{"question": "q2", "in": ["x"]}]}          # controlling q2 is long_text + cycle-free
        qs[2]["answers"][0]["score"] = 10000
        qs.append({"id": "q1", "type": "single", "answers": [{"text": "a"}, {"text": "b"}]})  # duplicate id
        b["response_actions"][0]["skip_if_exists"] = False
        b["response_actions"][0]["child_type"] = "SOXDocument"
        b["tests"][0]["answers"]["q4"] = "Weekly"
        b["tests"][1]["answers"]["q3"] = ["MFA", "None of the above"]
        chain = [{"id": f"d{i}", "type": "single", "answers": [{"text": "y"}, {"text": "n"}],
                  **({"show_when": {"conditions": [{"question": f"d{i-1}", "in": ["y"]}]}} if i else {})} for i in range(8)]
        b["sections"][1]["subsections"][0]["questions"] += chain
        errs = "\n".join(lint_questionnaires(bad, set()))
        for needle in ["lifecycle must be", "not a questionnaire asset type", "must be single/multiple choice", "score out of -1..9999",
                       "duplicate question id", "skip_if_exists", "cannot create File/Link", "'Weekly' is not an answer",
                       "combines an exclusive answer", "dependency depth 8 levels (max 6)"]:
            self.assertIn(needle, errs)
        rc, out, _ = run("qr_score", [self.spec])
        self.assertEqual(rc, 0, out)
        self.assertIn("compliance=46.67", out)

    def test_15_questionnaire_plan_verify_and_read(self):
        rc, out, err = run("plan", ["questionnaire", self.spec])
        self.assertEqual(rc, 0, err)
        md = next((self.tmp / "build" / "TPR").glob("QUESTIONNAIRE-*.md")).read_text()
        for needle in ["QuestionnaireScoreAssessmentAction", "threshold=4", "Skip if it exists", "OPLC-QAssessment:LCStage", "| 25.0 | 15.0 | ['q2'] |"]:
            self.assertIn(needle, md)
        rc, out, _ = run("verify_spec", [self.spec])
        self.assertEqual(rc, 0, out)
        self.assertIn("UI-configured", out)
        saved = mock_openpages.S.assoc["SOXIssue"]
        mock_openpages.S.assoc["SOXIssue"] = []
        try:
            rc, out, _ = run("verify_spec", [self.spec])
            self.assertEqual(rc, 1)
            self.assertIn("SOXIssue is not a child of any asset type", out)
        finally:
            mock_openpages.S.assoc["SOXIssue"] = saved
        rc, out, _ = run("op", ["qa", "9001"])
        self.assertEqual(rc, 0)
        self.assertIn('"complianceScore": 25.0', out)

    def test_11_diff(self):
        a = self.tmp / "a-op-config.xml"; b = self.tmp / "b-op-config.xml"
        a.write_text('<openpagesConfiguration><contentTypes><contentType name="T1" label="A"/><contentType name="T2"/></contentTypes></openpagesConfiguration>')
        b.write_text('<openpagesConfiguration><contentTypes><contentType name="T2"/><contentType name="T1" label="B"/><contentType name="T3"/></contentTypes></openpagesConfiguration>')
        rc, out, _ = run("diff_config", [str(a), str(b)])
        self.assertEqual(rc, 3)
        self.assertIn("contentType[T3]", out)
        self.assertIn("label: 'A' → 'B'", out)
        self.assertIn("0 removed", out)


class ActivitySearchTest(unittest.TestCase):
    """activity_instances() must return every active activity in one read (no offset paging):
    live 9.2.1 skipped/duplicated rows when stepping `offset`, and test_run.py depends on this list."""

    def _client(self, total, server_cap=None):
        from opclient import OpenPagesClient
        c = object.__new__(OpenPagesClient)
        rows = [{"id": str(i), "grc_object": {"id": str(10000 + i)}} for i in range(1, total + 1)]
        calls = []

        def fake_get(path, **params):
            calls.append(dict(params))
            n = int(params.get("limit", 50))
            if server_cap:
                n = min(n, server_cap)
            return {"activity_instances": rows[:n], "paging": {"total_count": total, "offset": 1, "limit": n}}
        c.get = fake_get
        return c, calls

    def test_reads_all_in_one_call(self):
        c, calls = self._client(771)
        got = c.activity_instances()
        self.assertEqual(len(got), 771)
        self.assertEqual(len(calls), 1)
        self.assertNotIn("offset", calls[0])

    def test_requeries_with_total_when_larger(self):
        c, calls = self._client(2500)
        got = c.activity_instances()
        self.assertEqual(len(got), 2500)
        self.assertEqual([x["limit"] for x in calls], [2000, 2500])

    def test_warns_when_server_caps(self):
        c, _ = self._client(771, server_cap=500)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            got = c.activity_instances()
        self.assertEqual(len(got), 500)
        self.assertIn("returned 500 of 771", err.getvalue())


class CalculationLintTest(unittest.TestCase):
    """Expression lint follows Admin Guide 9.2.x ch.14 syntax rules (references/calculations.md)."""

    def L(self, expr, ops=("OpenMs", "C", "D1")):
        from spec import lint_expression
        return lint_expression(expr, set(ops))

    def test_valid_examples_from_guide(self):
        for e in [
            "if exists([$OpenMs$]) then count([$OpenMs$]) else 0 endif",
            "max([$Child:LossImpact/OPSS-LossIm:Estimated Loss$])",
            "if exists(sum([$C$])) then sum([$C$]) else currency(0.00, 'USD') endif",
            "/** header **/ // note\nformat(end_of_quarter(today()))",
            "if count([$Child:KeyRiskIndicatorValue/OPSS-KRI-Shared:Breach Status/DescBy:OPSS-KRIVal:Value Date$]) < 2 then 'x' else 'y' endif",
            "[$APPLICATION_URL$] + \"/x?id=\" + [$System Fields:Resource ID$]",
            "if [$C$] == 'a (b' then 'High' elif [$C$] == 'M' then 'Medium' else 'Low' endif",
        ]:
            self.assertEqual(self.L(e), [], e)

    def test_errors_caught(self):
        cases = {
            "if exists([$OpenMs$]) then 1 endif": "final 'else'",
            "cnt([$OpenMs$])": "unknown function 'cnt'",
            "count([$OpenMs$]": "missing ')'",
            "count([$child:X/G:F$])": "capital letter",
            "[$D1$] == (tomorrow)": "tomorrow()",
            "count([$Opnms$])": "not an earlier operation",
            "'abc": "unterminated string",
            "[$System Fields:Comment$]": "System Fields:Comment",
        }
        for e, needle in cases.items():
            self.assertTrue(any(needle in m for m in self.L(e)), f"{e!r} -> {self.L(e)}")

    def test_spec_calculations_section(self):
        from spec import lint_spec
        spec = {"object_types": [{"name": "TPRRemediation", "parents": [{"type": "SOXIssue", "primary": True}]}],
                "calculations": [{"name": "Bad Calc", "object_type": "TPRRemediation", "type": "nightly",
                                  "inputs": [{"name": "1st", "relationship": "sibling", "field": "Status"}],
                                  "set": [{"field": "System Fields:Name", "expression": "count([$X$])"}]}]}
        errs = "\n".join(lint_spec(spec))
        for needle in ["type must be one of", "invalid operation name", "no siblings", "Field Group:Field",
                       "not an earlier operation", "cannot set system field"]:
            self.assertIn(needle, errs)


class DateTest(unittest.TestCase):
    """Spec dates are sent as midnight in the display zone (UTC midnight showed as the previous evening in ET)."""

    def test_bare_date_to_local_midnight_utc(self):
        import datetime
        from opclient import to_api_date
        self.assertEqual(to_api_date("2026-12-31", "America/New_York"), "2026-12-31T05:00:00.000Z")   # EST
        self.assertEqual(to_api_date("2026-07-01", "America/New_York"), "2026-07-01T04:00:00.000Z")   # EDT
        self.assertEqual(to_api_date(datetime.date(2026, 12, 31), "Asia/Tokyo"), "2026-12-30T15:00:00.000Z")
        self.assertEqual(to_api_date("2026-12-31T05:00:00.000Z", "America/New_York"), "2026-12-31T05:00:00.000Z")
        self.assertIsNone(to_api_date(None, "America/New_York"))

    def test_api_instant_back_to_display_date(self):
        from opclient import from_api_date
        self.assertEqual(from_api_date("2026-12-31T05:00:00.000Z", "America/New_York"), "2026-12-31")
        self.assertEqual(from_api_date("2026-12-31T00:00:00.000Z", "America/New_York"), "2026-12-30")  # the old bug
        self.assertEqual(from_api_date("Draft", "America/New_York"), "Draft")


class RelationshipLintTest(unittest.TestCase):
    """Top-level relationships: links between existing types (e.g. Vendor -> Finding for questionnaire actions)."""

    def test_rules(self):
        from spec import lint_relationships
        ok = {"relationships": [{"parent": "Vendor", "child": "Finding", "reason": "response action"}]}
        self.assertEqual(lint_relationships(ok), [])
        bad = {"relationships": [{"parent": "Vendor", "child": "Finding"},
                                 {"parent": "Finding", "child": "Vendor", "reason": "x"},
                                 {"parent": "X"}]}
        errs = " | ".join(lint_relationships(bad))
        self.assertIn("add a reason", errs)
        self.assertIn("circular", errs)
        self.assertIn("parent and child are required", errs)


class ExtensionLintTest(unittest.TestCase):
    """type_extensions (field groups on existing types) and workflow_changes (edits to IBM workflows)."""

    def test_rules(self):
        from spec import lint_extensions
        base = {"solution": {"key": "TPR"}}
        ok = dict(base, type_extensions=[{"type": "Finding", "reason": "r", "field_groups": [
                      {"name": "TPR-Fnd", "fields": [{"name": "Source", "type": "enum", "values": ["Vendor Attestation"]}]}]}],
                  workflow_changes=[{"workflow": "Sys-Workflow-Finding", "change": "Applicability", "reason": "r"}])
        self.assertEqual(lint_extensions(ok, {"TPRRemediation"}), [])
        bad = dict(base, type_extensions=[{"type": "Finding", "field_groups": [
                       {"name": "Fnd", "fields": [{"name": "Source", "type": "enum", "required": True}]}]}],
                   workflow_changes=[{"workflow": "X"}])
        errs = " | ".join(lint_extensions(bad, set()))
        for msg in ("add a reason", "should start with solution key", "enum without values",
                    "do not make an added field required", "workflow and change are required"):
            self.assertIn(msg, errs)


class ApplicabilityCheckTest(unittest.TestCase):
    """test_run.py workflow { expect_no_workflow / expect_workflow }: which workflow auto-started on a new object."""

    def _run(self, wf_block, instances):
        import test_run

        class C:
            def shape_fields(self, t, v): return []
            def create_object(self, *a, **k): return {"id": "900"}
            def activity_instances(self, **k): return instances

        r = test_run.Runner(C(), {"tests": {}}, "r1", True)
        with contextlib.redirect_stdout(io.StringIO()):
            r.run({"name": "x", "create": [{"ref": "f", "type": "Finding", "name": "F"}], "workflow": dict(wf_block, object="@f", wait=0)})
        return r.results[-1]

    def test_none_expected(self):
        self.assertTrue(self._run({"expect_no_workflow": True}, [])["ok"])
        res = self._run({"expect_no_workflow": True},
                        [{"id": "5", "grc_object": {"id": "900"}, "workflow": {"name": "Sys-Workflow-Finding"}}])
        self.assertFalse(res["ok"])
        self.assertIn("Sys-Workflow-Finding", res["steps"][-1])

    def test_expected_workflow(self):
        inst = [{"id": "5", "grc_object": {"id": "900"}, "workflow": {"name": "Sys-Workflow-Finding"}},
                {"id": "6", "grc_object": {"id": "123"}, "workflow": {"name": "Other"}}]
        self.assertTrue(self._run({"expect_workflow": "Sys-Workflow-Finding"}, inst)["ok"])
        self.assertFalse(self._run({"expect_workflow": "Sys-Workflow-Finding"}, inst[1:])["ok"])


class AutoStartCollisionTest(unittest.TestCase):
    """verify_spec warns when two enabled auto-start workflows sit on one type (broke a program launch on 9.2.1)."""

    def _verify(self, wfs):
        from verify_spec import verify

        class Src:
            def type_def(self, name): return None
            def workflows(self): return wfs
        return verify({"questionnaires": [{"name": "Q", "asset_types": ["Vendor"]}]}, Src())

    def test_two_enabled_create_workflows_warn(self):
        wfs = [{"id": "65", "name": "Questionnaire Assessment Workflow", "type_definition_name": "QuestionnaireAssessment",
                "type": "create", "is_enabled": True, "state": "published"},
               {"id": "122", "name": "TPR Questionnaire Assessment Workflow", "type_definition_name": "QuestionnaireAssessment",
                "type": "create", "is_enabled": True, "state": "published"}]
        warns = [f for f in self._verify(wfs) if f[0] == "WARN" and "auto-start" in f[2]]
        self.assertEqual(len(warns), 1)
        self.assertIn("id 122", warns[0][2])

    def test_disabled_copy_is_fine(self):
        wfs = [{"id": "65", "name": "A", "type_definition_name": "QuestionnaireAssessment", "type": "create", "is_enabled": True, "state": "published"},
               {"id": "122", "name": "B", "type_definition_name": "QuestionnaireAssessment", "type": "create", "is_enabled": False, "state": "published"}]
        self.assertFalse([f for f in self._verify(wfs) if "auto-start" in f[2]])


class GenFieldsTest(unittest.TestCase):
    """gen_fields.py: spec -> ObjectManager field XML in the shape of a live 9.2.1 dump, and drift detection."""

    SPEC = {"solution": {"key": "TPR", "name": "T"}, "profiles": ["OpenPages Modules Master"],
            "object_types": [{"name": "TPRRemediation", "field_groups": [{"name": "TPR-Rem", "description": "G", "fields": [
                {"name": "Status", "type": "enum", "required": True, "values": ["Draft", "Closed"], "default": "Draft"},
                {"name": "Owner", "type": "user_group", "required": True},
                {"name": "Done", "type": "boolean"}]}]}],
            "type_extensions": [{"type": "Finding", "reason": "r", "field_groups": [{"name": "TPR-Fnd", "fields": [
                {"name": "Source", "type": "enum", "values": ["Vendor Attestation"]}]}]}]}

    PROFILE_REF = ('<openpagesConfiguration xmlFormatVersion="1.31"><objectProfiles explicitListing="false">'
                   '<objectProfile name="OpenPages Modules Master" description="d" enabled="true">'
                   '<includedObjectType name="Finding" displayOrder="38"/>'
                   '<includedObjectType name="TPRRemediation" displayOrder="125"/>'
                   '</objectProfile></objectProfiles></openpagesConfiguration>')

    def _gen(self, spec, ref=None):
        import gen_fields
        import xml.etree.ElementTree as ET
        return gen_fields.build(spec, ref or gen_fields.Reference(root=ET.fromstring(self.PROFILE_REF)))

    def test_display_order_needs_reference(self):
        import gen_fields
        _, errors, _ = gen_fields.build(self.SPEC, gen_fields.Reference(None))
        self.assertTrue(any("displayOrder" in e for e in errors))

    def test_shape_matches_dump_encoding(self):
        root, errors, _ = self._gen(self.SPEC)
        self.assertEqual(errors, [])
        self.assertEqual([c.tag for c in root][:3], ["systemAdminMode", "bundleTypes", "systemAdminMode"])
        st = root.find(".//bundleType[@name='TPR-Rem']/propertyType[@name='Status']")
        self.assertEqual(st.get("dataType"), "Enumerated String")
        self.assertEqual(st.get("defaultValue"), "1")                     # enum default = value number
        self.assertEqual([e.get("value") for e in st.iter("enumValue")], ["1", "2"])
        ow = root.find(".//propertyType[@name='Owner']")
        self.assertEqual((ow.get("dataType"), ow.find("displayType").get("name")), ("Simple String", "User/Group Selector"))
        self.assertEqual(root.find(".//propertyType[@name='Done']").get("defaultValue"), "false")
        self.assertEqual(root.find(".//propertyType[@name='Source']/rpsColumnDefinition").get("contentTypeName"), "Finding")
        prof = root.find("objectProfiles")
        self.assertEqual(prof.get("explicitListing"), "false")
        self.assertIsNotNone(prof.find(".//includedObjectType[@name='Finding']/includedFieldGroup[@name='TPR-Fnd']/includedField[@name='Source']"))
        # 9.2.1 validator rejects includedObjectType without displayOrder
        self.assertEqual({i.get("name"): i.get("displayOrder") for i in prof.iter("includedObjectType")},
                         {"TPRRemediation": "125", "Finding": "38"})

    def test_unconfirmed_types_refused(self):
        import copy
        spec = copy.deepcopy(self.SPEC)
        spec["object_types"][0]["field_groups"][0]["fields"].append({"name": "Tags", "type": "multi_enum", "values": ["a"]})
        root, errors, _ = self._gen(spec)
        self.assertTrue(any("Tags" in e and "no confirmed" in e for e in errors))
        self.assertIsNone(root.find(".//propertyType[@name='Tags']"))

    def test_round_trip_and_drift(self):
        import copy, gen_fields
        live, _, _ = self._gen(self.SPEC)                 # pretend the built system equals the spec
        r2 = gen_fields.Reference(root=live)
        gen, _, _ = self._gen(self.SPEC, r2)
        self.assertEqual([d for d in gen_fields.compare(self.SPEC, gen, r2) if d[0] != "INFO"], [])
        drift = copy.deepcopy(self.SPEC)
        drift["object_types"][0]["field_groups"][0]["fields"][0]["values"] = ["Draft", "Open", "Closed"]
        drift["object_types"][0]["field_groups"][0]["fields"][2]["required"] = True
        gen2, _, _ = self._gen(drift, r2)
        kinds = {(k, w) for k, w, _ in gen_fields.compare(drift, gen2, r2)}
        self.assertIn(("DIFF", "TPR-Rem:Status"), kinds)
        self.assertIn(("DIFF", "TPR-Rem:Done"), kinds)

class GenRelationshipsTest(unittest.TestCase):
    """gen_fields.py --relationships: the UI set is written in full (nothing lost if the loader replaces members)."""

    DUMP = ('<openpagesConfiguration xmlFormatVersion="1.31"><contentTypeRelationshipSets>'
            '<contentTypeRelationshipSet name="SOX Object Model" inheritsFrom="">'
            '<contentTypeRelationship parent="Engagement" child="Finding" type="Association" enabled="true" minParents="1" '
            'maxParents="2147483647" minChildren="0" maxChildren="2147483647"/></contentTypeRelationshipSet>'
            '<contentTypeRelationshipSet name="SOX Extended Object Model" inheritsFrom="SOX Object Model">'
            '<contentTypeRelationship parent="SOXBusEntity" child="Other" type="Attachment" enabled="true" minParents="0" '
            'maxParents="2147483647" minChildren="0" maxChildren="2147483647"/>'
            '<contentTypeRelationship parent="Finding" child="TPRRemediation" type="Association" enabled="true" minParents="0" '
            'maxParents="1" minChildren="0" maxChildren="2147483647"/></contentTypeRelationshipSet>'
            '</contentTypeRelationshipSets></openpagesConfiguration>')
    SPEC = {"object_types": [{"name": "TPRRemediation", "parents": [{"type": "Finding", "primary": True, "max_parents": 1}],
                              "children": ["TPRMilestone"]}],
            "relationships": [{"parent": "Vendor", "child": "Finding", "reason": "r"},
                              {"parent": "Engagement", "child": "Finding", "reason": "r"}]}

    def _ref(self):
        import gen_fields
        import xml.etree.ElementTree as ET
        return gen_fields.RelReference(root=ET.fromstring(self.DUMP))

    def test_whole_set_kept_and_new_added(self):
        import gen_fields
        root, errors, notes = gen_fields.build_relationships(self.SPEC, self._ref())
        self.assertEqual(errors, [])
        sets = list(root.iter("contentTypeRelationshipSet"))
        self.assertEqual([s.get("name") for s in sets], ["SOX Extended Object Model"])     # IBM set never written
        got = {(r.get("parent"), r.get("child"), r.get("type")): r.get("maxParents") for r in sets[0]}
        self.assertIn(("SOXBusEntity", "Other", "Attachment"), got)                        # foreign member kept
        self.assertEqual(got[("Finding", "TPRRemediation", "Association")], "1")
        self.assertIn(("TPRRemediation", "TPRMilestone", "Association"), got)             # new from children
        self.assertIn(("Vendor", "Finding", "Association"), got)                           # new from relationships
        self.assertNotIn(("Engagement", "Finding", "Association"), got)                    # provided by IBM set
        self.assertTrue(any("IBM set" in n for n in notes))

    def test_compare(self):
        import gen_fields, copy
        diffs = gen_fields.compare_relationships(self.SPEC, self._ref())
        self.assertIn(("MISSING", "Vendor -> Finding"), {(k, w) for k, w, _ in diffs})
        spec = copy.deepcopy(self.SPEC)
        del spec["object_types"][0]["parents"][0]["max_parents"]
        self.assertTrue(any(k == "DIFF" and "maxParents" in m for k, _, m in gen_fields.compare_relationships(spec, self._ref())))

    def test_needs_dump(self):
        import gen_fields
        root, errors, _ = gen_fields.build_relationships(self.SPEC, gen_fields.RelReference(None))
        self.assertIsNone(root)
        self.assertTrue(errors)


class UserGuideLintTest(unittest.TestCase):
    """Rules taken from the User Guide 9.2.x ch.9 (object selector op, no variables in response-action object names)."""

    def _qn(self, **ra):
        return {"name": "Q", "scoring": "simple", "lifecycle": "3 Stage Lifecycle (with review)", "asset_types": ["Vendor"],
                "sections": [{"title": "S", "weight": 1, "subsections": [{"title": "s", "weight": 1, "questions": [
                    {"id": "q1", "type": "single", "weight": 1, "text": "t", "answers": [{"text": "Yes", "score": 10}, {"text": "No", "score": 0}]},
                    {"id": "q2", "type": "object_selector", "text": "pick"}]}]}],
                "response_actions": [dict({"name": "a", "operation": "create_object", "child_type": "SOXIssue", "skip_if_exists": True,
                                           "when": {"conditions": [{"question": "q1", "in": ["No"]}]}}, **ra)],
                "workflow": {"name": "W", "operations": []}}

    def test_rules(self):
        from spec import lint_questionnaires
        errs = " | ".join(lint_questionnaires({"questionnaires": [self._qn(object_name="Gap ${asset.name}")]}, set()))
        self.assertIn("object_name uses a ${...} variable", errs)
        self.assertIn("Associate questionnaire object selector responses", errs)
        qn = self._qn(object_name="Gap")
        qn["workflow"]["operations"] = [{"action": "Approve and Close", "operation": "associate_object_selector"}]
        errs2 = " | ".join(lint_questionnaires({"questionnaires": [qn]}, set()))
        self.assertNotIn("object_name uses", errs2)
        self.assertNotIn("object selector responses", errs2)

class ReverseSpecTest(unittest.TestCase):
    """reverse_spec.py: inventory picks non-IBM items; spec draft round-trips through gen_fields --compare."""

    DUMP = """<openpagesConfiguration xmlFormatVersion="1.31">
      <systemInformation name="x" installDate="2026-06-20 03:41:01.0" openpages="11.2.1 (Build: 9.2.1-89 2026/06/19)"/>
      <bundleTypes>
        <bundleType name="OPSS-Iss" description="" type="Content Type" suppliedByVendor="true">
          <propertyType name="Prio" dataType="Integer" required="false" description="" minValue="" maxValue="" defaultValue="">
            <rpsColumnDefinition columnName="prio" contentTypeName="SOXIssue"/><displayType name="Integer"/></propertyType></bundleType>
        <bundleType name="ABC-Main" description="Main" type="Content Type" suppliedByVendor="false">
          <propertyType name="Status" description="" dataType="Enumerated String" minValue="" maxValue="" defaultValue="2" required="true"
                        multiValued="false" searchEnabled="true" currencyCode="" dataLength="">
            <enumType name="Status" description=""><enumValue name="Open" value="1" displayOrder="1"/>
              <enumValue name="Closed" value="2" displayOrder="2"/></enumType>
            <rpsColumnDefinition columnName="status" contentTypeName="ABCCase"/><displayType name="List"/></propertyType>
          <propertyType name="Owner" description="" dataType="Simple String" minValue="" maxValue="" defaultValue="" required="false"
                        multiValued="false" searchEnabled="false" currencyCode="" dataLength="">
            <rpsColumnDefinition columnName="owner" contentTypeName="ABCCase"/><displayType name="User/Group Selector"/></propertyType>
        </bundleType>
        <bundleType name="ABC-Iss" description="" type="Content Type" suppliedByVendor="false">
          <propertyType name="Flag" description="" dataType="Boolean" minValue="" maxValue="" defaultValue="true" required="false"
                        multiValued="false" searchEnabled="false" currencyCode="" dataLength="">
            <rpsColumnDefinition columnName="flag" contentTypeName="SOXIssue"/><displayType name="Boolean"/></propertyType>
        </bundleType>
      </bundleTypes>
      <jspBasedContentTypes>
        <contentType name="SOXIssue" description="Issue" multiVersionable="true" searchEnabled="true" suppliedByVendor="true"/>
        <contentType name="ABCCase" description="A case" multiVersionable="true" searchEnabled="true" suppliedByVendor="false"/>
      </jspBasedContentTypes>
      <contentTypeRelationshipSets>
        <contentTypeRelationshipSet name="SOX Object Model" inheritsFrom="">
          <contentTypeRelationship parent="SOXBusEntity" child="SOXIssue" type="Association" enabled="true" minParents="0" maxParents="2147483647" minChildren="0" maxChildren="2147483647"/>
        </contentTypeRelationshipSet>
        <contentTypeRelationshipSet name="SOX Extended Object Model" inheritsFrom="SOX Object Model">
          <contentTypeRelationship parent="SOXIssue" child="ABCCase" type="Association" enabled="true" minParents="0" maxParents="1" minChildren="0" maxChildren="2147483647"/>
          <contentTypeRelationship parent="Vendor" child="SOXIssue" type="Association" enabled="true" minParents="0" maxParents="2147483647" minChildren="0" maxChildren="2147483647"/>
        </contentTypeRelationshipSet>
      </contentTypeRelationshipSets>
      <queryDefinitions>
        <queryDefinition name="ABC Open" contentType="ABCCase" type="x" visibility="public" expression="Status != Closed" suppliedByVendor="false"/>
        <queryDefinition name="IBM One" contentType="SOXIssue" type="x" visibility="public" expression="" suppliedByVendor="true"/>
      </queryDefinitions>
      <objectStrings><localeStrings name="U.S. English">
        <objectTypeString name="ABCCase" singularValue="Case" pluralValue="Cases"/>
      </localeStrings></objectStrings>
    </openpagesConfiguration>"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "dump.xml").write_text(self.DUMP)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_inventory_and_spec(self):
        import reverse_spec
        import yaml
        d = reverse_spec.Dumps([str(self.tmp / "dump.xml")])
        inv, _ = reverse_spec.inventory(d, [])
        self.assertEqual([s["key"] for s in inv["solutions"]], ["ABC"])
        sol = inv["solutions"][0]
        self.assertEqual(sol["object_types"], ["ABCCase"])
        self.assertEqual(sol["type_extensions"], [{"type": "SOXIssue", "field_groups": ["ABC-Iss"]}])
        self.assertEqual(sol["filters"], ["ABC Open"])                       # IBM filter left out
        self.assertEqual([r["child"] for r in sol["relationships"]], ["SOXIssue"])   # Vendor -> SOXIssue via the extension
        spec, notes = reverse_spec.build_spec(d, sol, [], self.tmp / "raw")
        ot = spec["object_types"][0]
        self.assertEqual((ot["label"], ot["plural_label"], ot["template"]), ("Case", "Cases", "existing"))
        self.assertEqual(ot["parents"], [{"type": "SOXIssue", "max_parents": 1}])
        st = {f["name"]: f for f in ot["field_groups"][0]["fields"]}
        self.assertEqual(st["Status"], {"name": "Status", "type": "enum", "required": True, "values": ["Open", "Closed"],
                                        "default": "Closed", "search": True})
        self.assertEqual(st["Owner"]["type"], "user_group")
        self.assertEqual(spec["type_extensions"][0]["field_groups"][0]["fields"][0], {"name": "Flag", "type": "boolean", "default": True})
        self.assertTrue(any("primary parent" in n for n in notes))
        from spec import lint_spec
        self.assertEqual([e for e in lint_spec(spec) if "no parents" not in e], [])          # existing: true relaxes prefix rules

    def test_round_trip_on_tpr_reference_dumps(self):
        ref = ROOT / "build" / "TPR" / "reference"
        a, b = ref / "tpr-reference-op-config.xml", ref / "tpr-relationships-op-config.xml"
        if not (a.exists() and b.exists()):
            self.skipTest("TPR reference dumps not present")
        import reverse_spec, gen_fields
        d = reverse_spec.Dumps([str(a), str(b)])
        inv, _ = reverse_spec.inventory(d, [])
        sol = next(s for s in inv["solutions"] if s["key"] == "TPR")
        spec, _ = reverse_spec.build_spec(d, sol, [], self.tmp / "raw")
        gen, errors, _ = gen_fields.build(spec, gen_fields.Reference(str(a)))
        self.assertEqual(errors, [])
        diffs = gen_fields.compare(spec, gen, gen_fields.Reference(str(a))) + \
            gen_fields.compare_relationships(spec, gen_fields.RelReference(str(b)))
        self.assertEqual([x for x in diffs if x[0] != "INFO"], [])


from unittest import mock  # noqa: E402  (OmWrapperTest)

class OmWrapperTest(unittest.TestCase):
    """om.py: overlay never touches the client; settings per env; dump option sets; write guards; audit."""

    FAKE = """#!/bin/sh
APP_HOME=$(cd "$(dirname "$0")/.." && pwd -P)
{
  echo "ARGS $*"
  echo "PWD $(pwd -P)"
  echo "JAVA_HOME $JAVA_HOME"
  echo "LIB $(ls "$APP_HOME/lib" | head -1)"
  grep -E '^(rest.url.path|insecure.skip.tls.verify|was_auth_server_url)' openpages-tools-client.properties
  grep -E '^configuration.manager.dump' ObjectManager.properties
  [ -f ObjectManagerExportFilters.xml ] && echo "FILTER yes" || echo "FILTER no"
} > "$OM_TEST_OUT"
if [ "$1" = "d" ]; then echo "<openpagesConfiguration/>" > "$5/$6-op-config.xml"; fi
echo "Process 1 has status: ${OM_TEST_STATUS:-STATUS_FINISHED_SUCCESS}"
"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        cl = self.tmp / "client"
        (cl / "bin").mkdir(parents=True)
        (cl / "lib").mkdir()
        (cl / "lib" / "openpages-tools-client.jar").write_text("x")
        (cl / "bin" / "ObjectManager.sh").write_text("#!/bin/sh\nJAVA_HOME=/opt/ibm/semeru-21\n" + self.FAKE)
        (cl / "bin" / "ObjectManager.sh").chmod(0o755)
        self.orig_props = "rest.url.path = http://opapp:10108/grc/api\ninsecure.skip.tls.verify = true\nwas_auth_server_url =\n"
        (cl / "bin" / "openpages-tools-client.properties").write_text(self.orig_props)
        (cl / "bin" / "ObjectManager.properties").write_text(
            "configuration.manager.dump.bundle.types=true\nconfiguration.manager.dump.content.type.relationship.sets=true\n"
            "configuration.manager.dump.registry=true\nconfiguration.manager.dump.resources.root.folder=/\n")
        (cl / "bin" / "ObjectManagerExportFilters.xml").write_text("<x/>")
        cfg = self.tmp / "proj" / "config"
        cfg.mkdir(parents=True)
        common = f"om_client_dir: {cl}\n    om_java_home: /fake/jdk21\n"
        (cfg / "environments.yaml").write_text(
            "environments:\n"
            f"  local:\n    base_url: https://aimpb.local:10111\n    tier: dev\n    allow_writes: true\n    verify_tls: false\n    auth: basic\n    {common}"
            f"  uat:\n    base_url: https://uat.example\n    tier: uat\n    allow_writes: false\n    verify_tls: true\n    auth: oauth\n"
            f"    client_id_env: OM_T_ID\n    client_secret_env: OM_T_SECRET\n    {common}"
            f"  prod:\n    base_url: https://prod.example\n    tier: prod\n    allow_writes: true\n    auth: basic\n    {common}")
        self.loader = self.tmp / "proj" / "build"
        self.loader.mkdir()
        (self.loader / "x-op-config.xml").write_text("<openpagesConfiguration/>")
        self.out = self.tmp / "out.txt"
        self.env = mock.patch.dict(os.environ, {"OP_CONFIG": str(cfg / "environments.yaml"), "OM_TEST_OUT": str(self.out),
                                                "OP_USER": "admin", "OP_PASSWORD": "pw", "OM_T_ID": "cid", "OM_T_SECRET": "csecret"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_om(self, *args):
        import om
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            rc = om.main(list(args))
        return rc, buf.getvalue(), (self.out.read_text() if self.out.exists() else "")

    def test_validate_local_uses_overlay_and_v1(self):
        rc, _, got = self.run_om("validate", str(self.loader), "x", "--env", "local")
        self.assertEqual(rc, 0)
        self.assertIn(f"ARGS v c admin pw {self.loader.resolve()} x", got)
        self.assertIn("rest.url.path = https://aimpb.local:10111/grc/api", got)
        self.assertIn("insecure.skip.tls.verify = true", got)
        self.assertIn("JAVA_HOME /fake/jdk21", got)                      # pinned server path removed, ours used
        self.assertIn("LIB openpages-tools-client.jar", got)
        self.assertNotIn(str(self.tmp / "client"), got.split("PWD ")[1].split("\n")[0])   # ran in the overlay
        self.assertEqual((self.tmp / "client" / "bin" / "openpages-tools-client.properties").read_text(), self.orig_props)

    def test_dump_relationships_only_that_option_and_no_filter(self):
        rc, out, got = self.run_om("dump", "relationships", "--env", "local", "--out", str(self.tmp / "d"))
        self.assertEqual(rc, 0)
        self.assertIn("configuration.manager.dump.content.type.relationship.sets=true", got)
        self.assertIn("configuration.manager.dump.bundle.types=false", got)
        self.assertIn("configuration.manager.dump.registry=false", got)
        self.assertIn("FILTER no", got)                                    # client's filter file not carried over
        self.assertTrue((self.tmp / "d" / "local-relationships-op-config.xml").exists())

    def test_dump_reference_needs_filter_and_uses_it(self):
        with self.assertRaises(SystemExit):
            self.run_om("dump", "reference", "--env", "local", "--out", str(self.tmp / "d"))
        f = self.tmp / "f.xml"
        f.write_text("<openpagesConfigurationBOM/>")
        rc, _, got = self.run_om("dump", "reference", "--env", "local", "--out", str(self.tmp / "d"), "--filter", str(f))
        self.assertEqual(rc, 0)
        self.assertIn("FILTER yes", got)
        self.assertIn("configuration.manager.dump.registry=true", got)       # reference keeps other options as they are

    def test_oauth_env(self):
        rc, _, got = self.run_om("validate", str(self.loader), "x", "--env", "uat")
        self.assertEqual(rc, 0)
        self.assertIn("ARGS v c cid csecret", got)
        self.assertIn("was_auth_server_url = https://uat.example/oauth2/endpoint/OPOauthProvider", got)
        self.assertIn("insecure.skip.tls.verify = false", got)

    def test_load_guards_and_audit(self):
        import om
        for envname in ("prod", "uat"):
            with self.assertRaises(SystemExit) as cm:
                self.run_om("load", str(self.loader), "x", "--env", envname, "--yes")
            self.assertIn("REFUSED", str(cm.exception))
        rc, _, got = self.run_om("load", str(self.loader), "x", "--env", "local", "--yes")
        self.assertEqual(rc, 0)
        self.assertIn("ARGS l c admin", got)
        audit = (self.tmp / "proj" / "runs" / "audit.jsonl").read_text()
        self.assertIn('"tool": "ObjectManager"', audit)
        self.assertNotIn("pw", json.loads(audit.splitlines()[-1]).get("user", ""))

    def test_error_status_fails_and_log_masks_secret(self):
        with mock.patch.dict(os.environ, {"OM_TEST_STATUS": "STATUS_FINISHED_ERROR"}):
            rc, _, _ = self.run_om("validate", str(self.loader), "x", "--env", "uat")
        self.assertEqual(rc, 2)
        logs = list((self.tmp / "proj" / "runs").glob("om-uat-validate-*.log"))
        self.assertTrue(logs)
        self.assertNotIn("csecret", logs[0].read_text())

    def test_dry_run_runs_nothing(self):
        rc, out, got = self.run_om("validate", str(self.loader), "x", "--env", "local", "--dry-run")
        self.assertEqual(rc, 0)
        self.assertEqual(got, "")
        self.assertIn("********", out)
        self.assertNotIn(" pw ", out)


class OmWindowsTest(OmWrapperTest):
    """om.py on Windows: client launcher .cmd, JAVA_HOME line stripped, lib copied when symlinks are refused."""

    def test_windows_overlay_uses_cmd_and_copies_lib(self):
        import om
        cl = self.tmp / "client"
        (cl / "bin" / "ObjectManager.cmd").write_text('@echo off\r\nset "JAVA_HOME=C:\\opt\\semeru"\r\necho run\r\n')
        env = om.load_env("local")
        with mock.patch.object(om, "IS_WINDOWS", True), \
             mock.patch.object(om.os, "symlink", side_effect=OSError("no symlink privilege")):
            self.assertEqual(om.launcher_name(cl / "bin"), "ObjectManager.cmd")
            self.assertEqual(om.client_dir(env), cl)
            tmp = om.build_overlay(cl, env, "basic", None, None)
        try:
            self.assertFalse((tmp / "lib").is_symlink())
            self.assertTrue((tmp / "lib" / "openpages-tools-client.jar").exists())      # copied
            text = (tmp / "bin" / "ObjectManager.cmd").read_text()
            self.assertNotIn("JAVA_HOME", text)
            self.assertIn("echo run", text)
            self.assertIn("ObjectManager.sh", [f.name for f in (tmp / "bin").iterdir()])  # copied, unused on Windows
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertTrue((cl / "lib" / "openpages-tools-client.jar").exists())            # client untouched

    def test_windows_without_launcher_names_cmd(self):
        import om
        with mock.patch.object(om, "IS_WINDOWS", True):
            with self.assertRaises(SystemExit) as e:
                om.client_dir(om.load_env("local"))
        self.assertIn("ObjectManager.cmd", str(e.exception))


if __name__ == "__main__":
    unittest.main()
