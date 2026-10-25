#!/usr/bin/env python3
"""
dump_schema.py - snapshot the live object model of an OpenPages environment (read-only).

Writes to <project>/schema/<env>/:
  index.json            all object types (id, name, label, root folder)
  types/<Name>.json     full type definition incl. field definitions + association definitions
  workflows.json        all workflow definitions with stages (activities) and actions (transitions)
  SCHEMA.md             human/Claude-readable summary (fields, data types, required, enums, relationships)

  dump_schema.py                       # everything
  dump_schema.py --only ACME,SOXIssue  # comma list of name prefixes/names
  dump_schema.py --no-workflows

Commit schema/<env>/ to git: the diff between two dumps IS your configuration change log.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from opclient import OPError, client_from_args, common_args, project_root  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    common_args(ap)
    ap.add_argument("--only", help="comma-separated type names or prefixes")
    ap.add_argument("--no-workflows", action="store_true")
    ap.add_argument("--out", help="output dir (default <project>/schema/<env>)")
    args = ap.parse_args(argv)
    c = client_from_args(args)
    out = Path(args.out) if args.out else project_root() / "schema" / c.env.name
    (out / "types").mkdir(parents=True, exist_ok=True)

    types = sorted(c.types(), key=lambda t: t.get("name", ""))
    only = [s.strip() for s in args.only.split(",")] if args.only else None
    sel = [t for t in types if not only or any(t["name"] == o or t["name"].startswith(o) for o in only)]
    index = [{k: t.get(k) for k in ("id", "name", "localized_label", "localized_plural_label", "root_folder_path")} for t in types]
    (out / "index.json").write_text(json.dumps(index, indent=2))

    md = [f"# Object model snapshot: env `{c.env.name}` ({c.env.base_url})", "",
          f"{len(types)} object types in environment; {len(sel)} detailed below.", ""]
    for t in sel:
        name = t["name"]
        try:
            full = c.type_def(name, fields=True)
            full["associations"] = c.type_associations(name)
        except OPError as e:
            print(f"WARN {name}: {e.summary()}", file=sys.stderr)
            continue
        (out / "types" / f"{name}.json").write_text(json.dumps(full, indent=2, default=str))
        md += [f"## {full.get('localized_label')} (`{name}`, id {full.get('id')})", ""]
        parents = [a["name"] for a in full["associations"] if str(a.get("relationship", "")).lower() == "parent"]
        children = [a["name"] for a in full["associations"] if str(a.get("relationship", "")).lower() == "child"]
        md += [f"- Parents: {', '.join(parents) or '-'}", f"- Children: {', '.join(children) or '-'}", "",
               "| Field | Data type | Req | Computed | Enum values |", "|---|---|---|---|---|"]
        for f in full.get("field_definitions", []):
            enums = ", ".join((e.get("name") or e.get("localized_label") or "") for e in f.get("enum_values", []))
            md.append(f"| `{f.get('name')}` | {f.get('data_type')} | {'Y' if f.get('required') else ''} | {'Y' if f.get('computed') else ''} | {enums[:200]} |")
        md.append("")
        print(f"dumped {name}: {len(full.get('field_definitions', []))} fields, {len(full['associations'])} relationships")

    if not args.no_workflows:
        try:
            wfs = c.workflow_definitions()
            (out / "workflows.json").write_text(json.dumps(wfs, indent=2, default=str))
            md += ["# Workflows", ""]
            for d in wfs:
                if only and not any(str(d.get("type_definition_name", "")).startswith(o) for o in only):
                    continue
                md.append(f"## {d.get('name')} (id {d.get('id')}, v{d.get('version_number')}, {d.get('state')}) on `{d.get('type_definition_name')}`")
                for a in d.get("activities", []):
                    acts = "; ".join(f"{tr.get('name')} -> {tr.get('target')}" for tr in a.get("transitions", []))
                    md.append(f"- **{a.get('name')}** ({a.get('type')}): {acts or '-'}")
                md.append("")
            print(f"dumped {len(wfs)} workflow definitions")
        except OPError as e:
            print(f"WARN workflows: {e.summary()}", file=sys.stderr)

    (out / "SCHEMA.md").write_text("\n".join(md))
    print(f"-> {out}")


if __name__ == "__main__":
    main()
