#!/usr/bin/env python3
"""
derive_type.py - derive a NEW object type loader file from an ObjectManager dump of a platform
object type (the template), for import with ObjectManager (v c / l c) or Import Configuration.

IBM provides no UI to create object types in 9.2.x. The supported route: dump an existing type,
derive a new <contentType>, validate, import. This script does the derivation schema-agnostically
(it does not assume a specific xmlFormatVersion) and writes a review report of every change.

  derive_type.py --dump build/TPR/template/soxissue-op-config.xml --baseline SOXIssue \
                 --spec specs/tpr.yaml --type TPRRemediation
  -> build/TPR/types/tprremediation-op-config.xml       (loader: pass prefix 'tprremediation')
  -> build/TPR/types/tprremediation-derive-report.md    (REVIEW BEFORE IMPORT)

What it does
  1. Finds the baseline <contentType name="SOXIssue"> (exactly one required).
  2. Clones it; renames system name, labels, plural labels, description, root folder path.
  3. Removes references to the baseline's own (non-system) field groups: the new type starts with
     system field groups only; the solution's field groups are added in the UI (or a later loader).
     Keep one with --keep-field-group NAME.
  4. Copies other elements that reference the baseline by name (e.g. object text strings), renamed.
     Relationship elements are NOT copied: add parent/child relationships in the UI
     (Object Types > Relationships > New Relationship), which is documented and reviewable.
  5. Sets allowOverride="true" on the new contentType (lets a corrected re-import update attributes).
  6. Flags any leftover mention of the baseline name/label and every numeric id-like attribute.

Never loads anything. Import is a separate, human-run step (see references/custom-object-type.md).
"""
import argparse
import copy
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

PLATFORM = {  # 9.2.x platform object types (Administrator's Guide > Object types > Platform object types)
    "SOXBusEntity": "Business Entity", "SOXIssue": "Issue", "SOXTask": "Issue Action Item",
    "SOXDocument": "File", "SOXExternalDocument": "Link", "SOXSignature": "Signature",
}
RECOMMENDED = {"SOXIssue", "SOXTask", "SOXDocument", "SOXExternalDocument"}
LABEL_ATTR = re.compile(r"label|singularValue", re.I)   # 9.2.1 objectTypeString uses singularValue / pluralValue
PLURAL_ATTR = re.compile(r"plural", re.I)
DESC_ATTR = re.compile(r"^description$", re.I)
FOLDER_ATTR = re.compile(r"folder|path|root", re.I)
ID_ATTR = re.compile(r"(^id$|Id$|_id$)")


def local(tag):
    return tag.split("}")[-1]


def parents(root):
    return {c: p for p in root.iter() for c in p}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dump", required=True, help="ObjectManager dump containing the baseline contentType")
    ap.add_argument("--baseline", required=True, help="baseline object type system name, e.g. SOXIssue")
    ap.add_argument("--type", required=True, help="new object type system name (must be in the spec)")
    ap.add_argument("--spec", help="solution spec (labels, description, key)")
    ap.add_argument("--label"); ap.add_argument("--plural"); ap.add_argument("--description")
    ap.add_argument("--root-folder", help="default /_op_sox/Project/Default/<Type>")
    ap.add_argument("--keep-field-group", action="append", default=[], help="baseline field group to keep (repeatable)")
    ap.add_argument("--out", help="output loader path (must end with -op-config.xml)")
    args = ap.parse_args(argv)

    t_spec = {}
    key = None
    if args.spec:
        from spec import load_file
        spec = load_file(args.spec)
        key = (spec.get("solution") or {}).get("key")
        t_spec = next((t for t in spec.get("object_types", []) if t["name"] == args.type), None)
        if t_spec is None:
            raise SystemExit(f"type {args.type} not found in spec {args.spec}")
    new = args.type
    label = args.label or t_spec.get("label") or new
    plural = args.plural or t_spec.get("plural_label") or label + "s"
    desc = args.description or t_spec.get("description") or label
    root_folder = args.root_folder or f"/_op_sox/Project/Default/{new}"
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", new):
        raise SystemExit("new type system name must be letters/digits, starting with a letter")

    notes, warns, changes = [], [], []
    if args.baseline not in PLATFORM:
        warns.append(f"Baseline `{args.baseline}` is not a platform object type; solution types drag in solution-specific field groups/relationships.")
    elif args.baseline not in RECOMMENDED:
        warns.append(f"Baseline `{args.baseline}` ({PLATFORM[args.baseline]}) is a special type; prefer SOXIssue or SOXTask.")
    base_label = PLATFORM.get(args.baseline)

    tree = ET.parse(args.dump)
    root = tree.getroot()
    pmap = parents(root)
    cts = [e for e in root.iter() if local(e.tag) == "contentType" and e.get("name") == args.baseline]
    if len(cts) != 1:
        raise SystemExit(f"expected exactly one <contentType name=\"{args.baseline}\"> in dump, found {len(cts)}")
    base = cts[0]
    if any(e.get("name") == new for e in root.iter() if local(e.tag) == "contentType"):
        raise SystemExit(f"{new} already present in dump")
    base_labels = {v for k, v in base.attrib.items() if LABEL_ATTR.search(k) and not PLURAL_ATTR.search(k)}
    base_plurals = {v for k, v in base.attrib.items() if PLURAL_ATTR.search(k)}
    if base_label:
        base_labels.add(base_label)
    base_folders = {v for k, v in base.attrib.items() if k == "rootFolder" and v.startswith("/")}   # NOT jspPath etc.

    bundle_names = {e.get("name") for e in root.iter() if local(e.tag) == "bundleType" and e.get("name")}
    drop_groups = {b for b in bundle_names if not b.lower().startswith("system") and b not in args.keep_field_group}

    def rewrite(el, where):
        for k, v in list(el.attrib.items()):
            nv = v
            if local(el.tag) == "objectTypeString" and k == "singularValue":
                nv = label
            elif local(el.tag) == "objectTypeString" and k == "pluralValue":
                nv = plural
            elif local(el.tag) == "objectTypeString" and k == "suppliedByVendor":
                nv = "false"
            elif v == args.baseline:
                nv = new
            elif PLURAL_ATTR.search(k) and (v in base_plurals or (base_label and v in (base_label + "s", base_label + "es"))):
                nv = plural
            elif LABEL_ATTR.search(k) and v in base_labels:
                nv = label
            elif DESC_ATTR.match(k):
                nv = desc
            elif v in base_folders:
                nv = root_folder
            elif args.baseline in v:
                nv = v.replace(args.baseline, new)
            if nv != v:
                el.set(k, nv)
                changes.append(f"{where}<{local(el.tag)}> @{k}: `{v}` → `{nv}`")
        if el.text and el.text.strip():
            t = el.text.strip()
            nt = t.replace(args.baseline, new)
            if t in base_labels:
                nt = label
            if nt != t:
                el.text = el.text.replace(t, nt)
                changes.append(f"{where}<{local(el.tag)}> text: `{t}` → `{nt}`")

    # 1-3. clone + rewrite the contentType
    ct = copy.deepcopy(base)
    cpar = parents(ct)
    for el in list(ct.iter()):
        refs = [v for v in el.attrib.values() if v in drop_groups] + ([el.text.strip()] if el.text and el.text.strip() in drop_groups else [])
        if refs and el is not ct:
            par = cpar.get(el)
            if par is not None:
                par.remove(el)
                notes.append(f"removed <{local(el.tag)}> referencing baseline field group `{refs[0]}`")
    for el in ct.iter():
        rewrite(el, "contentType ")
    ct.set("allowOverride", "true")
    changes.append("contentType @allowOverride → `true`")
    if ct.get("suppliedByVendor") == "true":
        ct.set("suppliedByVendor", "false")
        changes.append("contentType @suppliedByVendor: `true` → `false` (custom type; confirm ObjectManager validation accepts it)")

    # 4. other elements referencing the baseline by name (e.g. object strings), excluding relationships/field groups
    extras = []  # (wrapper_tag_path, element)
    skipped_rel = 0
    base_nodes = set(base.iter())
    base_anc = set(_ancestors(base, pmap))
    for el in root.iter():
        if el in base_nodes or el in base_anc:
            continue
        if local(el.tag) in ("bundleType", "propertyType"):
            continue
        if args.baseline not in el.attrib.values():
            continue
        if "relationship" in local(el.tag).lower() or any("relationship" in local(a.tag).lower() for a in [pmap.get(el)] if a is not None):
            skipped_rel += 1
            continue
        extras.append(el)
    # keep only outermost matches
    ext_set = set(extras)
    extras = [e for e in extras if not any(a in ext_set for a in _ancestors(e, pmap))]

    # build output doc mirroring wrapper structure
    out_root = ET.Element(root.tag, root.attrib)
    wrappers = {}

    def place(orig, new_el):
        chain = list(reversed(_ancestors(orig, pmap)))[1:]  # ancestors below root, top-down
        cur = out_root
        path = ()
        for a in chain:
            path += (local(a.tag), tuple(sorted(a.attrib.items())))
            if path not in wrappers:
                w = ET.SubElement(cur, a.tag, a.attrib)
                wrappers[path] = w
            cur = wrappers[path]
        cur.append(new_el)

    place(base, ct)
    for e in extras:
        c = copy.deepcopy(e)
        for sub in c.iter():
            rewrite(sub, f"<{local(e.tag)}> ")
        place(e, c)
        notes.append(f"copied <{local(e.tag)} name={e.get('name')!r}> (renamed)")
    if skipped_rel:
        notes.append(f"{skipped_rel} relationship element(s) for {args.baseline} NOT copied: add relationships in the UI")

    # the type's root folder resource (dump: <nonFormBasedResources><resource name=<rootFolder> .../>)
    folder_found = False
    for el in root.iter():
        if local(el.tag) == "resource" and el.get("name") in base_folders:
            c = copy.deepcopy(el)
            c.set("name", root_folder)
            if c.get("shortName"):
                c.set("shortName", root_folder.rsplit("/", 1)[-1])
            c.set("parentFolder", root_folder.rsplit("/", 1)[0])
            place(el, c)
            folder_found = True
            changes.append(f"<resource> root folder `{el.get('name')}` → `{root_folder}` (creator/dates kept from template)")
    if not folder_found:
        warns.append(f"no root folder <resource> for `{sorted(base_folders)}` in the dump: ObjectManager may need it; re-export including it")
    if not any(local(e.tag) == "objectTypeString" for e in extras):
        warns.append("dump has no <objectTypeString> for the baseline: label / plural label are NOT in the loader. "
                     "Re-export with <objectStrings><localeStrings name=\"U.S. English\"><objectTypeString name=\"%s\"/></localeStrings></objectStrings> "
                     "in ObjectManagerExportFilters.xml, or set the labels in the UI after import" % args.baseline)

    # keep the dump's own order and its System Admin Mode markers around the contentType
    sam = [e for e in root if local(e.tag) == "systemAdminMode"]
    rank = {"nonFormBasedResources": 0, "jspBasedContentTypes": 2, "formBasedContentTypes": 2, "dependencies": 4}
    out_root[:] = sorted(out_root, key=lambda e: rank.get(local(e.tag), 5))
    if sam:
        idx = next((i for i, e in enumerate(out_root) if local(e.tag) in ("jspBasedContentTypes", "formBasedContentTypes")), 0)
        out_root.insert(idx, ET.Element(sam[0].tag, {"enabled": "true"}))
        out_root.insert(idx + 2, ET.Element(sam[0].tag, {"enabled": "false"}))
        notes.append("kept the dump's System Admin Mode markers (true before the contentType, false after)")

    # 6. residual scan
    for el in out_root.iter():
        for k, v in el.attrib.items():
            if args.baseline in v or (base_label and v == base_label):
                warns.append(f"leftover reference in <{local(el.tag)}> @{k}=`{v}`")
            if ID_ATTR.search(k) and v.isdigit():
                warns.append(f"numeric id-like attribute <{local(el.tag)}> @{k}=`{v}`: environment-specific? confirm it is safe to import or remove it")

    out = Path(args.out) if args.out else Path("build") / (key or "types") / "types" / f"{new.lower()}-op-config.xml"
    if not out.name.endswith("-op-config.xml"):
        raise SystemExit("output file name must end with -op-config.xml (ObjectManager naming convention)")
    out.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(out_root)
    ET.ElementTree(out_root).write(out, encoding="UTF-8", xml_declaration=True)

    rep = out.with_name(out.name.replace("-op-config.xml", "-derive-report.md"))
    L = [f"# Derive report: `{new}` from `{args.baseline}`", "",
         f"- Source dump: `{args.dump}`", f"- Loader: `{out}` (ObjectManager prefix `{out.name[:-len('-op-config.xml')]}`)",
         f"- Label / plural: {label} / {plural}", f"- Root folder: `{root_folder}`",
         f"- Field groups dropped from template: {', '.join(sorted(drop_groups)) or 'none'}", "",
         "## Warnings (resolve before import)", ""] + ([f"- {w}" for w in warns] or ["- none"]) + [
         "", "## Changes", ""] + [f"- {c}" for c in changes] + ["", "## Notes", ""] + ([f"- {n}" for n in notes] or ["- none"]) + [
         "", "## Next steps", "",
         "1. Review this report and the XML diff against the template.",
         "2. Target env, SAM OFF (the loader toggles System Admin Mode itself): `ObjectManager.sh v c <user> <pw> <dir> <prefix>` (validate) → fix → `ObjectManager.sh l c ...` (load).",
         "   Do NOT drop or re-create the reporting schema.",
         "3. UI: add relationships, field groups/fields, profiles, views (see references/custom-object-type.md).",
         "4. `op.py type <Type> --fields`, `verify_spec.py <spec>`; Object Prefix Z<n> + Generate reporting framework if reported on."]
    rep.write_text("\n".join(L))
    print(f"-> {out}\n-> {rep}\n{len(changes)} changes, {len(warns)} warnings")
    return 1 if warns else 0


def _ancestors(el, pmap):
    out = []
    p = pmap.get(el)
    while p is not None:
        out.append(p)
        p = pmap.get(p)
    return out


if __name__ == "__main__":
    sys.exit(main())
