#!/usr/bin/env python3
"""
cleanup.py - soft-delete the objects recorded in a test run manifest (reverse creation order).

  cleanup.py runs/test-local-0929153012.json            # dry-run
  cleanup.py runs/test-local-0929153012.json --apply

Refuses if the manifest's env differs from the selected env. Soft delete only (recoverable via
GET /v2/contents/deletedresources); this tooling never purges.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from opclient import OPError, client_from_args, common_args, write_args  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    common_args(ap); write_args(ap)
    ap.add_argument("manifest")
    args = ap.parse_args(argv)
    m = json.loads(Path(args.manifest).read_text())
    c = client_from_args(args, apply=args.apply)
    if m.get("env") != c.env.name:
        raise SystemExit(f"manifest is for env '{m.get('env')}', selected env is '{c.env.name}'")
    for o in reversed(m.get("created", [])):
        try:
            c.delete_object(o["id"])
            print(f"{'deleted' if args.apply else 'would delete'} {o['type']} {o['id']} {o.get('name','')}")
        except OPError as e:
            print(f"skip {o['id']}: {e.summary()}")


if __name__ == "__main__":
    main()
