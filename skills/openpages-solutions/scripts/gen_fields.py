#!/usr/bin/env python3
"""
gen_fields.py - generate an ObjectManager loader file for the solution's FIELD GROUPS, FIELDS, ENUM VALUES, FIELD
LABELS and PROFILE INCLUSION from the spec, and/or compare the spec with a reference dump of what is built.

  gen_fields.py specs/tpr.yaml --compare build/TPR/reference/tpr-reference-op-config.xml
      -> drift report only (spec vs. live dump), nothing written except the report
  gen_fields.py specs/tpr.yaml --reference build/TPR/reference/tpr-reference-op-config.xml
      -> build/<KEY>/fields/<key>-fields-op-config.xml   (loader: prefix '<key>-fields')
      -> build/<KEY>/fields/<key>-fields-report.md        (REVIEW BEFORE LOADING)

Covers: object_types[].field_groups and type_extensions[].field_groups (field groups on existing types).
Relationships (--relationships <dump>): the 'SOX Extended Object Model' set (where UI-added relationships live on
9.2.1) is written in FULL - existing members + the spec's - so nothing is lost whether the loader merges or replaces.
Not covered (still UI): views, workflows, calculations.

Encoding rules come from a live 9.2.1 dump (2026-10-22), not from guesses. A spec field type whose encoding has not
been seen in a dump is REFUSED (dump an existing field of that type first, then add it to ENCODINGS):
confirmed: enum, integer, date, currency, long_string, user_group, boolean.

Shape mirrors the dump: SAM-on <bundleTypes> SAM-off, objectProfiles explicitListing="false" (the profile entries listed
are added/updated, others left alone), objectStrings. No DOCTYPE (derive_type.py output loaded fine without one).

Never loads anything. Validate first: ObjectManager.sh v c <user> <pw> <dir> <prefix>; load: l c ... (SAM handled
by the systemAdminMode elements in the file). Policy: no SQL/DDL, never drop or re-create the reporting schema.
"""
from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from spec import load_spec  # noqa: E402

# spec type -> (dataType, displayType, extra propertyType attrs, displayTypeProperty defaults)
ENCODINGS = {
    "enum":        ("Enumerated String", "List", {"multiValued": "false", "isHierarchical": "false"}, {}),
    "integer":     ("Integer", "Integer", {}, {}),
    "date":        ("Date", "Date", {}, {}),
    "currency":    ("Currency", "Currency", {}, {"exchangeRateReadOnly": None}),
    "long_string": ("Long String", "Text Area", {"dataLength": "Medium"}, {}),
    "user_group":  ("Simple String", "User/Group Selector", {},
                    {"includeDisabled": "false", "includeSubGroups": "true", "minimumAccess": "",
                     "startingGroup": "OpenPagesApplicationUsers"}),
    "boolean":     ("Boolean", "Boolean", {}, {}),
}
UNCONFIRMED = {"multi_enum", "decimal", "simple_string", "medium_string", "business_entity"}
SYSTEM_GROUPS = {"System Fields"}
PROP_ATTR_ORDER = ["name", "description", "dataType", "minValue", "maxValue", "defaultValue", "required", "encrypted",
                   "currencyCode", "isDimension", "isFact", "multiValued", "isHierarchical", "searchEnabled",
                   "includeConversion", "suppliedByVendor", "dataLength"]
# attributes compared between spec and dump (rps column names are server-assigned: reported, not failed)
COMPARE_ATTRS = ["dataType", "description", "minValue", "maxValue", "defaultValue", "required", "currencyCode",
                 "multiValued", "searchEnabled", "dataLength"]


def b(v) -> str:
    return "true" if v else "false"


def column_name(field: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", field.lower()).strip("_")[:30]


def groups_by_owner(spec: dict) -> list[tuple[str, dict, bool]]:
    """(owner type, field group dict, is_extension) for every solution field group."""
    out = []
    for t in spec.get("object_types", []) or []:
        for g in t.get("field_groups", []) or []:
            out.append((t["name"], g, False))
    for e in spec.get("type_extensions", []) or []:
        for g in e.get("field_groups", []) or []:
            out.append((e["type"], g, True))
    return out


# ------------------------------------------------------------------ reference dump
class Reference:
    def __init__(self, path: str | None = None, root: ET.Element | None = None):
        self.root = root if root is not None else (ET.parse(path).getroot() if path else None)
        self.props: dict[tuple[str, str], ET.Element] = {}
        self.bundles: dict[str, ET.Element] = {}
        self.strings: dict[tuple, ET.Element] = {}
        self.profiles: dict[str, ET.Element] = {}
        if self.root is None:
            return
        for bt in self.root.iter("bundleType"):
            self.bundles[bt.get("name")] = bt
            for p in bt.findall("propertyType"):
                self.props[(bt.get("name"), p.get("name"))] = p
        for s in self.root.iter("fieldString"):
            self.strings[("field", s.get("fieldGroup"), s.get("name"))] = s
        for s in self.root.iter("enumValueString"):
            self.strings[("enum", s.get("fieldGroup"), s.get("field"), s.get("name"))] = s
        for op in self.root.iter("objectProfile"):
            self.profiles[op.get("name")] = op

    @property
    def xml_format(self) -> str:
        return self.root.get("xmlFormatVersion", "1.31") if self.root is not None else "1.31"

    def column(self, group, field):
        p = self.props.get((group, field))
        rps = p.find("rpsColumnDefinition") if p is not None else None
        return rps.get("columnName") if rps is not None else None

    def profile_field(self, profile, otype, group, field):
        op = self.profiles.get(profile)
        if op is None:
            return None
        for iot in op.findall("includedObjectType"):
            if iot.get("name") != otype:
                continue
            for g in iot.findall("includedFieldGroup"):
                if g.get("name") != group:
                    continue
                for f in g.findall("includedField"):
                    if f.get("name") == field:
                        return f
        return None


# ------------------------------------------------------------------ build
def build(spec: dict, ref: Reference) -> tuple[ET.Element, list[str], list[str]]:
    errors, notes = [], []
    root = ET.Element("openpagesConfiguration", xmlFormatVersion=ref.xml_format)
    ET.SubElement(root, "systemAdminMode", enabled="true")
    bundles = ET.SubElement(root, "bundleTypes")
    strings: list[ET.Element] = []
    profile_rows: list[tuple[str, str, dict, str]] = []   # (owner type, group, field, displayType)

    for owner, g, is_ext in groups_by_owner(spec):
        gname = g["name"]
        bt = ET.SubElement(bundles, "bundleType", name=gname, description=g.get("description", ""),
                           type="Content Type", suppliedByVendor="false")
        for f in g.get("fields", []) or []:
            ftype, fname = f.get("type"), f["name"]
            if ftype in UNCONFIRMED or ftype not in ENCODINGS:
                errors.append(f"{gname}:{fname}: type '{ftype}' has no confirmed ObjectManager encoding yet; dump an existing "
                              f"field of that type and add it to ENCODINGS (field skipped)")
                continue
            data_type, display, extra, disp_props = ENCODINGS[ftype]
            values = [str(v) for v in f.get("values", []) or []]
            default = ""
            if "default" in f and f["default"] is not None:
                if ftype == "enum":
                    if str(f["default"]) not in values:
                        errors.append(f"{gname}:{fname}: default '{f['default']}' is not one of the values")
                    else:
                        default = str(values.index(str(f["default"])) + 1)   # enum default = value number (dump)
                elif ftype == "boolean":
                    default = b(f["default"])
                else:
                    default = str(f["default"])
            elif ftype == "boolean":
                default = "false"
            attrs = {
                "name": fname, "description": f.get("description", ""), "dataType": data_type,
                "minValue": "" if f.get("min") is None else str(f["min"]),
                "maxValue": "" if f.get("max") is None else str(f["max"]),
                "defaultValue": default, "required": b(f.get("required")), "encrypted": "false",
                "currencyCode": f.get("currency", "USD") if ftype == "currency" else "",
                "isDimension": "false", "isFact": "false", "multiValued": "false",
                "searchEnabled": b(f.get("search")), "includeConversion": "true", "suppliedByVendor": "false",
                "dataLength": "",
            }
            attrs.update(extra)
            if ftype == "long_string" and f.get("length"):
                attrs["dataLength"] = str(f["length"])
            pt = ET.SubElement(bt, "propertyType", {k: attrs[k] for k in PROP_ATTR_ORDER if k in attrs})
            if ftype == "enum":
                et = ET.SubElement(pt, "enumType", name=fname, description="")
                for i, v in enumerate(values, 1):
                    ET.SubElement(et, "enumValue", name=v, value=str(i), displayOrder=str(i),
                                  isCommentRequired="false", isAttachmentRequired="false", hidden="false")
            col = ref.column(gname, fname)
            if col is None:
                col = column_name(fname)
                if is_ext:
                    notes.append(f"{gname}:{fname}: reporting column '{col}' on existing type {owner} may collide "
                                 f"(the server renamed 'source' to 'source00' on Finding); check the validate output")
            ET.SubElement(pt, "rpsColumnDefinition", columnName=col, contentTypeName=owner)
            da = ET.SubElement(pt, "displayTypeAttributes")
            da.text = "{ }"
            dt = ET.SubElement(pt, "displayType", name=display)
            props = dict(disp_props)
            if ftype == "user_group" and f.get("starting_group"):
                props["startingGroup"] = f["starting_group"]
            for pn, pv in props.items():
                dtp = ET.SubElement(dt, "displayTypeProperty", name=pn)
                if pv is not None:
                    ET.SubElement(dtp, "displayTypePropertyValue", name=pv, **({"fullPath": ""} if pn == "startingGroup" else {}))
            # strings
            label = f.get("label", fname)
            strings.append(ET.Element("fieldString", name=fname, fieldGroup=gname, singularValue=label, pluralValue="",
                                      guidance=f.get("guidance", label), altValue="", suppliedByVendor="false",
                                      overriddenByUser="false"))
            for v in values:
                strings.append(ET.Element("enumValueString", name=v, field=fname, fieldGroup=gname, value=v,
                                          suppliedByVendor="false", overriddenByUser="false"))
            profile_rows.append((owner, gname, f, display))
    ET.SubElement(root, "systemAdminMode", enabled="false")

    # profiles: only the solution's groups/fields, merged (explicitListing="false")
    profs = spec.get("profiles", []) or []
    if profs:
        ops = ET.SubElement(root, "objectProfiles", explicitListing="false")
        for pname in profs:
            src = ref.profiles.get(pname)
            pattrs = {"name": pname}
            if src is not None:
                for k in ("description", "defaultSelection", "fallback", "enabled"):
                    if src.get(k) is not None:
                        pattrs[k] = src.get(k)
            else:
                notes.append(f"profile '{pname}' not in the reference dump: attributes other than name are omitted")
            op = ET.SubElement(ops, "objectProfile", pattrs)
            by_type: dict[str, dict[str, list]] = {}
            for owner, gname, f, display in profile_rows:
                by_type.setdefault(owner, {}).setdefault(gname, []).append((f, display))
            orders = {i.get("name"): i.get("displayOrder") for i in (src.findall("includedObjectType") if src is not None else [])}
            next_order = max([int(v) for v in orders.values() if str(v).isdigit()] or [0]) + 1
            for owner, groups in by_type.items():
                # displayOrder is required by the 9.2.1 validator ("includedObjectType ... displayOrder: Not provided!")
                order = orders.get(owner)
                if not order:
                    if src is None:
                        errors.append(f"profile '{pname}': displayOrder for {owner} unknown; pass --reference <dump>")
                        order = "1"
                    else:
                        order = str(next_order)
                        next_order += 1
                        notes.append(f"profile '{pname}': {owner} not in the profile yet; displayOrder {order} assigned")
                iot = ET.SubElement(op, "includedObjectType", name=owner, displayOrder=order)
                for gname, fields in groups.items():
                    ig = ET.SubElement(iot, "includedFieldGroup", name=gname)
                    for f, display in fields:
                        inf = ET.SubElement(ig, "includedField", name=f["name"],
                                            readOnly=b(f.get("read_only")), required=b(f.get("required")))
                        ET.SubElement(inf, "displayType", name=display)
    if strings:
        os_ = ET.SubElement(root, "objectStrings")
        ls = ET.SubElement(os_, "localeStrings", name="U.S. English")
        ls.extend(strings)
    return root, errors, notes


# ------------------------------------------------------------------ compare
def compare(spec: dict, gen: ET.Element, ref: Reference) -> list[tuple[str, str, str]]:
    """(severity, where, message). DIFF = spec and live disagree; MISSING = in spec, not live; EXTRA = live only."""
    out = []
    gen_ref = Reference(root=gen)
    owners = {}
    for owner, g, _ in groups_by_owner(spec):
        owners[g["name"]] = owner
        if g["name"] not in ref.bundles:
            out.append(("MISSING", g["name"], f"field group not in the dump (owner {owner})"))
        elif (g.get("description") or "") != (ref.bundles[g["name"]].get("description") or ""):
            out.append(("DIFF", g["name"], f"field group description: spec '{g.get('description') or ''}', "
                                           f"live '{ref.bundles[g['name']].get('description') or ''}'"))
    for (grp, fld), p in gen_ref.props.items():
        live = ref.props.get((grp, fld))
        where = f"{grp}:{fld}"
        if live is None:
            if grp in ref.bundles:
                out.append(("MISSING", where, "field not in the dump"))
            continue
        for a in COMPARE_ATTRS:
            sv, lv = p.get(a, ""), live.get(a, "")
            if sv != lv:
                out.append(("DIFF", where, f"{a}: spec gives '{sv}', live has '{lv}'"))
        gv = [(e.get("name"), e.get("value"), e.get("hidden")) for e in p.iter("enumValue")]
        lv_ = [(e.get("name"), e.get("value"), e.get("hidden")) for e in live.iter("enumValue")]
        if gv != lv_:
            out.append(("DIFF", where, f"enum values: spec {gv}, live {lv_}"))
        gd, ld = p.find("displayType"), live.find("displayType")
        if gd is not None and ld is not None and gd.get("name") != ld.get("name"):
            out.append(("DIFF", where, f"displayType: spec '{gd.get('name')}', live '{ld.get('name')}'"))
        gcol, lcol = p.find("rpsColumnDefinition"), live.find("rpsColumnDefinition")
        if gcol is not None and lcol is not None and gcol.get("columnName") != lcol.get("columnName"):
            out.append(("INFO", where, f"reporting column: generated '{gcol.get('columnName')}', live '{lcol.get('columnName')}' (server-assigned)"))
        gs, ls = gen_ref.strings.get(("field", grp, fld)), ref.strings.get(("field", grp, fld))
        if gs is not None and ls is not None and gs.get("singularValue") != ls.get("singularValue"):
            out.append(("DIFF", where, f"label: spec '{gs.get('singularValue')}', live '{ls.get('singularValue')}'"))
        for pname in spec.get("profiles", []) or []:
            pf = ref.profile_field(pname, owners.get(grp), grp, fld)
            if pf is None:
                out.append(("DIFF", where, f"not included in profile '{pname}' for {owners.get(grp)}"))
            elif pf.get("required") != p.get("required"):
                out.append(("DIFF", where, f"profile '{pname}' required={pf.get('required')}, field required={p.get('required')}"))
    for (grp, fld) in ref.props:
        if grp in owners and (grp, fld) not in gen_ref.props:
            out.append(("EXTRA", f"{grp}:{fld}", "field exists live but not in the spec"))
    return out


# ------------------------------------------------------------------ relationships
UNLIMITED = "2147483647"
UI_SET = "SOX Extended Object Model"   # 9.2.1: relationships added in the UI land here (dump 2026-10-23)


def spec_relationships(spec: dict) -> dict[tuple[str, str], dict]:
    """(parent, child) -> {max_parents, min_parents, source}. From object_types parents/children and top-level
    relationships (existing types)."""
    out: dict[tuple[str, str], dict] = {}

    def add(parent, child, src, **kw):
        cur = out.setdefault((parent, child), {"source": src})
        for k, v in kw.items():
            if v is not None:
                cur[k] = v

    for t in spec.get("object_types", []) or []:
        for p in t.get("parents", []) or []:
            pt = p["type"] if isinstance(p, dict) else p
            add(pt, t["name"], f"{t['name']}.parents", max_parents=(p.get("max_parents") if isinstance(p, dict) else None),
                min_parents=(p.get("min_parents") if isinstance(p, dict) else None))
        for ch in t.get("children", []) or []:
            add(t["name"], ch if isinstance(ch, str) else ch["type"], f"{t['name']}.children")
    for r in spec.get("relationships", []) or []:
        add(r["parent"], r["child"], "relationships", max_parents=r.get("max_parents"), min_parents=r.get("min_parents"))
    return out


class RelReference:
    def __init__(self, path: str | None = None, root: ET.Element | None = None):
        self.root = root if root is not None else (ET.parse(path).getroot() if path else None)
        self.sets: dict[str, ET.Element] = {}
        self.index: dict[tuple[str, str, str], tuple[str, ET.Element]] = {}   # (parent, child, type) -> (set, elem)
        if self.root is None:
            return
        for s in self.root.iter("contentTypeRelationshipSet"):
            self.sets[s.get("name")] = s
            for rel in s.findall("contentTypeRelationship"):
                self.index[(rel.get("parent"), rel.get("child"), rel.get("type"))] = (s.get("name"), rel)

    def find(self, parent, child, rtype="Association"):
        return self.index.get((parent, child, rtype))


def rel_attrs(parent, child, want: dict) -> dict:
    return {"parent": parent, "child": child, "type": "Association", "enabled": "true",
            "minParents": str(want.get("min_parents", 0)), "maxParents": str(want.get("max_parents", UNLIMITED)),
            "minChildren": "0", "maxChildren": UNLIMITED}


def build_relationships(spec: dict, rref: RelReference) -> tuple[ET.Element | None, list[str], list[str]]:
    """Whole UI set = every relationship already in it + the spec's (added/updated). Written in full so that a loader
    that REPLACES the set's members loses nothing; one that merges sees no change for the existing ones."""
    errors, notes = [], []
    if rref.root is None or UI_SET not in rref.sets:
        return None, [f"relationships need --relationships <dump> containing the '{UI_SET}' set "
                      "(ObjectManager dump with only content.type.relationship.sets=true, no filter file)"], []
    src_set = rref.sets[UI_SET]
    root = ET.Element("openpagesConfiguration", xmlFormatVersion=rref.root.get("xmlFormatVersion", "1.31"))
    ET.SubElement(root, "systemAdminMode", enabled="true")
    sets = ET.SubElement(root, "contentTypeRelationshipSets")
    out_set = ET.SubElement(sets, "contentTypeRelationshipSet", name=UI_SET, inheritsFrom=src_set.get("inheritsFrom", ""))
    members: dict[tuple, dict] = {}
    for rel in src_set.findall("contentTypeRelationship"):
        members[(rel.get("parent"), rel.get("child"), rel.get("type"))] = dict(rel.attrib)
    for (parent, child), want in spec_relationships(spec).items():
        hit = rref.find(parent, child)
        if hit and hit[0] != UI_SET:
            notes.append(f"{parent} -> {child}: provided by '{hit[0]}' (IBM set), not written")
            continue
        new = rel_attrs(parent, child, want)
        cur = members.get((parent, child, "Association"))
        if cur is None:
            notes.append(f"{parent} -> {child}: NEW relationship (from {want['source']})")
        else:
            for key, attr in (("max_parents", "maxParents"), ("min_parents", "minParents")):
                if key in want:
                    if cur.get(attr) != new[attr]:
                        notes.append(f"{parent} -> {child}: {attr} {cur.get(attr)} -> {new[attr]} (spec)")
                else:
                    new[attr] = cur.get(attr, new[attr])          # keep live values the spec does not set
            for attr in ("minChildren", "maxChildren"):
                new[attr] = cur.get(attr, new[attr])
            if cur.get("enabled") != "true":
                notes.append(f"{parent} -> {child}: re-enabled (spec lists it)")
        members[(parent, child, "Association")] = new
    order = ["parent", "child", "type", "enabled", "minParents", "maxParents", "minChildren", "maxChildren"]
    for a in members.values():
        ET.SubElement(out_set, "contentTypeRelationship", {k: a[k] for k in order if k in a})
    keep = [k for k in members if (k[0], k[1]) not in spec_relationships(spec)]
    if keep:
        notes.append(f"{len(keep)} relationship(s) already in '{UI_SET}' kept unchanged (not from this spec): "
                     + ", ".join(f"{p}->{c} ({t})" for p, c, t in keep))
    ET.SubElement(root, "systemAdminMode", enabled="false")
    return root, errors, notes


def compare_relationships(spec: dict, rref: RelReference) -> list[tuple[str, str, str]]:
    out = []
    for (parent, child), want in spec_relationships(spec).items():
        where = f"{parent} -> {child}"
        hit = rref.find(parent, child)
        if not hit:
            out.append(("MISSING", where, f"relationship not in the dump (spec: {want['source']})"))
            continue
        s, rel = hit
        if rel.get("enabled") != "true":
            out.append(("DIFF", where, f"disabled in '{s}'"))
        live_max = rel.get("maxParents")
        spec_max = str(want.get("max_parents", UNLIMITED))
        if live_max != spec_max:
            out.append(("DIFF", where, f"maxParents: spec gives {spec_max}"
                        + ("" if "max_parents" in want else " (not set = unlimited)") + f", live has {live_max}"))
        live_min, spec_min = rel.get("minParents"), str(want.get("min_parents", 0))
        if s == UI_SET and live_min != spec_min:
            out.append(("DIFF", where, f"minParents: spec gives {spec_min}, live has {live_min}"))
    return out


def indent(e: ET.Element, level=0):
    pad = "\n" + "  " * level
    if len(e):
        if not (e.text or "").strip():
            e.text = pad + "  "
        for c in e:
            indent(c, level + 1)
        if not (c.tail or "").strip():
            c.tail = pad
    if level and not (e.tail or "").strip():
        e.tail = pad


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("--reference", help="ObjectManager dump of the built solution (reuses server column names)")
    ap.add_argument("--compare", metavar="DUMP", help="only compare the spec with this dump and write the drift report")
    ap.add_argument("--relationships", metavar="DUMP", help="relationship-set dump: also generate (or, with --compare, "
                    "check) relationships -> <key>-relationships-op-config.xml")
    ap.add_argument("--out", help="output dir (default <project>/build/<KEY>/fields)")
    args = ap.parse_args(argv)

    spec = load_spec(args.spec)
    key = spec["solution"]["key"]
    ref = Reference(args.compare or args.reference)
    root, errors, notes = build(spec, ref)
    out_dir = Path(args.out) if args.out else Path(args.spec).resolve().parent.parent / "build" / key / "fields"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{key.lower()}-fields"

    lines = [f"# Field generation report: {spec['solution']['name']} ({key})", ""]
    if errors:
        lines += ["## Errors (fields skipped)", ""] + [f"- {e}" for e in errors] + [""]
    if notes:
        lines += ["## Notes", ""] + [f"- {n}" for n in notes] + [""]

    rc = 1 if errors else 0
    rref = RelReference(args.relationships) if args.relationships else None
    if args.compare:
        diffs = compare(spec, root, ref)
        if rref is not None:
            diffs += compare_relationships(spec, rref)
        real = [d for d in diffs if d[0] != "INFO"]
        lines += [f"## Spec vs. `{args.compare}`", "", f"**{len(real)} differences**, {len(diffs) - len(real)} info", "",
                  "| Kind | Where | Detail |", "|---|---|---|"] + [f"| {k} | `{w}` | {m} |" for k, w, m in diffs]
        report = out_dir / f"{stem}-compare.md"
        report.write_text("\n".join(lines) + "\n")
        print("\n".join(lines))
        print(f"-> {report}")
        return 1 if real or errors else 0

    indent(root)
    xml_path = out_dir / f"{stem}-op-config.xml"
    ET.ElementTree(root).write(xml_path, encoding="UTF-8", xml_declaration=True)
    n_fields = sum(1 for _ in root.iter("propertyType"))
    lines += ["## Output", "", f"- `{xml_path.name}`: {sum(1 for _ in root.iter('bundleType'))} field groups, {n_fields} fields, "
              f"profiles: {', '.join(spec.get('profiles', []) or ['none'])}",
              "", "## Load (human-run)", "",
              f"1. Review this report and the XML. 2. `ObjectManager.sh v c <user> <pw> <dir> {stem}` (validate).",
              f"3. `ObjectManager.sh l c <user> <pw> <dir> {stem}` in a maintenance window (SAM toggled by the file).",
              "4. `verify_spec.py <spec>` and `gen_fields.py <spec> --compare <new dump>` must both be clean.",
              "Never drop or re-create the reporting schema; no SQL/DDL."]
    if rref is not None:
        rroot, rerr, rnotes = build_relationships(spec, rref)
        lines += ["", "## Relationships", ""] + [f"- ERROR: {e}" for e in rerr] + [f"- {n}" for n in rnotes]
        if rroot is not None:
            indent(rroot)
            rel_path = out_dir / f"{key.lower()}-relationships-op-config.xml"
            ET.ElementTree(rroot).write(rel_path, encoding="UTF-8", xml_declaration=True)
            n_rel = sum(1 for _ in rroot.iter("contentTypeRelationship"))
            lines += [f"- `{rel_path.name}`: set '{UI_SET}' written in FULL ({n_rel} relationships: existing members kept, "
                      "spec relationships added/updated), so a loader that replaces set members loses nothing.",
                      f"- Load separately: `v c ... {key.lower()}-relationships`, then `l c`. Rollback = re-load the "
                      "relationship dump taken before (keep it)."]
            print(f"-> {rel_path}")
        rc = rc or (1 if rerr else 0)
    report = out_dir / f"{stem}-report.md"
    report.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"-> {xml_path}\n-> {report}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
