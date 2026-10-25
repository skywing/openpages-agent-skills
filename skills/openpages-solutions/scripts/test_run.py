#!/usr/bin/env python3
"""
test_run.py - run the `tests.scenarios` of a solution spec against a dev/test environment.

For each scenario: create objects (with primary parents + extra associations), then drive the
workflow through the listed actions and assert stage / state / field values after each step.

  test_run.py specs/tpr.yaml                       # DRY RUN: prints the calls it would make
  test_run.py specs/tpr.yaml --apply               # executes (env must allow writes; never prod)
  test_run.py specs/tpr.yaml --apply --only "rework loop" --cleanup --junit runs/junit.xml

Every created object id is recorded in runs/test-<env>-<ts>.json (the run manifest).
--cleanup soft-deletes them at the end (reverse creation order); or later: cleanup.py <manifest>.

Scenario schema (see templates/solution-spec.example.yaml):
  create:   [{ref, type, name ('{run}' is replaced by run id), parent ('@ref'|'@fixture'|id|path),
              fields {FieldGroup:Field: value}, children: ['@ref'], parents: ['@ref']}]
  workflow: {object: '@ref', start: <definition name, for manual-start workflows>, expect_stage,
             steps: [{action, expect_stage, expect_state, expect_fields, expect_error}]}

Workflow instance ids: the object is read with include_workflow=true and the first entry of
`workflow_activity_ids` is used as the instance id for GET /workflows/instances/{id} and
POST /workflows/instances/{id}/transition/{action}. It is re-read after every step.
First run on a new version: use -v and confirm this against your environment.
"""
import argparse
import datetime as _dt
import json
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from opclient import (OPError, WriteRefused, _BARE_DATE, client_from_args, common_args, from_api_date,  # noqa: E402
                      project_root, write_args)
from spec import load_spec, resolve_template  # noqa: E402


def norm(v):
    if isinstance(v, dict):
        return v.get("name") or v.get("localized_label") or v.get("id")
    if isinstance(v, list):
        return sorted(str(norm(x)) for x in v)
    return v


class Runner:
    def __init__(self, c, spec, run_id, apply):
        self.c, self.spec, self.run_id, self.apply = c, spec, run_id, apply
        self.refs: dict[str, str] = {}
        self.created: list[dict] = []
        self.results: list[dict] = []
        self._fixture_cache: dict[str, str] = {}

    # ---------- references
    def resolve(self, ref):
        if ref is None:
            return None
        ref = str(ref)
        if not ref.startswith("@"):
            return self._to_id(ref)
        key = ref[1:]
        if key in self.refs:
            return self.refs[key]
        fx = (self.spec.get("tests") or {}).get("fixtures", {})
        if key in fx:
            return self._to_id(str(fx[key]))
        raise SystemExit(f"Unknown reference {ref}")

    def _to_id(self, v):
        if v.isdigit():
            return v
        if v not in self._fixture_cache:
            # REST GET /contents/{id} takes a numeric id only (a path gives HTTP 500 RESTEASY003210).
            # Accept "Type:Name" and look the id up with a read-only query.
            if ":" not in v or v.startswith("/"):
                raise SystemExit(f"fixture '{v}' must be a numeric object id or 'Type:Name' (e.g. 'Finding:My Finding'); "
                                 "REST cannot resolve a folder path. Find ids with: ./op op.py query \"SELECT [Resource ID],[Name] FROM [Finding]\"")
            otype, name = v.split(":", 1)
            esc = name.replace("'", "''")
            rows = list(self.c.query(f"SELECT [Resource ID] FROM [{otype.strip()}] WHERE [Name] = '{esc}'"))
            if len(rows) != 1:
                raise SystemExit(f"fixture '{v}' matched {len(rows)} objects; use the numeric id instead")
            self._fixture_cache[v] = str(rows[0]["Resource ID"])
        return self._fixture_cache[v]

    # ---------- workflow helpers
    OWNER_KEYS = {"grc_object_id", "object_id", "content_id", "resource_id"}

    @staticmethod
    def _owner_ids(node, out=None):
        """Values of keys that name the GRC object an instance belongs to (exact key names only:
        a loose match also caught ids such as object_type_id and wrongly rejected the right instance)."""
        out = set() if out is None else out
        if isinstance(node, dict):
            for k, v in node.items():
                if str(k).lower() in Runner.OWNER_KEYS and isinstance(v, (str, int)) and str(v).isdigit():
                    out.add(str(v))
                else:
                    Runner._owner_ids(v, out)
        elif isinstance(node, list):
            for x in node:
                Runner._owner_ids(x, out)
        return out

    @staticmethod
    def _stage(inst):
        """(name, label) of the current activity; tolerant of the shapes seen on 9.2.1:
        {workflow:{activity:{name,label}}}, {activity:{...}}, or flat activity_name/activity_label."""
        if not isinstance(inst, dict):
            return None, None
        for path in (("workflow", "activity"), ("activity",), ("current_activity",), ("workflow", "current_activity")):
            node = inst
            for k in path:
                node = node.get(k) if isinstance(node, dict) else None
            if isinstance(node, dict) and (node.get("name") or node.get("label")):
                return node.get("name"), node.get("label")
        for holder in (inst, inst.get("workflow") if isinstance(inst.get("workflow"), dict) else {}):
            if holder.get("activity_name") or holder.get("activity_label"):
                return holder.get("activity_name"), holder.get("activity_label")
        return None, None

    def wf_state_once(self, obj_id, hint=None):
        """Current workflow state of an object. `hint` = activity_instance_id returned by the last transition
        (a transition creates a NEW activity instance, so the id seen before it is stale).
        Without a hint, workflow_activity_ids is scanned and only an instance that belongs to THIS object is used:
        live 9.2.1 showed ids from other objects/older activities, which made later scenarios drive the wrong object."""
        o = self.c.get_object(obj_id, include_workflow=True)
        ids = [str(i) for i in (o.get("workflow_activity_ids") or [])]
        if not hint:
            # Reliable lookup (live 9.2.1): active activity instances, filtered by the owning object.
            # content.workflow_activity_ids is NOT an activity-instance id and pointed at other objects.
            try:
                mine = [a for a in self.c.activity_instances()
                        if str((a.get("grc_object") or {}).get("id")) == str(obj_id)]
            except OPError:
                mine = []
            if mine:
                act = max(mine, key=lambda a: int(a["id"]) if str(a.get("id", "")).isdigit() else 0)
                aid = str(act["id"])
                full = self.c.workflow_instance(aid)
                sname, slabel = self._stage(full)
                return {"object": o, "instance_id": aid, "instance": full or act, "ids": ids, "foreign": None,
                        "stage_name": sname or act.get("status"), "stage_label": slabel or act.get("status"),
                        "status": (full or {}).get("status") or act.get("status")}
        wf = o.get("workflow") or {}
        cands = [str(hint)] if hint else (list(reversed(ids)) or ([str(wf["id"])] if wf.get("id") else []))
        inst_id, inst, fallback = None, None, None
        foreign = None
        if len(cands) == 1:                    # the object lists exactly one instance: use it if it is this object's
            cand = self.c.workflow_instance(cands[0])
            owners = self._owner_ids(cand)
            if owners and str(obj_id) not in owners:
                foreign = (cands[0], sorted(owners))   # live 9.2.1: object listed another object's instance
            else:
                inst_id, inst = cands[0], cand
            cands = []
        for cid in cands[:8]:
            cand = self.c.workflow_instance(cid)
            owners = self._owner_ids(cand)
            if owners and str(obj_id) not in owners:
                continue                      # belongs to another object
            if not owners and fallback is None:
                fallback = (cid, cand)        # no owner info in this payload: usable only as a last resort
                continue
            inst_id, inst = cid, cand
            if hint or str((cand or {}).get("status", "")).lower() not in ("completed", "complete", "closed"):
                break
        if inst_id is None and fallback:
            inst_id, inst = fallback
        sname, slabel = self._stage(inst)
        status = (inst or {}).get("status") or ((inst or {}).get("workflow") or {}).get("status") or (inst or {}).get("process_state")
        return {"object": o, "instance_id": inst_id, "instance": inst, "ids": ids, "foreign": foreign,
                "stage_name": sname, "stage_label": slabel, "status": status}

    def wf_state(self, obj_id, hint=None, expected=None, settle=True, timeout=15):
        """wf_state_once, but waits for the workflow to settle: live 9.2.1 starts workflows and runs automatic
        actions asynchronously, so a read right after create/transition can show no stage (or the old one)."""
        deadline = time.time() + (timeout if settle else 0)
        while True:
            st = self.wf_state_once(obj_id, hint)
            has_stage = bool(st["stage_name"] or st["stage_label"])
            if not settle or time.time() >= deadline:
                if st.get("foreign") and not st["instance_id"]:
                    fid, owners = st["foreign"]
                    raise AssertionError(f"SAFETY STOP: object {obj_id} lists workflow instance {fid}, which belongs to object(s) "
                                         f"{owners}. Not transitioning another object. (workflow_activity_ids is unreliable here)")
                return st
            if has_stage and (expected is None or self.check_stage(st, expected)):
                return st
            time.sleep(1)

    def check_stage(self, st, expected):
        return expected in (st.get("stage_name"), st.get("stage_label"), st.get("status"))

    def check_fields(self, obj, expected):
        bad = []
        live = {f.get("name"): f.get("value") for f in obj.get("fields", [])}
        tz = getattr(getattr(self.c, "env", None), "timezone", "") or ""
        for k, v in expected.items():
            got = norm(live.get(k))
            if isinstance(v, (str, _dt.date)) and _BARE_DATE.match(str(v)):
                got = from_api_date(got, tz)   # compare a spec date with the API instant in the display zone
                v = str(v)
            if got != norm(v):
                bad.append(f"{k}: got {got!r}, expected {v!r}")
        return bad

    # ---------- scenario
    def run(self, sc):
        name = sc["name"]
        steps = []
        ok = True
        manual = []
        t0 = time.time()
        ctx = {"run": self.run_id}
        try:
            for spec_obj in sc.get("create", []):
                o = resolve_template(spec_obj, ctx)
                parent = self.resolve(o.get("parent"))
                payload = self.c.shape_fields(o["type"], o.get("fields", {}))
                res = self.c.create_object(o["type"], o["name"], payload, primary_parent_id=parent, description=o.get("description"))
                if res is None:  # dry-run
                    self.refs[o["ref"]] = f"<{o['ref']}>"
                    continue
                oid = str(res["id"])
                self.refs[o["ref"]] = oid
                self.created.append({"ref": o["ref"], "id": oid, "type": o["type"], "name": o["name"]})
                steps.append(f"created {o['type']} {oid} '{o['name']}'")
                for ch in o.get("children", []):
                    self.c.associate(oid, [self.resolve(ch)], "child")
                for p in o.get("parents", []):
                    self.c.associate(oid, [self.resolve(p)], "parent")
            wf = sc.get("workflow")
            if wf and self.apply and ("expect_no_workflow" in wf or "expect_workflow" in wf):
                # Applicability check: which workflow (if any) auto-started on the object. Waits `wait` seconds
                # (default 10) because live 9.2.1 starts workflows asynchronously.
                oid = self.resolve(wf["object"])
                deadline = time.time() + float(wf.get("wait", 10))
                mine = []
                while True:
                    mine = [a for a in self.c.activity_instances()
                            if str((a.get("grc_object") or {}).get("id")) == str(oid)]
                    if mine or time.time() >= deadline:
                        break
                    time.sleep(1)
                names = sorted({str(((a.get("workflow") or {}).get("name"))) for a in mine})
                if wf.get("expect_no_workflow"):
                    if mine:
                        raise AssertionError(f"workflow(s) {names} started on {oid}; expected none (Applicability not in effect?)")
                    steps.append(f"no workflow started on {oid} within {wf.get('wait', 10)}s (as expected)")
                if wf.get("expect_workflow"):
                    if wf["expect_workflow"] not in names:
                        raise AssertionError(f"expected workflow {wf['expect_workflow']!r} on {oid}, found {names or 'none'}")
                    steps.append(f"workflow {wf['expect_workflow']!r} started on {oid} (as expected)")
            elif wf and self.apply:
                oid = self.resolve(wf["object"])
                if wf.get("start"):
                    defs = [d for d in self.c.workflow_definitions() if d.get("name") == wf["start"]]
                    if not defs:
                        raise AssertionError(f"workflow definition '{wf['start']}' not found")
                    self.c.start_workflow(defs[0]["id"], oid)
                st = self.wf_state(oid, expected=wf.get("expect_stage"))
                if not st["instance_id"]:
                    raise AssertionError("no active workflow instance on object (auto-start off? applicability conditions not met?)")
                if not (st["stage_name"] or st["stage_label"]):
                    steps.append("raw instance (stage not found in payload): " + json.dumps(st["instance"], default=str)[:2000])
                if wf.get("expect_stage") and not self.check_stage(st, wf["expect_stage"]):
                    raise AssertionError(f"initial stage {st['stage_name']!r}/{st['stage_label']!r}, expected {wf['expect_stage']!r}")
                steps.append(f"workflow instance {st['instance_id']} at {st['stage_label'] or st['stage_name']} (object ids {st['ids']})")
                hint = None
                for step in wf.get("steps", []):
                    act = step["action"]
                    if step.get("manual"):
                        manual.append(f"{act}: {step.get('manual_reason') or 'manual check'}")
                        steps.append(f"MANUAL: '{act}' must be checked in the UI ({step.get('manual_reason') or 'not drivable via REST'}); "
                                     f"object {oid} left at {st.get('stage_label') or st.get('stage_name')} for that check unless --cleanup")
                        break   # later steps depend on this one
                    try:
                        r = self.c.transition(st["instance_id"], act, comment=step.get("comment"))
                        if isinstance(r, dict) and r.get("grc_object_id") and str(r["grc_object_id"]) != str(oid):
                            raise AssertionError(f"SAFETY STOP: '{act}' on instance {st['instance_id']} acted on object "
                                                 f"{r['grc_object_id']}, not {oid}. Check and clean up object {r['grc_object_id']}.")
                        if isinstance(r, dict) and r.get("activity_instance_id"):
                            hint = str(r["activity_instance_id"])
                        if r is None:
                            # live 9.2.1: HTTP 204 with no body = the server did NOT perform the transition
                            # (instance not visible/active for this user). Never count it as success.
                            raise AssertionError(f"action {act!r} on instance {st['instance_id']} returned HTTP 204 (no content): "
                                                 "not performed. Is the workflow active on the object and is the API user an assignee of the current stage?")
                        if step.get("expect_error"):
                            raise AssertionError(f"action {act!r} succeeded but an error was expected")
                        steps.append(f"{act} -> {json.dumps(r)[:300] if r else 'ok'}")
                    except OPError as e:
                        if not step.get("expect_error"):
                            raise AssertionError(f"action {act!r} failed: {e.summary()}")
                        steps.append(f"{act} rejected as expected: {e.codes or e.status}")
                    if step.get("expect_state") == "completed":
                        # live 9.2.1: the final transition answers {"process_state": "complete"} and the last
                        # activity id still reads as the old stage, so trust the response first.
                        if isinstance(r, dict) and str(r.get("process_state", "")).lower() in ("complete", "completed"):
                            continue
                        st2 = self.wf_state(oid, hint, settle=False)
                        if st2["instance_id"] and st2["instance"] and st2["status"] not in (None, "completed", "Completed"):
                            raise AssertionError(f"expected workflow completed, still at {st2['stage_label'] or st2['stage_name']}")
                        continue
                    st = self.wf_state(oid, hint, expected=step.get("expect_stage"))
                    if step.get("expect_stage") and not self.check_stage(st, step["expect_stage"]):
                        if not (st["stage_name"] or st["stage_label"]):
                            steps.append("raw instance (stage not found in payload): " + json.dumps(st["instance"], default=str)[:2000])
                        raise AssertionError(f"after {act!r}: stage {st['stage_name']!r}/{st['stage_label']!r}, expected {step['expect_stage']!r}")
                    if step.get("expect_fields"):
                        bad = self.check_fields(st["object"], step["expect_fields"])
                        if bad:
                            raise AssertionError(f"after {act!r}: " + "; ".join(bad))
            elif wf and ("expect_no_workflow" in wf or "expect_workflow" in wf):
                print(f"[dry-run] check workflow auto-start on {wf['object']}: "
                      + ("none expected" if wf.get("expect_no_workflow") else f"expect {wf.get('expect_workflow')}"))
            elif wf:
                for step in wf.get("steps", []):
                    if step.get("manual"):
                        print(f"[dry-run] MANUAL step {step['action']} (check in the UI)")
                        continue
                    print(f"[dry-run] transition {wf['object']} --{step['action']}--> expect {step.get('expect_stage') or step.get('expect_state') or ('error' if step.get('expect_error') else '?')}")
        except (AssertionError, OPError, ValueError) as e:
            ok = False
            steps.append(f"FAIL: {e.summary() if isinstance(e, OPError) else e}")
        self.results.append({"name": name, "ok": ok, "manual": manual, "seconds": round(time.time() - t0, 2), "steps": steps})
        label = "FAIL" if not ok else ("MANUAL" if manual else "PASS")
        print(f"{label:6} {name}")
        for s in steps:
            print(f"      {s}")


def junit(results, path):
    ts = ET.Element("testsuite", name="openpages", tests=str(len(results)), failures=str(sum(not r["ok"] for r in results)))
    for r in results:
        tc = ET.SubElement(ts, "testcase", name=r["name"], time=str(r["seconds"]))
        if not r["ok"]:
            ET.SubElement(tc, "failure", message=r["steps"][-1]).text = "\n".join(r["steps"])
        elif r.get("manual"):
            ET.SubElement(tc, "skipped", message="manual UI check: " + "; ".join(r["manual"])).text = "\n".join(r["steps"])
        else:
            ET.SubElement(tc, "system-out").text = "\n".join(r["steps"])
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(ts).write(path, encoding="utf-8", xml_declaration=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    common_args(ap); write_args(ap)
    ap.add_argument("spec")
    ap.add_argument("--only", help="run only the scenario with this name")
    ap.add_argument("--cleanup", action="store_true", help="soft-delete created objects at the end")
    ap.add_argument("--junit", help="write JUnit XML report to this path")
    args = ap.parse_args(argv)
    spec = load_spec(args.spec)
    c = client_from_args(args, apply=args.apply)
    if args.apply and not c.env.allow_writes:
        raise SystemExit(f"env {c.env.name} does not allow writes")
    run_id = time.strftime("%m%d%H%M%S")
    r = Runner(c, spec, run_id, args.apply)
    scen = [s for s in (spec.get("tests") or {}).get("scenarios", []) if not args.only or s["name"] == args.only]
    try:
        for s in scen:
            r.run(s)
    except WriteRefused as e:
        raise SystemExit(str(e))
    finally:
        if args.apply:
            manifest = project_root() / "runs" / f"test-{c.env.name}-{run_id}.json"
            manifest.parent.mkdir(parents=True, exist_ok=True)
            manifest.write_text(json.dumps({"env": c.env.name, "run_id": run_id, "spec": args.spec, "created": r.created, "results": r.results}, indent=2))
            print(f"-> manifest {manifest}")
            if args.cleanup and r.created:
                for o in reversed(r.created):
                    try:
                        c.delete_object(o["id"])
                        print(f"   soft-deleted {o['type']} {o['id']}")
                    except OPError as e:
                        print(f"   could not delete {o['id']}: {e.summary()}")
    if args.junit:
        junit(r.results, args.junit)
    failed = sum(not x["ok"] for x in r.results)
    manual_n = sum(1 for x in r.results if x["ok"] and x.get("manual"))
    print(f"\n{len(r.results) - failed - manual_n}/{len(r.results)} scenarios passed, {failed} failed, "
          f"{manual_n} need a manual UI check{' (dry-run)' if not args.apply else ''}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
