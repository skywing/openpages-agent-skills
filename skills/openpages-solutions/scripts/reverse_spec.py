#!/usr/bin/env python3
"""
reverse_spec.py - reverse-engineer an EXISTING OpenPages solution into a spec (brownfield), from read-only dumps.

Two steps:

  1. inventory   - list what is NOT supplied by IBM, grouped into suggested solutions:
     reverse_spec.py inventory --dump <custom-config dump> [--dump <relationship dump>] [--schema schema/<env>]
       -> build/_reverse/INVENTORY.md
       -> build/_reverse/selection.yaml        (edit: choose key/name and the items that belong to the solution)

  2. spec        - build a spec draft for one solution from the selection:
     reverse_spec.py spec --selection build/_reverse/selection.yaml --key ABC --dump ... [--schema schema/<env>]
       -> specs/<key>.yaml                      (draft; existing: true)
       -> build/<KEY>/reverse/REVERSE-REPORT.md (what was captured, what is partial, TODOs)
       -> build/<KEY>/reverse/raw/...           (raw workflow / view / calculation XML for refinement)

How "custom" is detected (9.2.1, observed on a live dump):
  - contentType, bundleType (field group), queryDefinition (filter), responsiveView, dashboardView: suppliedByVendor="false"
  - relationships: members of the 'SOX Extended Object Model' set (where UI-added relationships live)
  - workflows (processDefinition has no vendor flag): on a custom type -> custom; on an IBM type -> 'review', and
    with --schema the REST created_on is compared with the install date (systemInformation installDate)
  - calculations / rules: on a custom type -> custom; on an IBM type -> 'review'

Proof step after 'spec' (both read-only, safe on prod):
  gen_fields.py specs/<key>.yaml --compare <dump> --relationships <relationship dump>   -> 0 differences
  verify_spec.py specs/<key>.yaml --env <env>                                            -> 0 errors
Never writes to OpenPages.
"""
from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

UNLIMITED = "2147483647"
UI_SET = "SOX Extended Object Model"
# (dataType, displayType or None, multiValued) -> spec type. Confirmed rows match gen_fields.ENCODINGS.
REVERSE_TYPES = [
    (("Enumerated String", None, "true"), "multi_enum"),
    (("Enumerated String", None, None), "enum"),
    (("Integer", None, None), "integer"),
    (("Date", None, None), "date"),
    (("Currency", None, None), "currency"),
    (("Long String", None, None), "long_string"),
    (("Simple String", "User/Group Selector", None), "user_group"),
    (("Simple String", None, None), "simple_string"),
    (("Medium String", None, None), "medium_string"),
    (("Boolean", None, None), "boolean"),
    (("Float", None, None), "decimal"),
    (("Decimal", None, None), "decimal"),
]
CONFIRMED = {"enum", "integer", "date", "currency", "long_string", "user_group", "boolean"}
VIEW_TYPES = {"task": "task", "taskview": "task", "grid": "grid", "gridview": "grid", "creation": "creation",
              "creationview": "creation", "create": "creation"}


# ------------------------------------------------------------------ dump index
class Dumps:
    def __init__(self, paths: list[str]):
        self.roots = [ET.parse(p).getroot() for p in paths]
        self.install_date = ""
        self.version = ""
        self.types, self.bundles, self.labels, self.fstrings = {}, {}, {}, {}
        self.rels: list[tuple[str, dict]] = []
        self.queries, self.views, self.dashboards, self.processes, self.calcs, self.rules = [], [], [], [], [], []
        self.profiles: dict[str, ET.Element] = {}
        for r in self.roots:
            si = r.find("systemInformation")
            if si is not None:
                self.install_date = self.install_date or si.get("installDate", "")
                self.version = self.version or si.get("openpages", "")
            for tag in ("jspBasedContentTypes", "formBasedContentTypes", "fileUploadContentTypes"):
                for ct in r.iter(tag):
                    for c in ct.findall("contentType"):
                        self.types[c.get("name")] = c
            for bt in r.iter("bundleType"):
                self.bundles[bt.get("name")] = bt
            for s in r.iter("objectTypeString"):
                self.labels[s.get("name")] = (s.get("singularValue"), s.get("pluralValue"))
            for s in r.iter("fieldString"):
                self.fstrings[(s.get("fieldGroup"), s.get("name"))] = s
            for s in r.iter("contentTypeRelationshipSet"):
                for rel in s.findall("contentTypeRelationship"):
                    self.rels.append((s.get("name"), dict(rel.attrib)))
            self.queries += list(r.iter("queryDefinition"))
            self.views += list(r.iter("responsiveView"))
            self.dashboards += list(r.iter("dashboardView"))
            self.processes += list(r.iter("processDefinition"))
            self.calcs += list(r.iter("tbCalculation"))
            self.rules += list(r.iter("tbRule"))
            for op in r.iter("objectProfile"):
                self.profiles.setdefault(op.get("name"), op)

    def owner(self, bundle: ET.Element) -> str | None:
        for p in bundle.findall("propertyType"):
            rps = p.find("rpsColumnDefinition")
            if rps is not None and rps.get("contentTypeName"):
                return rps.get("contentTypeName")
        return None


def custom(e: ET.Element) -> bool:
    return str(e.get("suppliedByVendor", "")).lower() == "false"


def prefix(name: str) -> str:
    """'TPRRemediation' -> 'TPR', 'TPR-Rem' -> 'TPR', 'ACME_KRI' -> 'ACME'."""
    m = re.match(r"^([A-Za-z0-9]+?)[-_ :]", name)
    if m:
        return m.group(1).upper()
    m = re.match(r"^([A-Z]{2,})(?=[A-Z][a-z])", name)
    return m.group(1) if m else name[:3].upper()


def load_rest_workflows(schema: str | None) -> list[dict]:
    if not schema:
        return []
    import json
    f = Path(schema) / "workflows.json"
    return json.loads(f.read_text()) if f.exists() else []


# ------------------------------------------------------------------ inventory
def inventory(d: Dumps, rest_wfs: list[dict]) -> tuple[dict, list[str]]:
    ctypes = sorted(n for n, c in d.types.items() if custom(c))
    cset = set(ctypes)
    groups = {}
    for n, b in d.bundles.items():
        if custom(b):
            groups[n] = d.owner(b)
    ui_rels = [r for s, r in d.rels if s == UI_SET]
    queries = [q for q in d.queries if custom(q)]
    views = [v for v in d.views if custom(v)]
    dashes = [v for v in d.dashboards if custom(v)]
    created = {w.get("name"): w.get("created_on", "") for w in rest_wfs}
    inst = d.install_date[:10]

    def wf_status(p):
        if p.get("objectType") in cset:
            return "custom"
        c = created.get(p.get("name"), "")
        if c and inst and c[:10] > inst:
            return "custom (created after install)"
        return "review"

    # suggested solutions: connected custom types (+ prefix), then attach the rest by object type / prefix
    parent = {t: t for t in ctypes}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for r in ui_rels:
        a, b = r.get("parent"), r.get("child")
        if a in parent and b in parent:
            parent[find(a)] = find(b)
    by_prefix = {}
    for t in ctypes:
        by_prefix.setdefault(prefix(t), []).append(t)
    for ts in by_prefix.values():
        for t in ts[1:]:
            parent[find(t)] = find(ts[0])
    clusters: dict[str, list[str]] = {}
    for t in ctypes:
        clusters.setdefault(find(t), []).append(t)
    sols = []
    for members in clusters.values():
        pre = sorted({prefix(t) for t in members}, key=lambda p: -sum(prefix(t) == p for t in members))[0]
        sols.append({"key": pre, "name": f"{pre} solution (rename)", "object_types": sorted(members),
                     "type_extensions": [], "relationships": [], "filters": [], "views": [], "workflows": [],
                     "calculations": [], "profiles": []})
    sol_of_type = {t: s for s in sols for t in s["object_types"]}
    sol_of_prefix = {s["key"]: s for s in sols}
    unassigned = {"type_extensions": [], "relationships": [], "filters": [], "views": [], "workflows": [], "calculations": []}

    def place(kind, item, otype=None, name=""):
        s = sol_of_type.get(otype) or sol_of_prefix.get(prefix(name or ""))
        (s[kind] if s else unassigned[kind]).append(item)

    ext: dict[str, dict[str, list]] = {}
    for g, owner in sorted(groups.items()):
        if owner in cset:
            continue
        ext.setdefault(prefix(g), {}).setdefault(owner or "?", []).append(g)
    for pre, owners in ext.items():
        for owner, gs in owners.items():
            item = {"type": owner, "field_groups": gs}
            (sol_of_prefix[pre]["type_extensions"] if pre in sol_of_prefix else unassigned["type_extensions"]).append(item)
    for r in ui_rels:
        a, b = r.get("parent"), r.get("child")
        if a in cset or b in cset:
            continue                                   # covered by object_types parents/children
        item = {"parent": a, "child": b, "type": r.get("type")}
        # attach to a solution that extends either side
        s = next((s for s in sols if any(e["type"] in (a, b) for e in s["type_extensions"])), None)
        (s["relationships"] if s else unassigned["relationships"]).append(item)
    for q in queries:
        place("filters", q.get("name"), q.get("contentType"), q.get("name"))
    for v in views + dashes:
        place("views", v.get("name"), v.get("objectTypeName"), v.get("name"))
    for p in d.processes:
        st = wf_status(p)
        if st.startswith("custom"):
            place("workflows", p.get("name"), p.get("objectType"), p.get("name"))
        else:
            unassigned["workflows"].append(f"{p.get('name')} [review: on IBM type {p.get('objectType')}]")
    seen = {p.get("name") for p in d.processes}
    for w in rest_wfs:                     # REST-only: workflows not in the ObjectManager dump, dated by created_on
        if w.get("name") in seen:
            continue
        otype = w.get("type_definition_name")
        c = str(w.get("created_on", ""))[:10]
        if otype in cset or (c and inst and c > inst):
            place("workflows", w.get("name"), otype, w.get("name"))
    for c in d.calcs:
        if c.get("objectType") in cset:
            place("calculations", c.get("name"), c.get("objectType"))
        else:
            unassigned["calculations"].append(f"{c.get('name')} [review: on {c.get('objectType')}]")
    for s in sols:
        s["profiles"] = sorted(n for n, op in d.profiles.items()
                               if any(i.get("name") in s["object_types"] for i in op.findall("includedObjectType")))
    notes = []
    if not d.profiles:
        notes.append("no objectProfiles in the dumps: profile inclusion will be empty (dump object.profiles too)")
    if not rest_wfs:
        notes.append("no --schema: workflows on IBM types cannot be dated; they are listed for review")
    if not any(s == UI_SET for s, _ in d.rels):
        notes.append(f"no '{UI_SET}' relationship set in the dumps: pass the relationship dump")
    return {"version": d.version, "install_date": d.install_date, "solutions": sols, "unassigned": unassigned}, notes


# ------------------------------------------------------------------ spec
def reverse_field(d: Dumps, group: str, p: ET.Element, notes: list[str]) -> dict:
    dt, disp, mv = p.get("dataType"), (p.find("displayType").get("name") if p.find("displayType") is not None else None), p.get("multiValued")
    stype = None
    for (rdt, rdisp, rmv), t in REVERSE_TYPES:
        if rdt == dt and (rdisp is None or rdisp == disp) and (rmv is None or rmv == mv):
            stype = t
            break
    name = p.get("name")
    f: dict = {"name": name, "type": stype or "simple_string"}
    if stype is None:
        notes.append(f"{group}:{name}: unknown encoding dataType='{dt}' display='{disp}'; set to simple_string, FIX BY HAND")
    elif stype not in CONFIRMED:
        notes.append(f"{group}:{name}: type '{stype}' (dataType '{dt}', display '{disp}') is not a confirmed generator "
                     "encoding: gen_fields will refuse it until confirmed from this dump")
    if p.get("required") == "true":
        f["required"] = True
    vals = sorted(p.iter("enumValue"), key=lambda e: int(e.get("displayOrder") or e.get("value") or 0))
    if vals:
        f["values"] = [e.get("name") for e in vals]
        hidden = [e.get("name") for e in vals if e.get("hidden") == "true"]
        if hidden:
            notes.append(f"{group}:{name}: hidden enum values {hidden} (kept in values; mark them in the UI)")
    dv = p.get("defaultValue") or ""
    if dv:
        if stype in ("enum", "multi_enum") and vals:
            hit = [e.get("name") for e in vals if e.get("value") == dv]
            if hit:
                f["default"] = hit[0]
        elif stype == "boolean":
            if dv == "true":
                f["default"] = True
        else:
            f["default"] = dv
    if p.get("description"):
        f["description"] = p.get("description")
    for a, k in (("minValue", "min"), ("maxValue", "max")):
        if p.get(a):
            v = p.get(a)
            f[k] = int(v) if re.fullmatch(r"-?\d+", v) else v
    if p.get("searchEnabled") == "true":
        f["search"] = True
    if stype == "currency" and p.get("currencyCode") not in ("", "USD", None):
        f["currency"] = p.get("currencyCode")
    if stype == "long_string" and p.get("dataLength") not in ("", "Medium", None):
        f["length"] = p.get("dataLength")
    if stype == "user_group":
        for dtp in p.iter("displayTypeProperty"):
            if dtp.get("name") == "startingGroup":
                v = dtp.find("displayTypePropertyValue")
                if v is not None and v.get("name") not in ("", "OpenPagesApplicationUsers"):
                    f["starting_group"] = v.get("name")
    fs = d.fstrings.get((group, name))
    if fs is not None:
        if fs.get("singularValue") and fs.get("singularValue") != name:
            f["label"] = fs.get("singularValue")
        g = fs.get("guidance")
        if g and g != (f.get("label") or name):
            f["guidance"] = g
    return f


def build_spec(d: Dumps, sel: dict, rest_wfs: list[dict], raw_dir: Path) -> tuple[dict, list[str]]:
    notes: list[str] = []
    key = sel["key"]
    types = list(sel.get("object_types", []) or [])
    tset = set(types)
    ui = [r for s, r in d.rels if s == UI_SET]
    allrels = [r for _, r in d.rels]
    m = re.search(r"Build:\s*([\d.]+-?\d*)", d.version or "")
    spec: dict = {"solution": {"name": sel.get("name", key), "key": key, "version": "0.1.0",
                               "target_version": (m.group(1) if m else d.version) or "9.2.x",
                               "owner": "TODO", "existing": True,
                               "description": "Reverse-engineered from a live environment by reverse_spec.py. Review every TODO."},
                  "profiles": list(sel.get("profiles", []) or [])}
    ots = []
    for t in types:
        ct = d.types.get(t)
        if ct is None:
            notes.append(f"object type {t}: not in the dumps (add it to the dump filter)")
            continue
        lab, plural = d.labels.get(t, (t, t + "s"))
        ot = {"name": t, "label": lab or t, "plural_label": plural or (lab or t) + "s", "template": "existing"}
        if ct.get("description"):
            ot["description"] = ct.get("description")
        parents = []
        for r in allrels:
            if r.get("child") == t and r.get("type") == "Association":
                p = {"type": r.get("parent")}
                if r.get("maxParents") not in (None, UNLIMITED):
                    p["max_parents"] = int(r.get("maxParents"))
                if r.get("minParents") not in (None, "0"):
                    p["min_parents"] = int(r.get("minParents"))
                parents.append(p)
        if parents:
            notes.append(f"{t}: primary parent is not in the dumps; mark one parent 'primary: true' (Task View / creation views show it)")
        else:
            notes.append(f"{t}: no parent relationship found")
        ot["parents"] = parents
        kids = sorted({r.get("child") for r in allrels if r.get("parent") == t and r.get("type") == "Association"
                       and r.get("child") not in tset})
        if kids:
            ot["children"] = kids
        fgs = []
        for gname, b in sorted(d.bundles.items()):
            if d.owner(b) != t or not custom(b):
                continue
            g = {"name": gname}
            if b.get("description"):
                g["description"] = b.get("description")
            g["fields"] = [reverse_field(d, gname, p, notes) for p in b.findall("propertyType")]
            fgs.append(g)
        ot["field_groups"] = fgs
        ots.append(ot)
    spec["object_types"] = ots
    exts = []
    for e in sel.get("type_extensions", []) or []:
        fgs = []
        for gname in e.get("field_groups", []):
            b = d.bundles.get(gname)
            if b is None:
                notes.append(f"field group {gname}: not in the dumps")
                continue
            g = {"name": gname, "fields": [reverse_field(d, gname, p, notes) for p in b.findall("propertyType")]}
            if b.get("description"):
                g["description"] = b.get("description")
            fgs.append(g)
        exts.append({"type": e["type"], "reason": "TODO: why the solution adds this to a shared type", "field_groups": fgs})
    if exts:
        spec["type_extensions"] = exts
    rels = []
    for r in sel.get("relationships", []) or []:
        live = next((x for x in ui if x.get("parent") == r["parent"] and x.get("child") == r["child"]), {})
        item = {"parent": r["parent"], "child": r["child"], "reason": "TODO: why the solution needs this link"}
        if live.get("maxParents") not in (None, UNLIMITED):
            item["max_parents"] = int(live["maxParents"])
        rels.append(item)
    if rels:
        spec["relationships"] = rels
    qmap = {q.get("name"): q for q in d.queries}
    fl = []
    for n in sel.get("filters", []) or []:
        q = qmap.get(n)
        if q is not None:
            fl.append({"name": n, "object_type": q.get("contentType"), "criteria": q.get("expression") or "TODO"})
    if fl:
        spec["filters"] = fl
    vmap = {v.get("name"): v for v in d.views + d.dashboards}
    vl = []
    for n in sel.get("views", []) or []:
        v = vmap.get(n)
        if v is None:
            continue
        vt = VIEW_TYPES.get(str(v.get("viewType", "")).lower().replace(" ", ""), str(v.get("viewType", "")).lower() or "task")
        raw = raw_dir / "views" / f"{safe(n)}.xml"
        save(v, raw)
        vl.append({"name": n, "type": vt, "object_type": v.get("objectTypeName"), "raw": str(raw)})
    if vl:
        spec["views"] = vl
        notes.append(f"views: {len(vl)} captured as name/type/object type + raw XML; sections/fields are refined by hand")
    rest = {w.get("name"): w for w in rest_wfs}
    pmap = {p.get("name"): p for p in d.processes}
    wl = []
    for n in sel.get("workflows", []) or []:
        p = pmap.get(n)
        w = rest.get(n)
        if p is None and w is None:
            notes.append(f"workflow {n}: not in the dumps")
            continue
        item = {"name": n, "object_type": (p.get("objectType") if p is not None else w.get("type_definition_name")),
                "start": "auto" if (w or {}).get("type") == "create" or (p is not None and p.get("type") == "create") else "manual",
                "execute_as_system": (p is not None and p.get("execAsSystem") == "true")}
        if p is not None:
            raw = raw_dir / "workflows" / f"{safe(n)}.xml"
            save(p, raw)
            item["raw"] = str(raw)
        stages = []
        for a in (w or {}).get("activities", []):
            st = {"name": a.get("name")}
            if a.get("type") in ("start", "end"):
                st["type"] = a["type"]
            acts = [{"name": t.get("name"), "to": t.get("target")} for t in a.get("transitions", []) or []]
            if acts:
                st["actions"] = acts
            stages.append(st)
        if stages:
            item["stages"] = stages
        else:
            notes.append(f"workflow {n}: no REST stages (pass --schema); stages must be filled from the raw XML")
        wl.append(item)
    if wl:
        spec["workflows"] = wl
        notes.append("workflows: stages/actions from REST; assignees, operations, validations and comment settings are "
                     "in the raw XML and still to be written into the spec")
    cmap = {c.get("name"): c for c in d.calcs}
    cl = []
    for n in sel.get("calculations", []) or []:
        c = cmap.get(n)
        if c is None:
            continue
        raw = raw_dir / "calculations" / f"{safe(n)}.xml"
        save(c, raw)
        cl.append({"name": n, "object_type": c.get("objectType"), "type": str(c.get("type", "")).lower(),
                   "enabled": c.get("enabled", "true") == "true", "raw": str(raw)})
    if cl:
        spec["calculations_captured"] = cl     # not 'calculations': inputs/set are not parsed yet (lint would fail)
        notes.append("calculations: listed under calculations_captured with raw XML; move each to 'calculations:' with "
                     "inputs/set when refined (references/calculations.md)")
    spec["tests"] = {"fixtures": {}, "scenarios": []}
    spec["open_decisions"] = [{"item": "Reverse-engineered spec review", "status": "open",
                               "note": "resolve every TODO in this file and REVERSE-REPORT.md; add test scenarios"}]
    return spec, notes


def safe(n: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", n)[:80]


def save(e: ET.Element, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(e).write(path, encoding="UTF-8", xml_declaration=True)


def dump_yaml(obj) -> str:
    if yaml is None:
        raise SystemExit("PyYAML required (./op runs with the project venv)")
    return yaml.safe_dump(obj, sort_keys=False, allow_unicode=True, width=120)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("inventory", "spec"):
        sp = sub.add_parser(name)
        sp.add_argument("--dump", action="append", required=True, help="ObjectManager dump (repeat for several)")
        sp.add_argument("--schema", help="dump_schema.py output dir (schema/<env>) for REST workflow stages/dates")
        sp.add_argument("--out", help="project root (default: current directory)")
        if name == "spec":
            sp.add_argument("--selection", required=True)
            sp.add_argument("--key", required=True)
    args = ap.parse_args(argv)
    root = Path(args.out or ".")
    d = Dumps(args.dump)
    rest = load_rest_workflows(args.schema)
    if args.cmd == "inventory":
        inv, notes = inventory(d, rest)
        out = root / "build" / "_reverse"
        out.mkdir(parents=True, exist_ok=True)
        (out / "selection.yaml").write_text(
            "# Edit: one entry per solution. Fix key/name, move items between solutions or from 'unassigned', delete\n"
            "# what is not part of a solution. Then: reverse_spec.py spec --selection build/_reverse/selection.yaml --key <KEY> ...\n"
            + dump_yaml(inv))
        L = [f"# Inventory of non-IBM configuration ({inv['version']}, installed {inv['install_date']})", ""]
        L += [f"- NOTE: {n}" for n in notes] + [""]
        for s in inv["solutions"]:
            L += [f"## Suggested solution `{s['key']}`", ""]
            for k in ("object_types", "type_extensions", "relationships", "profiles", "filters", "views", "workflows", "calculations"):
                if s[k]:
                    L.append(f"- **{k}**: " + ", ".join(x if isinstance(x, str) else str(x) for x in s[k]))
            L.append("")
        L += ["## Unassigned (decide: belongs to a solution, or leave out)", ""]
        for k, v in inv["unassigned"].items():
            if v:
                L.append(f"- **{k}** ({len(v)}): " + ", ".join(x if isinstance(x, str) else str(x) for x in v[:60])
                         + (" ..." if len(v) > 60 else ""))
        (out / "INVENTORY.md").write_text("\n".join(L) + "\n")
        print("\n".join(L))
        print(f"-> {out / 'INVENTORY.md'}\n-> {out / 'selection.yaml'}")
        return 0
    sels = yaml.safe_load(Path(args.selection).read_text())
    sel = next((s for s in sels.get("solutions", []) if s.get("key") == args.key), None)
    if sel is None:
        raise SystemExit(f"key {args.key} not in {args.selection}")
    raw_dir = root / "build" / args.key / "reverse" / "raw"
    spec, notes = build_spec(d, sel, rest, raw_dir)
    spec_path = root / "specs" / f"{args.key.lower()}.yaml"
    if spec_path.exists():
        spec_path = root / "specs" / f"{args.key.lower()}.reversed.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("# DRAFT reverse-engineered by reverse_spec.py - review every TODO before use\n" + dump_yaml(spec))
    rep = root / "build" / args.key / "reverse" / "REVERSE-REPORT.md"
    rep.parent.mkdir(parents=True, exist_ok=True)
    n_fields = sum(len(g["fields"]) for t in spec["object_types"] for g in t["field_groups"]) + \
        sum(len(g["fields"]) for e in spec.get("type_extensions", []) for g in e["field_groups"])
    L = [f"# Reverse-engineering report: {spec['solution']['name']} ({args.key})", "",
         f"Spec draft: `{spec_path}`", "",
         "| Captured | Count | Completeness |", "|---|---|---|",
         f"| object types | {len(spec['object_types'])} | full (labels, description, parents/children, max parents) |",
         f"| fields | {n_fields} | full (type, required, values, default, min/max, search, label) |",
         f"| shared-type field groups | {len(spec.get('type_extensions', []))} | full; reason TODO |",
         f"| relationships between shared types | {len(spec.get('relationships', []))} | full; reason TODO |",
         f"| filters | {len(spec.get('filters', []))} | name, type, criteria expression |",
         f"| views | {len(spec.get('views', []))} | name/type/object type + raw XML |",
         f"| workflows | {len(spec.get('workflows', []))} | stages/actions (REST) + raw XML |",
         f"| calculations | {len(spec.get('calculations_captured', []))} | name/type + raw XML |", "",
         "## Notes and TODOs", ""] + [f"- {n}" for n in notes] + [
         "", "## Prove the draft (read-only, safe on prod)", "",
         f"1. `gen_fields.py {spec_path} --compare <dump> --relationships <relationship dump>` -> 0 differences",
         f"2. `verify_spec.py {spec_path} --env <env>` -> 0 errors",
         "3. Resolve TODOs (primary parents, reasons, owner), refine workflows/views/calculations from raw/, add tests",
         "4. From then on the spec is the source of truth: changes go spec -> generate/plan -> verify -> test -> package"]
    rep.write_text("\n".join(L) + "\n")
    print("\n".join(L))
    print(f"-> {spec_path}\n-> {rep}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
