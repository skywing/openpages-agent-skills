#!/usr/bin/env bash
# Read-only connectivity + schema check against the local OpenPages container.
# Usage (from ~/aidev/openpages):  bash first_check.sh
set -u
cd "$(dirname "$0")"
PY=.venv/bin/python
WANT="$(tr -d ' \n' < .python-version 2>/dev/null || echo 3.12)"
if [ ! -x "$PY" ] || [ "$($PY -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null)" != "$WANT" ]; then
  echo "Setting up .venv with Python $WANT"; bash setup_venv.sh || exit 1
fi
S=skills/openpages-solutions/scripts
mkdir -p runs
ENV_NAME="${OP_ENV:-local}"
$PY - "$ENV_NAME" <<'PYEOF' || exit 1
import sys, yaml
name = sys.argv[1]
e = (yaml.safe_load(open("config/environments.yaml")) or {}).get("environments", {}).get(name) or {}
if not e:
    print(f"environment '{name}' not found in config/environments.yaml"); sys.exit(1)
tls = "verify" if e.get("verify_tls", True) else "NO verification (dev only)"
if e.get("ca_file"):
    tls = f"verify against ca_file {e['ca_file']} (verify_tls ignored)"
print(f"env={name} url={e.get('base_url')} tier={e.get('tier')} tls: {tls}")
for k in ("username_env", "password_env"):
    v = str(e.get(k, ""))
    if not v.isidentifier() or not v.replace("_", "").isupper():
        print(f"WARNING: {k}='{v}' should be the NAME of an environment variable (e.g. OP_USER / OP_PASSWORD), not a value")
if e.get("ca_file") and not e.get("verify_tls", True):
    print("WARNING: ca_file is set, so TLS is still verified. Comment it out to run with verify_tls: false")
PYEOF
if [ -z "${OP_USER:-}" ]; then read -r -p "OpenPages user: " OP_USER; export OP_USER; fi
if [ -z "${OP_PASSWORD:-}" ]; then read -r -s -p "Password: " OP_PASSWORD; echo; export OP_PASSWORD; fi
run() { local name=$1; shift; echo "== $name"; "$@" > "runs/$name.txt" 2>&1; local rc=$?; tail -n 15 "runs/$name.txt"; echo "   (exit $rc, full output: runs/$name.txt)"; }
run 01-ping       $PY $S/op.py ping
run 02-types      $PY $S/op.py types
run 03-qtypes     $PY $S/op.py types --grep Questionnaire
run 04-wf-qa      $PY $S/op.py wf --type QuestionnaireAssessment
run 05-rels-issue $PY $S/op.py rels SOXIssue
run 06-dump       $PY $S/dump_schema.py --only SOXIssue,SOXTask,QuestionnaireAssessment,QuestionnaireTemplate,Program,Vendor
echo; echo "Done. Nothing was written to OpenPages. Tell Claude to read runs/ and schema/local/."
