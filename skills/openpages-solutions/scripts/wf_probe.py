#!/usr/bin/env python3
"""
wf_probe.py - read-only diagnosis of a workflow on one object (no writes).

  ./op wf_probe.py <object id> [--type TPRRemediation]

Prints, in one report: the object's workflow-related keys and TPR/workflow fields, every id in
workflow_activity_ids with what GET /workflows/instances/{id} returns (body or empty = HTTP 204),
and the workflow definitions for the type (name, id, enabled/published state, activities).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from opclient import OPError, client_from_args, common_args  # noqa: E402


def short(v, n=1500):
    s = json.dumps(v, default=str)
    return s if len(s) <= n else s[:n] + " ...(truncated)"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("object_id")
    ap.add_argument("--type", help="object type for the definitions listing (default: from the object)")
    common_args(ap)
    a = ap.parse_args(argv)
    c = client_from_args(a)

    print(f"== object {a.object_id}")
    o = c.get_object(a.object_id, include_workflow=True)
    top = {k: v for k, v in o.items() if k != "fields"}
    print(short(top, 3000))
    otype = a.type or (o.get("type_definition_id") or "")
    print("\n== workflow-related fields")
    for f in o.get("fields", []):
        n = f.get("name", "")
        if ":" in n and (n.split(":")[0].startswith(("TPR", "OPSS-Wf", "OPLC")) or "Workflow" in n or "Status" in n):
            print(f"  {n} = {short(f.get('value'), 300)}")

    ids = [str(i) for i in (o.get("workflow_activity_ids") or [])]
    print(f"\n== workflow_activity_ids: {ids or 'NONE (no workflow on this object)'}")
    for i in ids:
        try:
            r = c.workflow_instance(i)
            print(f"  GET /workflows/instances/{i} -> " + ("EMPTY BODY (HTTP 204: no active instance visible to this user)" if r is None else short(r)))
        except OPError as e:
            print(f"  GET /workflows/instances/{i} -> ERROR {e.summary()}")

    print("\n== GET /workflows/instances/search (active activity instances)")
    try:
        first = c.get("/workflows/instances/search") or {}
        print(f"  first page paging = {short(first.get('paging'), 200) if isinstance(first, dict) else '?'}")
        acts = c.activity_instances()
        print(f"  all pages: {len(acts)} activity instances")
        by_type = {}
        for x in acts:
            t = ((x.get("grc_object") or {}).get("type_definition") or {}).get("name")
            by_type[t] = by_type.get(t, 0) + 1
        print(f"  by object type: {by_type}")
        mine = [x for x in acts if str((x.get("grc_object") or {}).get("id")) == str(a.object_id)]
        print(f"  for object {a.object_id}: " + (short(mine, 1500) if mine else "NONE"))
        tpr = [x for x in acts if ((x.get("grc_object") or {}).get("type_definition") or {}).get("name") == "TPRRemediation"]
        for x in tpr[:10]:
            print(f"  TPRRemediation activity {x.get('id')}: object {(x.get('grc_object') or {}).get('id')} status={x.get('status')} assignees={x.get('assignees')}")
    except OPError as e:
        print(f"  ERROR {e.summary()}")

    print(f"\n== workflow definitions for {otype or '(all)'}")
    try:
        defs = c.workflow_definitions(object_type=otype or None)
    except OPError as e:
        print(f"  ERROR {e.summary()}"); defs = []
    if not defs:
        print("  none returned")
    for d in defs:
        acts = [x.get("name") for x in (d.get("activities") or [])]
        keep = {k: d.get(k) for k in ("id", "name", "label", "object_type", "type", "enabled", "status", "state", "version", "published", "start_type") if k in d}
        print(f"  {short(keep, 600)}  activities={acts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
