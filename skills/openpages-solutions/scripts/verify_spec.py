#!/usr/bin/env python3
"""
verify_spec.py - check that an environment matches a solution spec (read-only).

  verify_spec.py specs/tpr.yaml                      # against live env (REST)
  verify_spec.py specs/tpr.yaml --from-dump schema/local
  verify_spec.py specs/tpr.yaml --lint-only          # spec sanity only, no env

Checks: object types exist; fields exist with expected data type / required / enum values;
parent+child relationships exist and are enabled; workflows exist on the right type, published,
enabled, with the expected stages and actions (action -> target stage).

Exit code: 0 = all ERROR-free, 1 = errors found. Report also written to runs/verify-<env>-<ts>.md
Severity: ERROR (blocks packaging) | WARN (review) | INFO
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from opclient import OPError, client_from_args, common_args, project_root  # noqa: E402
from spec import CANDIDATES, enum_names, iter_fields, lint_spec, load_file, parent_types, type_map  # noqa: E402


class LiveSource:
    def __init__(self, client):
        self.c = client
        self._types = None

    def type_def(self, name):
        try:
            t = self.c.type_def(name, fields=True)
            t["associations"] = self.c.type_associations(name)
            return t
        except OPError as e:
            if e.status == 404 or e.status == 400:
                return None
            raise

    def workflows(self):
        return self.c.workflow_definitions()


class DumpSource:
    def __init__(self, path):
        self.p = Path(path)

    def type_def(self, name):
        f = self.p / "types" / f"{name}.json"
        return json.loads(f.read_text()) if f.exists() else None

    def workflows(self):
        f = self.p / "workflows.json"
        return json.loads(f.read_text()) if f.exists() else []


def verify(spec, src) -> list[tuple[str, str, str]]:
    findings = []

    def add(sev, where, msg):
        findings.append((sev, where, msg))

    tmap = type_map()
    exts = [{"name": e["type"], "field_groups": e.get("field_groups", []), "_ext": True}
            for e in spec.get("type_extensions", []) or [] if e.get("type")]
    for t in spec.get("object_types", []) + exts:
        tn = t["name"]
        live = src.type_def(tn)
        if not live:
            add("ERROR", tn, "object type not found")
            continue
        if t.get("label") and live.get("localized_label") and t["label"] != live["localized_label"]:
            add("WARN", tn, f"label is '{live['localized_label']}', spec says '{t['label']}'")
        fdefs = {f["name"]: f for f in live.get("field_definitions", [])}
        for full, f in iter_fields(t):
            lf = fdefs.get(full)
            if not lf:
                add("ERROR", f"{tn}.{full}", "field not found on type (field group not added to type, or name mismatch)")
                continue
            want = f["type"]
            got = lf.get("data_type")
            if want in tmap:
                if got not in tmap[want]:
                    add("ERROR", f"{tn}.{full}", f"data_type {got}, expected {sorted(tmap[want])} for '{want}'")
            elif got in CANDIDATES.get(want, set()):
                add("INFO", f"{tn}.{full}", f"data_type {got} for '{want}' matches an unconfirmed default; pin it: config/type_map.yaml -> {want}: [{got}]")
            else:
                add("WARN", f"{tn}.{full}", f"data_type {got} for '{want}' is unconfirmed; if correct pin it: config/type_map.yaml -> {want}: [{got}]")
            if bool(f.get("required")) != bool(lf.get("required")):
                add("WARN", f"{tn}.{full}", f"required={lf.get('required')} (spec {bool(f.get('required'))}); profiles/views can also override required")
            if f.get("values"):
                live_vals = enum_names(lf)
                missing = [v for v in f["values"] if v not in live_vals]
                extra = sorted(live_vals - set(f["values"]))
                if missing:
                    add("ERROR", f"{tn}.{full}", f"missing enum values: {missing}")
                if extra:
                    add("INFO", f"{tn}.{full}", f"extra enum values in env: {extra}")
        assoc = {(str(a.get("relationship", "")).lower(), a.get("name")): a for a in live.get("associations", [])}
        for p in parent_types(t):
            a = assoc.get(("parent", p))
            if not a:
                add("ERROR", tn, f"parent relationship to {p} missing")
            elif not a.get("is_enabled", a.get("enabled", True)):
                add("ERROR", tn, f"parent relationship to {p} exists but is disabled")
        for ch in t.get("children", []):
            a = assoc.get(("child", ch))
            if not a:
                add("ERROR", tn, f"child relationship to {ch} missing")
            elif not a.get("is_enabled", a.get("enabled", True)):
                add("ERROR", tn, f"child relationship to {ch} exists but is disabled")

    for r in spec.get("relationships", []) or []:
        p, c = r.get("parent"), r.get("child")
        where = f"relationship {p} -> {c}"
        live = src.type_def(c)
        if not live:
            add("ERROR", where, f"child type {c} not found")
            continue
        a = {a.get("name"): a for a in live.get("associations", []) if str(a.get("relationship", "")).lower() == "parent"}.get(p)
        if not a:
            add("ERROR", where, f"missing: {c} > Relationships > New Relationship > {p} as parent (SAM on)")
        elif not a.get("is_enabled", a.get("enabled", True)):
            add("ERROR", where, "exists but is disabled")

    # Auto-start collisions (live 9.2.1, 2026-10-21): two enabled "create" workflows on one object type whose
    # Applicability both pass make EVERY object save fail ("multiple workflows to start on object creation";
    # a questionnaire program launch failed with "saveResource"). Applicability is not visible via REST: warn.
    watched = {w.get("object_type") for w in spec.get("workflows", []) or []}
    if spec.get("questionnaires"):
        watched.add("QuestionnaireAssessment")
    try:
        all_wfs = src.workflows()
    except OPError:
        all_wfs = []
    wf_types = {}
    for d in all_wfs:
        wf_types.setdefault(d.get("type_definition_name"), {})[d.get("name")] = d
    for ot in sorted(t for t in watched if t):
        auto = [d for d in wf_types.get(ot, {}).values()
                if str(d.get("type", "")).lower() == "create" and d.get("is_enabled", True) is not False
                and str(d.get("state", "published")).lower() == "published"]
        if len(auto) > 1:
            add("WARN", f"workflows on {ot}",
                "several enabled auto-start workflows: " + ", ".join(sorted(f"{d.get('name')} (id {d.get('id')})" for d in auto))
                + ". Unless their Applicability conditions exclude each other, every new object fails to save; disable the extra one")

    for qn in spec.get("questionnaires", []):
        where = f"questionnaire {qn['name']}"
        qa = src.type_def("QuestionnaireAssessment")
        if not qa:
            add("ERROR", where, "QuestionnaireAssessment object type not found (questionnaire framework not installed?)")
            continue
        qa_parents = {a.get("name") for a in qa.get("associations", []) if str(a.get("relationship", "")).lower() == "parent"}
        for at in qn.get("asset_types", []):
            if at not in qa_parents:
                add("ERROR", where, f"asset type {at} is not an allowed parent of QuestionnaireAssessment")
        fields = {f["name"] for f in qa.get("field_definitions", [])}
        for lf in ("OPLC-QAssessment:LCStage", "OPLC-QAssessment:LCName", "OPLC-Std:LCReadOnly", "OPLC-Std:LCInReview"):
            if fields and lf not in fields:
                add("WARN", where, f"lifecycle field {lf} not visible on QuestionnaireAssessment (profile/field filter?)")
        targets = [ra.get("child_type") for ra in qn.get("response_actions", []) if ra.get("child_type")]
        if (qn.get("low_score_objects") or {}).get("object_type"):
            targets.append(qn["low_score_objects"]["object_type"])
        for tgt in set(targets):
            td = src.type_def(tgt)
            if not td:
                add("ERROR", where, f"response-action target type {tgt} not found")
                continue
            tp = {a.get("name") for a in td.get("associations", []) if str(a.get("relationship", "")).lower() == "parent"}
            if not tp & set(qn.get("asset_types", [])):
                add("ERROR", where, f"{tgt} is not a child of any asset type {qn.get('asset_types')} (response action / low-score object would be skipped)")
        wfn = (qn.get("workflow") or {}).get("name")
        if wfn:
            wfs = [d for d in src.workflows() if d.get("name") == wfn]
            if not wfs:
                add("ERROR", where, f"workflow '{wfn}' not found" + (f" (copy of {(qn.get('workflow') or {}).get('copy_of')})" if (qn.get('workflow') or {}).get('copy_of') else ""))
            elif wfs[0].get("type_definition_name") != "QuestionnaireAssessment":
                add("ERROR", where, f"workflow '{wfn}' is on {wfs[0].get('type_definition_name')}, expected QuestionnaireAssessment")
            else:
                acts = {tr.get("name") for d in wfs for a in d.get("activities", []) for tr in a.get("transitions", [])} | \
                       {tr.get("label") for d in wfs for a in d.get("activities", []) for tr in a.get("transitions", [])}
                by_stage = {}
                for d in wfs:
                    for a in d.get("activities", []):
                        for tr in a.get("transitions", []) or []:
                            for st in (a.get("name"), a.get("label")):
                                by_stage.setdefault(st, set()).update({tr.get("name"), tr.get("label")})
                for op in (qn.get("workflow") or {}).get("operations", []):
                    st = op.get("stage")
                    if st and st not in by_stage:
                        add("ERROR", where, f"workflow stage '{st}' (for {op.get('operation')}) not found")
                    elif op.get("action") not in (by_stage.get(st, set()) if st else acts):
                        add("ERROR", where, f"workflow action '{op.get('action')}'" + (f" on stage '{st}'" if st else "") + f" (for {op.get('operation')}) not found")
        add("INFO", where, "template content, response actions and workflow operations are UI-configured: confirm with plan.py questionnaire checklist + a test program")

    if spec.get("workflows"):
        wfs = src.workflows()
        by_name = {}
        for d in wfs:
            by_name.setdefault(d.get("name"), []).append(d)
        for w in spec["workflows"]:
            cands = by_name.get(w["name"], [])
            if not cands:
                add("ERROR", f"workflow {w['name']}", "not found")
                continue
            d = max(cands, key=lambda x: int(x.get("version_number") or 0))
            if d.get("type_definition_name") != w["object_type"]:
                add("ERROR", f"workflow {w['name']}", f"on type {d.get('type_definition_name')}, spec says {w['object_type']}")
            if d.get("state") != "published":
                add("WARN", f"workflow {w['name']}", f"state={d.get('state')} (draft changes not published?)")
            if d.get("is_enabled") is False:
                add("ERROR", f"workflow {w['name']}", "disabled")
            live_st = {a.get("name"): a for a in d.get("activities", [])}
            live_by_label = {a.get("label"): a for a in d.get("activities", [])}
            for s in w.get("stages", []):
                ls = live_st.get(s["name"]) or live_by_label.get(s["name"])
                if not ls:
                    add("ERROR", f"workflow {w['name']}", f"stage '{s['name']}' not found (live: {sorted(k for k in live_st if k)})")
                    continue
                tr = {x.get("name"): x for x in ls.get("transitions", [])}
                tr_l = {x.get("label"): x for x in ls.get("transitions", [])}
                for a in s.get("actions", []):
                    lt = tr.get(a["name"]) or tr_l.get(a["name"])
                    if not lt:
                        add("ERROR", f"workflow {w['name']}", f"stage '{s['name']}': action '{a['name']}' not found (live: {sorted(k for k in tr if k)})")
                        continue
                    tgt = lt.get("target")
                    tgt_ok = tgt == a["to"] or (live_st.get(tgt) or {}).get("label") == a["to"]
                    if not tgt_ok:
                        add("ERROR", f"workflow {w['name']}", f"action '{s['name']}.{a['name']}' goes to '{tgt}', spec says '{a['to']}'")
                extra = set(tr) - {a["name"] for a in s.get("actions", [])}
                if extra:
                    add("INFO", f"workflow {w['name']}", f"stage '{s['name']}' has extra actions: {sorted(x for x in extra if x)}")
    return findings


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    common_args(ap)
    ap.add_argument("spec")
    ap.add_argument("--from-dump", help="verify against a schema dump dir instead of live REST")
    ap.add_argument("--lint-only", action="store_true")
    args = ap.parse_args(argv)
    spec = load_file(args.spec)
    lint = lint_spec(spec)
    findings = [("ERROR", "spec", m) for m in lint]
    env_name = "lint"
    if not args.lint_only:
        if args.from_dump:
            src, env_name = DumpSource(args.from_dump), Path(args.from_dump).name
        else:
            c = client_from_args(args)
            src, env_name = LiveSource(c), c.env.name
        findings += verify(spec, src)

    order = {"ERROR": 0, "WARN": 1, "INFO": 2}
    findings.sort(key=lambda x: (order[x[0]], x[1]))
    counts = {k: sum(1 for f in findings if f[0] == k) for k in order}
    lines = [f"# Verify `{spec.get('solution', {}).get('name')}` v{spec.get('solution', {}).get('version')} against `{env_name}`", "",
             f"**{counts['ERROR']} errors, {counts['WARN']} warnings, {counts['INFO']} info**", "", "| Sev | Where | Finding |", "|---|---|---|"]
    lines += [f"| {s} | `{w}` | {m} |" for s, w, m in findings]
    report = "\n".join(lines)
    print(report)
    try:
        out = project_root() / "runs" / f"verify-{env_name}-{time.strftime('%Y%m%d-%H%M%S')}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report)
        print(f"\n-> {out}", file=sys.stderr)
    except SystemExit:
        pass
    return 1 if counts["ERROR"] else 0


if __name__ == "__main__":
    sys.exit(main())
