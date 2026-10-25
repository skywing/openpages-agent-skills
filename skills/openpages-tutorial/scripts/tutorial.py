#!/usr/bin/env python3
"""
tutorial.py - drive the OpenPages Policy Exception (PEX) tutorial for one learner.

  ./op tutorial start --code KN [--owner <OpenPages user>] [--env shared-dev] [--process "KN Tutorial Process"]
  ./op tutorial lessons                 list the lessons and where each one is
  ./op tutorial status [--code KN]      progress
  ./op tutorial next   [--code KN]      the next lesson to do
  ./op tutorial check <n> [--code KN] [--confirm]
                                        check lesson n against the shared environment (read-only)

`start` writes:
  specs/px<code>.yaml                                   your solution spec (from templates/pex-spec.template.yaml)
  build/PX<CODE>/template/ObjectManagerExportFilters-*  filter files for the ObjectManager dumps in lessons 03-05
  runs/tutorial/<CODE>/progress.yaml                    lesson status (runs/ is not in git)

`check` never writes to OpenPages. Lessons whose result REST cannot read (views, calculations, the UI parts of the
questionnaire) are self-checks: the script lists what to confirm, and `--confirm` records that you confirmed it.
Every check from lesson 02 on also enforces the shared-environment naming rule: system names start with PX<CODE>,
labels with "<CODE> ".
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
SOL = SKILL.parent / "openpages-solutions" / "scripts"
sys.path.insert(0, str(SOL))

import yaml  # noqa: E402

from opclient import OPError, OpenPagesClient, load_env, project_root  # noqa: E402

CODE_RE = re.compile(r"^[A-Z]{2,4}$")
DEFAULT_ENV = "shared-dev"

# number, file stem, title, check kind
LESSONS = [
    (0, "00-setup", "Setup and guardrails", "env"),
    (1, "01-explore", "Explore the object model (read-only) and create your test Process", "fixture"),
    (2, "02-spec", "Design the spec: names that last forever", "lint"),
    (3, "03-object-types", "Custom object types from a platform template", "types"),
    (4, "04-relationships", "Relationships: parents, children, links to IBM types", "verify"),
    (5, "05-fields", "Field groups and field types (generated and by hand)", "verify"),
    (6, "06-profiles-views-filters", "Profiles, views and filters", "self"),
    (7, "07-calculations", "GRC calculations: automatic and manual", "self"),
    (8, "08-workflow", "The workflow: stages, actions, validations, operations", "verify"),
    (9, "09-testing", "Automated tests with test_run", "junit"),
    (10, "10-questionnaire", "Questionnaire: template, scoring, response actions, program", "verify"),
    (11, "11-reporting", "Reporting framework: what a change requires", "self"),
    (12, "12-packaging", "Packaging and promotion runbook", "package"),
    (13, "13-capstone", "Capstone: reverse-engineer your solution and finish cleanly", "self"),
]

# What a lesson's checkpoint spec contains (sections of the learner spec that must already be built).
CHECKPOINT = {
    4: {"object_types": "no_fields", "relationships": True},
    5: {"object_types": "full", "relationships": True, "type_extensions": True},
    8: {"object_types": "full", "relationships": True, "type_extensions": True, "workflows": True, "calculations": True},
    10: {"object_types": "full", "relationships": True, "type_extensions": True, "workflows": True, "calculations": True,
         "questionnaires": True},
}

SELF_CHECKS = {
    6: ["Your object types and fields are in the profile listed under `profiles:` (lesson 05 loaded this; confirm in the UI)",
        "Task view `{KEY}Exception-Task` is published with the sections and the Controls grid from the spec",
        "Grid view and creation view exist for `{KEY}Exception`",
        "Filters `{KEY} Open Exceptions` and `{KEY} Expiring Soon` exist and return your test exception",
        "You created one exception and one control through the UI and saw your views"],
    7: ["Calculation `{KEY} Days to Expiry` (automatic) is published; changing Requested Expiry on an exception updates "
        "Days to Expiry within a minute",
        "Calculation `{KEY} Control Counts` (manual) is published; you understand it runs only from the workflow (lesson 08)",
        "You know why Days to Expiry goes stale overnight (automatic calculations re-run on input changes, not daily)"],
    11: ["You can say which reporting action each change in your solution needs (new type, new field, new relationship)",
         "You did NOT drop or re-create the reporting schema, and you asked the environment owner before any framework generation"],
    13: ["`gen_fields --compare` against a fresh reference dump reports 0 differences (build/{KEY}/fields/*-compare.md)",
         "`reverse_spec.py spec` produced a draft from your dumps and you compared it with specs/{spec}",
         "Your workflow `{KEY} Exception Lifecycle` is disabled (or you agreed with the environment owner to keep it)",
         "Your filters are deleted or private, and your test objects are cleaned up (test_run --cleanup)"],
}


# ------------------------------------------------------------------ paths and state
def lesson_file(n: int) -> Path:
    return SKILL / "lessons" / f"{LESSONS[n][1]}.md"


def key_of(code: str) -> str:
    return f"PX{code}"


def state_dir(code: str) -> Path:
    return project_root() / "runs" / "tutorial" / code


def load_progress(code: str | None) -> dict:
    root = project_root() / "runs" / "tutorial"
    if not code:
        code = os.environ.get("OP_TUTORIAL_CODE")
    if not code:
        found = sorted(p.parent.name for p in root.glob("*/progress.yaml"))
        if len(found) != 1:
            raise SystemExit("Which learner? Pass --code XX (or set OP_TUTORIAL_CODE)." +
                             (f" Found: {', '.join(found)}" if found else " Run `tutorial start --code XX` first."))
        code = found[0]
    p = root / code.upper() / "progress.yaml"
    if not p.exists():
        raise SystemExit(f"No tutorial for {code} yet: run `./op tutorial start --code {code.upper()}`")
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def save_progress(prog: dict) -> None:
    p = state_dir(prog["code"]) / "progress.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(prog, sort_keys=False, allow_unicode=True), encoding="utf-8")


def load_learner_spec(prog: dict) -> dict:
    return yaml.safe_load((project_root() / prog["spec"]).read_text(encoding="utf-8"))


# ------------------------------------------------------------------ start
def render_template(code: str, owner: str, process: str) -> str:
    text = (SKILL / "templates" / "pex-spec.template.yaml").read_text(encoding="utf-8")
    for k, v in {"CODE": code, "KEY": key_of(code), "OWNER": owner, "PROCESS": process}.items():
        text = text.replace("{{%s}}" % k, v)
    left = re.findall(r"\{\{\w+\}\}", text)
    if left:
        raise SystemExit(f"template has unknown placeholders: {sorted(set(left))}")
    return text


def filter_files(spec: dict) -> dict[str, str]:
    """ObjectManager export filters: the two platform templates (lesson 03) and the reference dump of the built types."""
    key = spec["solution"]["key"]
    out = {}
    for base in ("SOXIssue", "SOXTask"):
        out[f"ObjectManagerExportFilters-{base}.xml"] = (
            "<openpagesConfigurationBOM xmlFormatVersion=\"1.0\">\n"
            f"  <!-- Template dump for lesson 03: ./om dump reference with this file as filter, prefix {base.lower()} -->\n"
            f"  <jspBasedContentTypes>\n    <contentType name=\"{base}\"/>\n  </jspBasedContentTypes>\n"
            f"  <dependencies>\n    <dependencySet objectType=\"{base}\"/>\n  </dependencies>\n"
            "  <objectStrings>\n    <localeStrings name=\"U.S. English\">\n"
            f"      <objectTypeString name=\"{base}\"/>\n    </localeStrings>\n  </objectStrings>\n"
            "</openpagesConfigurationBOM>\n")
    types = [t["name"] for t in spec.get("object_types", [])]
    groups = [g["name"] for t in spec.get("object_types", []) for g in t.get("field_groups", [])]
    groups += [g["name"] for e in spec.get("type_extensions", []) or [] for g in e.get("field_groups", [])]
    L = ["<openpagesConfigurationBOM xmlFormatVersion=\"1.0\">",
         f"  <!-- Reference dump of YOUR built types (lessons 04, 05, 13): ./om dump reference with this file as filter, prefix {key.lower()}-reference -->",
         "  <jspBasedContentTypes>"] + [f"    <contentType name=\"{t}\"/>" for t in types] + ["  </jspBasedContentTypes>",
         "  <dependencies>"] + [f"    <dependencySet objectType=\"{t}\"/>" for t in types] + ["  </dependencies>",
         "  <bundleTypes>"] + [f"    <bundleType name=\"{g}\"/>" for g in groups] + ["  </bundleTypes>",
         "  <objectProfiles>"] + [f"    <objectProfile name=\"{p}\"/>" for p in spec.get("profiles", [])] + ["  </objectProfiles>",
         "  <objectStrings>", "    <localeStrings name=\"U.S. English\">"]
    L += [f"      <objectTypeString name=\"{t}\"/>" for t in types]
    L += [f"      <fieldString fieldGroup=\"{g}\"/>" for g in groups]
    L += [f"      <enumValueString fieldGroup=\"{g}\"/>" for g in groups]
    L += ["    </localeStrings>", "  </objectStrings>", "</openpagesConfigurationBOM>", ""]
    out[f"ObjectManagerExportFilters-{key}-reference.xml"] = "\n".join(L)
    return out


def cmd_start(a) -> int:
    code = a.code.upper()
    if not CODE_RE.match(code):
        raise SystemExit("--code must be 2-4 letters (your initials), e.g. KN")
    key = key_of(code)
    owner = a.owner or os.environ.get("OP_USER")
    if not owner:
        raise SystemExit("--owner <your OpenPages user name> (or set OP_USER)")
    process = a.process or f"{code} Tutorial Process"
    root = project_root()
    spec_rel = f"specs/{key.lower()}.yaml"
    spec_path = root / spec_rel
    if spec_path.exists() and not a.force:
        raise SystemExit(f"{spec_rel} exists (your work). Use --force only to start over; system names already built stay built.")
    text = render_template(code, owner, process)
    spec = yaml.safe_load(text)
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(text, encoding="utf-8")
    tdir = root / "build" / key / "template"
    tdir.mkdir(parents=True, exist_ok=True)
    for name, body in filter_files(spec).items():
        (tdir / name).write_text(body, encoding="utf-8")
    env = a.env or DEFAULT_ENV
    try:
        load_env(env)
    except SystemExit as e:
        print(f"WARNING: {e}. Add a '{env}' entry to config/environments.yaml before lesson 00's check.")
    prog = {"code": code, "key": key, "owner": owner, "env": env, "spec": spec_rel, "process": process,
            "started": dt.datetime.now().isoformat(timespec="seconds"), "lessons": {}}
    old = state_dir(code) / "progress.yaml"
    if old.exists() and a.force:
        prog["lessons"] = (yaml.safe_load(old.read_text(encoding="utf-8")) or {}).get("lessons", {})
    save_progress(prog)
    print(f"Learner {code}: key {key}, environment {env}, owner {owner}")
    print(f"-> {spec_rel}")
    print(f"-> build/{key}/template/ (ObjectManager filter files)")
    print(f"-> runs/tutorial/{code}/progress.yaml")
    print(f"Next: read {rel(lesson_file(0))}, then ./op tutorial check 0")
    return 0


# ------------------------------------------------------------------ naming rule
def naming_issues(spec: dict, code: str) -> list[str]:
    key = key_of(code)
    errs = []

    def need_key(what, name):
        if not str(name).startswith(key):
            errs.append(f"{what} '{name}' must start with {key}")

    def need_label(what, label):
        if label is not None and not str(label).startswith(f"{code} "):
            errs.append(f"{what} label '{label}' must start with '{code} '")

    if (spec.get("solution") or {}).get("key") != key:
        errs.append(f"solution.key must be {key}")
    for t in spec.get("object_types", []):
        need_key("object type", t.get("name", ""))
        need_label(f"object type {t.get('name')}", t.get("label"))
        need_label(f"object type {t.get('name')} plural", t.get("plural_label"))
        for g in t.get("field_groups", []):
            need_key("field group", g.get("name", ""))
    for e in spec.get("type_extensions", []) or []:
        for g in e.get("field_groups", []):
            need_key(f"field group on {e.get('type')}", g.get("name", ""))
    for sect, what in (("filters", "filter"), ("views", "view"), ("calculations", "calculation"),
                       ("workflows", "workflow"), ("questionnaires", "questionnaire")):
        for x in spec.get(sect, []) or []:
            need_key(what, x.get("name", ""))
    for q in spec.get("questionnaires", []) or []:
        for ra in q.get("response_actions", []) or []:
            if ra.get("object_name") and not str(ra["object_name"]).startswith(f"{code} "):
                errs.append(f"response action '{ra.get('name')}': object_name '{ra['object_name']}' must start with '{code} '")
    if spec.get("workflow_changes"):
        errs.append("workflow_changes: the tutorial never edits shared workflows; remove this section")
    for sc in (spec.get("tests") or {}).get("scenarios", []):
        for c in sc.get("create", []):
            if not str(c.get("name", "")).startswith(f"{code}-TEST"):
                errs.append(f"test object '{c.get('name')}' must start with '{code}-TEST'")
    return errs


# ------------------------------------------------------------------ checkpoints
def checkpoint_spec(spec: dict, lesson: int) -> dict:
    want = CHECKPOINT[lesson]
    out = {"solution": copy.deepcopy(spec["solution"])}
    if want.get("object_types"):
        types = copy.deepcopy(spec.get("object_types", []))
        if want["object_types"] == "no_fields":
            for t in types:
                t.pop("field_groups", None)
        out["object_types"] = types
    for k in ("relationships", "type_extensions", "workflows", "calculations", "questionnaires"):
        if want.get(k) and spec.get(k):
            out[k] = copy.deepcopy(spec[k])
    if "profiles" in spec:
        out["profiles"] = list(spec["profiles"])
    return out


def run_script(script: str, *args: str) -> int:
    cmd = [sys.executable, str(SOL / script), *args]
    print(f"$ {' '.join(Path(c).name if i == 1 else c for i, c in enumerate(cmd))}")
    return subprocess.call(cmd, cwd=project_root())


def client(prog: dict) -> OpenPagesClient:
    return OpenPagesClient(load_env(prog["env"]))


# ------------------------------------------------------------------ checks
def check_env(prog, spec, a) -> bool:
    env = load_env(prog["env"])
    ok = True
    print(f"environment {env.name}: tier={env.tier} url={env.base_url} writes={'allowed' if env.allow_writes else 'blocked'}")
    if env.tier == "prod":
        print("FAIL  the tutorial never runs against a prod-tier environment"); return False
    if not env.allow_writes:
        print("FAIL  allow_writes is false: lessons 03-10 create configuration and test data"); ok = False
    try:
        c = client(prog)
        n = len(c.types())
        print(f"PASS  REST login works ({n} object types visible)")
        try:
            print(f"INFO  System Admin Mode now: {c.admin_mode()}")
        except OPError as e:
            print(f"INFO  System Admin Mode unreadable ({e.status}): you may lack admin rights")
    except (OPError, OSError, EOFError) as e:
        print(f"FAIL  cannot reach {env.base_url} ({type(e).__name__}: {e}): check base_url and the credential variables "
              f"{env.username_env}/{env.password_env}"); return False
    return ok


def check_fixture(prog, spec, a) -> bool:
    name = prog["process"]
    c = client(prog)
    esc = name.replace("'", "''")
    rows = list(c.query(f"SELECT [Resource ID], [Name] FROM [SOXProcess] WHERE [Name] = '{esc}'"))
    if len(rows) == 1:
        print(f"PASS  test Process '{name}' exists (id {rows[0].get('Resource ID')})")
        return True
    print(f"FAIL  {len(rows)} Process objects named '{name}': create exactly one (lesson 01, step 4)")
    return False


def check_lint(prog, spec, a) -> bool:
    ok = run_script("verify_spec.py", prog["spec"], "--lint-only") == 0
    try:
        c = client(prog)
        mine = {t["name"] for t in spec.get("object_types", [])}
        taken = sorted(t["name"] for t in c.types() if t.get("name", "").startswith(prog["key"]) and t["name"] not in mine)
        if taken:
            print(f"FAIL  other object types already use your key {prog['key']}: {taken}. Pick another --code and start again")
            ok = False
        else:
            print(f"PASS  key {prog['key']} is free in {prog['env']}")
    except (OPError, OSError, EOFError) as e:
        print(f"FAIL  could not check that key {prog['key']} is free in {prog['env']} ({type(e).__name__}: {e}); "
              "set the credentials and re-run")
        ok = False
    return ok


def check_types(prog, spec, a) -> bool:
    c = client(prog)
    ok = True
    for t in spec.get("object_types", []):
        try:
            d = c.type_def(t["name"], fields=False)
            lbl = d.get("localized_label") or d.get("label")
            print(f"PASS  {t['name']} exists (label '{lbl}')")
            if lbl and t.get("label") and lbl != t["label"]:
                print(f"WARN  label differs from the spec ('{t['label']}'): fix it in the UI or the spec")
        except OPError as e:
            print(f"FAIL  {t['name']} not found ({e.status}): derive, validate and load it (lesson 03)")
            ok = False
    return ok


def check_verify(prog, spec, a, lesson) -> bool:
    cp = checkpoint_spec(spec, lesson)
    p = state_dir(prog["code"]) / f"checkpoint-{lesson:02d}.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(cp, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return run_script("verify_spec.py", str(p.relative_to(project_root())), "--env", prog["env"]) == 0


def check_junit(prog, spec, a) -> bool:
    p = state_dir(prog["code"]) / "junit.xml"
    if not p.exists():
        print(f"FAIL  no test report: run test_run with --apply --cleanup --junit runs/tutorial/{prog['code']}/junit.xml")
        return False
    r = ET.parse(p).getroot()
    suites = [r] if r.tag == "testsuite" else list(r.iter("testsuite"))
    tests = sum(int(s.get("tests", 0)) for s in suites)
    bad = sum(int(s.get("failures", 0)) + int(s.get("errors", 0)) for s in suites)
    want = len((spec.get("tests") or {}).get("scenarios", []))
    print(f"{'PASS' if not bad and tests >= want else 'FAIL'}  {tests} tests, {bad} failed/errored (spec has {want} scenarios)")
    return not bad and tests >= want


def check_package(prog, spec, a) -> bool:
    p = project_root() / "build" / prog["key"] / "PACKAGE.md"
    if p.exists():
        print(f"PASS  {p.relative_to(project_root())} exists; read it top to bottom (lesson 12)")
        return True
    print(f"FAIL  run: ./op plan.py package {prog['spec']}")
    return False


def check_self(prog, spec, a, lesson) -> bool:
    items = [s.format(KEY=prog["key"], spec=Path(prog["spec"]).name) for s in SELF_CHECKS[lesson]]
    print("Self-check (REST cannot read these). Confirm each one:")
    for i in items:
        print(f"  [ ] {i}")
    if a.confirm:
        print("CONFIRMED by the learner (--confirm)")
        return True
    if sys.stdin.isatty():
        return input("All done? [y/N] ").strip().lower() in ("y", "yes")
    print("Not confirmed: re-run with --confirm once every item is true")
    return False


def cmd_check(a) -> int:
    prog = load_progress(a.code)
    n = a.lesson
    if not 0 <= n < len(LESSONS):
        raise SystemExit(f"lesson must be 0-{len(LESSONS) - 1}")
    _, stem, title, kind = LESSONS[n]
    print(f"== Lesson {n:02d}: {title}  (learner {prog['code']}, env {prog['env']})")
    spec = load_learner_spec(prog) if n >= 2 else {}
    ok = True
    if n >= 2:
        issues = naming_issues(spec, prog["code"])
        for i in issues:
            print(f"FAIL  naming: {i}")
        ok = not issues
        if ok:
            print("PASS  every name carries your code")
    if n == 10:
        ok = run_script("qr_score.py", prog["spec"]) == 0 and ok
    fn = {"env": check_env, "fixture": check_fixture, "lint": check_lint, "types": check_types, "junit": check_junit,
          "package": check_package}.get(kind)
    if fn:
        try:
            ok = fn(prog, spec, a) and ok
        except (OPError, OSError, EOFError, SystemExit) as e:
            print(f"FAIL  {type(e).__name__}: {e} (is {prog['env']} reachable, are the credential variables set?)")
            ok = False
    elif kind == "verify":
        ok = check_verify(prog, spec, a, n) and ok
    elif kind == "self":
        ok = check_self(prog, spec, a, n) and ok
    prog.setdefault("lessons", {})[n] = {"status": "passed" if ok else "failed",
                                         "checked": dt.datetime.now().isoformat(timespec="seconds")}
    save_progress(prog)
    print(f"\nLesson {n:02d}: {'PASSED' if ok else 'NOT YET'}")
    if ok and n + 1 < len(LESSONS):
        print(f"Next: lesson {n + 1:02d} - {LESSONS[n + 1][2]}  ({rel(lesson_file(n + 1))})")
    return 0 if ok else 1


# ------------------------------------------------------------------ status / next / lessons
def rel(p: Path) -> str:
    try:
        return str(p.relative_to(project_root()))
    except ValueError:
        return str(p)


def cmd_lessons(a) -> int:
    for n, stem, title, kind in LESSONS:
        print(f"{n:02d}  {title:<70} {rel(lesson_file(n))}")
    return 0


def cmd_status(a) -> int:
    prog = load_progress(a.code)
    print(f"Learner {prog['code']}  key {prog['key']}  env {prog['env']}  spec {prog['spec']}")
    done = prog.get("lessons", {})
    for n, stem, title, kind in LESSONS:
        st = done.get(n, {})
        mark = {"passed": "x", "failed": "!"}.get(st.get("status"), " ")
        print(f"  [{mark}] {n:02d} {title}" + (f"   ({st['checked']})" if st.get("checked") else ""))
    return 0


def cmd_next(a) -> int:
    prog = load_progress(a.code)
    done = prog.get("lessons", {})
    for n, stem, title, kind in LESSONS:
        if done.get(n, {}).get("status") != "passed":
            print(f"Lesson {n:02d}: {title}\n  read: {rel(lesson_file(n))}\n  then: ./op tutorial check {n}")
            return 0
    print("All lessons passed. Well done.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("start")
    p.add_argument("--code", required=True, help="your initials, 2-4 letters")
    p.add_argument("--owner", help="your OpenPages user name (default $OP_USER)")
    p.add_argument("--env", help=f"environment (default {DEFAULT_ENV})")
    p.add_argument("--process", help="name of your test Process (default '<CODE> Tutorial Process')")
    p.add_argument("--force", action="store_true", help="overwrite your spec (start over)")
    sub.add_parser("lessons")
    for name in ("status", "next"):
        p = sub.add_parser(name)
        p.add_argument("--code")
    p = sub.add_parser("check")
    p.add_argument("lesson", type=int)
    p.add_argument("--code")
    p.add_argument("--confirm", action="store_true", help="record a self-check as confirmed (only when it is true)")
    a = ap.parse_args(argv)
    return {"start": cmd_start, "lessons": cmd_lessons, "status": cmd_status, "next": cmd_next, "check": cmd_check}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
