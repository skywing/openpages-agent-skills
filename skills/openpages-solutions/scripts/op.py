#!/usr/bin/env python3
"""
op.py - read-only OpenPages explorer (REST API V2).

  op.py ping                              # connectivity + auth + admin mode status
  op.py types [--grep TEXT]               # list object types (id, system name, label)
  op.py type SOXIssue [--fields]          # one type; --fields prints field definitions
  op.py rels SOXIssue                     # allowed parent/child relationships (association defs)
  op.py query "SELECT [Resource ID],[Name] FROM [SOXIssue]" [--max 100] [--json]
  op.py get 12345 [--workflow] [--assoc]  # one object (id or path)
  op.py wf [--type SOXIssue]              # workflow definitions: stages + actions
  op.py wfi 385                           # a workflow (activity) instance
  op.py template SOXIssue                 # empty create payload for a type
  op.py qa 12345 [--out f.json]           # questionnaire assessment JSON (answers, scores)
  op.py qt 12345 [--out f.json]           # questionnaire template JSON

Never writes. Use seed.py / wf_test.py / cleanup.py for mutations.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from opclient import OPError, client_from_args, common_args  # noqa: E402


def out(obj):
    print(json.dumps(obj, indent=2, default=str))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    common_args(ap)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ping")
    p = sub.add_parser("types"); p.add_argument("--grep")
    p = sub.add_parser("type"); p.add_argument("type_id"); p.add_argument("--fields", action="store_true"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("rels"); p.add_argument("type_id")
    p = sub.add_parser("query"); p.add_argument("statement"); p.add_argument("--max", type=int, default=100); p.add_argument("--json", action="store_true"); p.add_argument("-i", "--case-insensitive", action="store_true")
    p = sub.add_parser("get"); p.add_argument("id"); p.add_argument("--workflow", action="store_true"); p.add_argument("--assoc", action="store_true")
    p = sub.add_parser("wf"); p.add_argument("--type"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("wfi"); p.add_argument("instance_id")
    p = sub.add_parser("template"); p.add_argument("type_id")
    for name in ("qa", "qt"):
        p = sub.add_parser(name); p.add_argument("id"); p.add_argument("--out")
    args = ap.parse_args(argv)
    c = client_from_args(args)

    try:
        if args.cmd == "ping":
            t = c.types()
            print(f"OK  env={c.env.name} tier={c.env.tier} url={c.env.base_url} object_types={len(t)} writes={'allowed' if c.env.allow_writes else 'blocked'}")
            try:
                print(f"System Admin Mode: {c.admin_mode()}")
            except OPError as e:
                print(f"System Admin Mode: unavailable ({e.status})")
        elif args.cmd == "types":
            for t in sorted(c.types(), key=lambda x: x.get("name", "")):
                line = f"{t.get('id'):>6}  {t.get('name'):<32} {t.get('localized_label','')}"
                if not args.grep or args.grep.lower() in line.lower():
                    print(line)
        elif args.cmd == "type":
            t = c.type_def(args.type_id, fields=args.fields)
            if args.json:
                return out(t)
            print(f"{t['id']}  {t['name']}  label={t.get('localized_label')}  root={t.get('root_folder_path')}")
            for f in t.get("field_definitions", []) if args.fields else []:
                flags = "".join(k[0].upper() for k in ("required", "computed", "read_only") if f.get(k))
                enums = ", ".join(e.get("name") or e.get("localized_label") for e in f.get("enum_values", [])[:12])
                print(f"  {f.get('id'):>6} {f.get('name'):<48} {f.get('data_type'):<18} {flags:<3} {enums}")
        elif args.cmd == "rels":
            assocs = c.type_associations(args.type_id)
            if not assocs:
                print(f"(no relationships defined for {args.type_id}: expected for a type just loaded; add them in the UI under System Admin Mode)")
            for a in assocs:
                print(f"  {a.get('relationship'):<7} {a.get('name'):<32} min={a.get('min')} max={a.get('max')} enabled={a.get('is_enabled', a.get('enabled'))} assoc_def={a.get('association_definition_id')}")
        elif args.cmd == "query":
            rows = []
            for i, r in enumerate(c.query(args.statement, case_insensitive=args.case_insensitive)):
                if i >= args.max:
                    break
                rows.append(r)
            if args.json:
                return out(rows)
            if rows:
                cols = list(rows[0])
                print(" | ".join(cols))
                for r in rows:
                    print(" | ".join(str(r.get(k, "")) for k in cols))
            print(f"({len(rows)} rows{' - truncated' if len(rows) == args.max else ''})", file=sys.stderr)
        elif args.cmd == "get":
            out(c.get_object(args.id, include_workflow=args.workflow, include_associations="both" if args.assoc else None))
        elif args.cmd == "wf":
            defs = c.workflow_definitions(object_type=args.type)
            if args.json:
                return out(defs)
            for d in defs:
                print(f"{d.get('id')} v{d.get('version_number')} [{d.get('state')}{'' if d.get('is_enabled', True) else ', disabled'}] {d.get('name')}  type={d.get('type_definition_name')}")
                for a in d.get("activities", []):
                    print(f"   stage {a.get('name')!r} ({a.get('type')})")
                    for tr in a.get("transitions", []):
                        print(f"      action {tr.get('name')!r} -> {tr.get('target')!r}")
        elif args.cmd == "wfi":
            out(c.workflow_instance(args.instance_id))
        elif args.cmd == "template":
            out(c.template(args.type_id))
        elif args.cmd in ("qa", "qt"):
            data = c.questionnaire_assessment(args.id) if args.cmd == "qa" else c.questionnaire_template(args.id)
            if args.out:
                Path(args.out).write_text(json.dumps(data, indent=2, default=str))
                print(f"-> {args.out}")
            else:
                out(data)
    except OPError as e:
        print(e.summary(), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
