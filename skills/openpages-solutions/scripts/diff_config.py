#!/usr/bin/env python3
"""
diff_config.py - semantic diff of two ObjectManager loader files (*-op-config.xml) or two
schema dump directories (schema/<env>/). Produces a change list suitable for a change ticket.

  diff_config.py build/TPR/export-v1/tpr-op-config.xml build/TPR/export-v2/tpr-op-config.xml
  diff_config.py schema/local schema/uat            # compare dev vs uat object models
  diff_config.py a.xml b.xml --md runs/diff.md

XML mode keys every element by its path of (tag, name) pairs, so reordering is ignored and
attribute changes are reported per element. It does not assume a specific XML schema version.
"""
import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

KEY_ATTRS = ("name", "systemName", "isoCode", "key", "id")


def key_of(el):
    for a in KEY_ATTRS:
        if a in el.attrib:
            return f"{el.tag}[{el.attrib[a]}]"
    return el.tag


def flatten_xml(path):
    root = ET.parse(path).getroot()
    out = {}

    def walk(el, prefix, sibling_counts):
        k = key_of(el)
        n = sibling_counts.get(k, 0)
        sibling_counts[k] = n + 1
        if n:
            k = f"{k}#{n}"
        p = f"{prefix}/{k}" if prefix else k
        text = (el.text or "").strip()
        out[p] = {**el.attrib, **({"#text": text} if text else {})}
        counts = {}
        for ch in el:
            walk(ch, p, counts)

    walk(root, "", {})
    return out


def flatten_dump(d):
    d = Path(d)
    out = {}
    for f in sorted((d / "types").glob("*.json")):
        t = json.loads(f.read_text())
        out[f"type[{t['name']}]"] = {"label": t.get("localized_label")}
        for fd in t.get("field_definitions", []):
            out[f"type[{t['name']}]/field[{fd['name']}]"] = {
                "data_type": fd.get("data_type"), "required": fd.get("required"), "computed": fd.get("computed"),
                "enum": ",".join(sorted((e.get("name") or "") for e in fd.get("enum_values", []))),
            }
        for a in t.get("associations", []):
            out[f"type[{t['name']}]/{str(a.get('relationship')).lower()}[{a.get('name')}]"] = {"enabled": a.get("is_enabled", a.get("enabled"))}
    wf = d / "workflows.json"
    if wf.exists():
        for w in json.loads(wf.read_text()):
            out[f"workflow[{w['name']}]"] = {"type": w.get("type_definition_name"), "state": w.get("state"), "version": w.get("version_number")}
            for a in w.get("activities", []):
                out[f"workflow[{w['name']}]/stage[{a.get('name')}]"] = {"type": a.get("type")}
                for t in a.get("transitions", []):
                    out[f"workflow[{w['name']}]/stage[{a.get('name')}]/action[{t.get('name')}]"] = {"target": t.get("target")}
    return out


def load(p):
    return flatten_dump(p) if Path(p).is_dir() else flatten_xml(p)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("old"); ap.add_argument("new"); ap.add_argument("--md")
    args = ap.parse_args(argv)
    a, b = load(args.old), load(args.new)
    added = sorted(set(b) - set(a))
    removed = sorted(set(a) - set(b))
    changed = []
    for k in sorted(set(a) & set(b)):
        if a[k] != b[k]:
            diffs = {x: (a[k].get(x), b[k].get(x)) for x in set(a[k]) | set(b[k]) if a[k].get(x) != b[k].get(x)}
            changed.append((k, diffs))
    L = [f"# Config diff", "", f"- old: `{args.old}`", f"- new: `{args.new}`", "",
         f"**{len(added)} added, {len(removed)} removed, {len(changed)} changed**", ""]
    if added:
        L += ["## Added", ""] + [f"- `{k}`" for k in added] + [""]
    if removed:
        L += ["## Removed", ""] + [f"- `{k}`" for k in removed] + [""]
    if changed:
        L += ["## Changed", ""]
        for k, d in changed:
            L.append(f"- `{k}`: " + "; ".join(f"{x}: {o!r} → {n!r}" for x, (o, n) in sorted(d.items())))
        L.append("")
    text = "\n".join(L)
    print(text)
    if args.md:
        Path(args.md).parent.mkdir(parents=True, exist_ok=True)
        Path(args.md).write_text(text)
    return 0 if not (added or removed or changed) else 3


if __name__ == "__main__":
    sys.exit(main())
