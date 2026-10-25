#!/usr/bin/env python3
"""
api_probe.py - READ-ONLY probe: find the server's own REST API description and test candidate
workflow lookups for one object. Only GET requests; nothing is changed.

  ./op api_probe.py <object id>

Saves any API description it finds to runs/openapi-<env>.json so the client can be fixed from the
real contract instead of guesses.
"""
import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from opclient import client_from_args, common_args, project_root  # noqa: E402

DOC_PATHS = [
    "/opgrc/api/v2/openapi.json", "/opgrc/api/v2/openapi", "/opgrc/api/v2/swagger.json", "/opgrc/api/v2/api-docs",
    "/opgrc/api/v2/docs", "/opgrc/api/openapi.json", "/opgrc/api/swagger.json", "/opgrc/api/v2/openapi.yaml",
    "/opgrc/api/docs", "/openapi/ui", "/api/explorer", "/ibm/api/docs", "/ibm/api/explorer",
]


def raw_get(c, full_path):
    req = urllib.request.Request(c.env.base_url + full_path, method="GET")
    req.add_header("Accept", "application/json, */*")
    req.add_header("Authorization", c._auth_header())
    try:
        with urllib.request.urlopen(req, context=c._ctx, timeout=c.env.timeout) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", ""), e.read()
    except Exception as e:  # noqa: BLE001
        return None, "", str(e).encode()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("object_id")
    common_args(ap)
    a = ap.parse_args(argv)
    c = client_from_args(a)

    print("== API description endpoints")
    saved = None
    for p in DOC_PATHS:
        st, ct, body = raw_get(c, p)
        print(f"  {st}  {p}  {ct[:40]}  {len(body)} bytes")
        if st == 200 and body and saved is None and (b'"paths"' in body or b"openapi" in body[:200].lower() or b"swagger" in body[:200].lower()):
            out = project_root() / "runs" / f"openapi-{c.env.name}.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(body)
            saved = out
    print(f"  -> saved: {saved}" if saved else "  -> no machine-readable API description found at the usual paths")
    if saved:
        try:
            spec = json.loads(saved.read_text())
            print("\n== workflow paths in the API description")
            for path, ops in sorted((spec.get("paths") or {}).items()):
                if "workflow" in path.lower():
                    print(f"  {path}: {', '.join(m.upper() for m in ops)}")
        except Exception as e:  # noqa: BLE001
            print(f"  (could not parse as JSON: {e})")

    oid = a.object_id
    print(f"\n== candidate workflow lookups for object {oid}")
    o = c.get_object(oid, include_workflow=True)
    ids = o.get("workflow_activity_ids") or []
    print(f"  workflow_activity_ids = {ids}")
    cands = [f"/opgrc/api/v2/contents/{oid}/workflows", f"/opgrc/api/v2/contents/{oid}/workflow",
             f"/opgrc/api/v2/workflows/instances?object_id={oid}", f"/opgrc/api/v2/workflows/instances/search?object_id={oid}",
             f"/opgrc/api/v2/workflows/instances/search?grc_object_id={oid}", f"/opgrc/api/v2/workflows/objects/{oid}"]
    for i in ids:
        cands += [f"/opgrc/api/v2/workflows/instances/{i}", f"/opgrc/api/v2/workflows/instances/{i}/activities",
                  f"/opgrc/api/v2/workflows/activities/{i}"]
    for p in cands:
        st, ct, body = raw_get(c, p)
        txt = body.decode(errors="replace").replace("\n", " ")
        print(f"  {st}  {p}\n       {txt[:400]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
