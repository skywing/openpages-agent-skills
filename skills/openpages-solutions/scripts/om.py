#!/usr/bin/env python3
"""
om.py - run IBM ObjectManager (desktop client) against an environment from config/environments.yaml.

  ./om validate <dir> <prefix> [--env local]          check a loader file (read-only)
  ./om load     <dir> <prefix> [--env local] [--yes]  load a loader file (WRITE: needs allow_writes, never prod)
  ./om dump reference      [--env uat] [--filter F]   solution reference dump (filter file, types + field groups)
  ./om dump relationships  [--env uat]                every relationship set, nothing else (no filter)
  ./om dump custom         [--env uat]                types, field groups, strings, profiles, filters, views,
                                                      workflows, calculations, rules (input for reverse_spec.py)
  ./om dump filter --filter F [--env uat]             any dump narrowed by your own filter file
  options: --out DIR  --prefix NAME  --dry-run (show what would run, secrets masked)

Why a wrapper:
  * The real client folder is NEVER modified. Each run gets a temporary bin/ (copied from the client, with this run's
    openpages-tools-client.properties, ObjectManager.properties and filter file) next to a link to the client's lib/.
    ObjectManager's launcher derives its home from its own location, so it uses the overlay; a crash leaves nothing
    switched over.
  * Server address and login come from the environment entry: base_url -> rest.url.path = <base_url>/grc/api (the V1 path:
    with /opgrc/api/v2 the 9.2.1 client cannot parse the server's replies); verify_tls -> insecure.skip.tls.verify;
    auth basic -> OP_USER/OP_PASSWORD-style variables, auth oauth -> client id/secret + was_auth_server_url.
  * Java 21 (what the server ships) is selected per run (om_java_home, or macOS java_home -v 21); your default java
    is untouched.
  * Loads are refused on tier prod and when allow_writes is false, ask for confirmation unless --yes, and are logged
    to runs/audit.jsonl. Full output goes to runs/om-<env>-<command>-<time>.log.

Environment entry keys used (all optional): om_client_dir (default $OP_OM_CLIENT, then <project>/openpages-tools-client, then ~/aidev/openpages-tools-client),
om_rest_url, om_oauth_url, om_java_home, om_insecure_tls.
Windows: uses bin/ObjectManager.cmd (or .bat) from the client folder, copies lib/ when symlinks are not allowed, finds Java
21 from om_java_home, JAVA_HOME or the usual Program Files folders; run it through om.cmd (sets PYTHONUTF8=1).
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from opclient import load_env, project_root  # noqa: E402

DUMP_KINDS = {
    # kind: (options switched ON, every other configuration.manager.dump.<x>=true/false switched OFF?, needs filter)
    "reference": ({"jsp.based.content.types", "bundle.types"}, False, True),
    "relationships": ({"content.type.relationship.sets"}, True, False),
    "custom": ({"jsp.based.content.types", "form.based.content.types", "file.upload.content.types", "bundle.types",
                "object.strings", "object.profiles", "query.definitions", "responsive.views", "dashboard.views",
                "process.definitions", "tbcalculations", "tbrules"}, True, False),
    "filter": (set(), False, True),
}
DUMP_KEY = re.compile(r"^\s*(configuration\.manager\.dump\.[A-Za-z0-9.]+)\s*[=:]\s*(true|false)\s*$", re.I)
CLIENT_FILES = ["ObjectManager.sh", "ObjectManager.properties", "openpages-tools-client.properties"]
IS_WINDOWS = os.name == "nt"
# Windows: the client's own launcher (ObjectManager.cmd or .bat, placed in bin/ by the environment owner).
WINDOWS_LAUNCHERS = ("ObjectManager.cmd", "ObjectManager.bat")


def launcher_name(bin_dir: Path) -> str:
    """ObjectManager launcher for this OS: ObjectManager.sh, or on Windows the first of WINDOWS_LAUNCHERS present."""
    if IS_WINDOWS:
        for n in WINDOWS_LAUNCHERS:
            if (bin_dir / n).exists():
                return n
        return WINDOWS_LAUNCHERS[0]
    return "ObjectManager.sh"


# ------------------------------------------------------------------ properties helpers
def set_prop(text: str, key: str, value: str) -> str:
    """Replace `key = ...` (any of = : separators, any spacing) or append it. Values are written verbatim."""
    pat = re.compile(rf"^(\s*){re.escape(key)}\s*[=:].*$", re.M)
    line = f"{key} = {value}"
    if pat.search(text):
        return pat.sub(lambda m: m.group(1) + line, text, count=1)
    return text.rstrip("\n") + "\n" + line + "\n"


def get_prop(text: str, key: str) -> str | None:
    m = re.search(rf"^\s*{re.escape(key)}\s*[=:]\s*(.*?)\s*$", text, re.M)
    return m.group(1) if m else None


def dump_options(text: str, on: set[str], all_off: bool) -> str:
    """Set configuration.manager.dump.* booleans: listed ones true; with all_off every other boolean false."""
    out, seen = [], set()
    for ln in text.splitlines():
        m = DUMP_KEY.match(ln)
        if m:
            name = m.group(1)[len("configuration.manager.dump."):]
            seen.add(name)
            if name in on:
                ln = f"{m.group(1)}=true"
            elif all_off:
                ln = f"{m.group(1)}=false"
        out.append(ln)
    for name in sorted(on - seen):
        out.append(f"configuration.manager.dump.{name}=true")
    return "\n".join(out) + "\n"


# ------------------------------------------------------------------ setup
def client_dir(env) -> Path:
    d = env.extra.get("om_client_dir") or os.environ.get("OP_OM_CLIENT")
    if d:
        p = Path(os.path.expanduser(str(d)))
        if not p.is_absolute():
            p = project_root() / p
    else:                                          # default: inside the project (git-ignored), then beside it
        cands = [project_root() / "openpages-tools-client", Path.home() / "aidev" / "openpages-tools-client"]
        p = next((c for c in cands if (c / "bin" / launcher_name(c / "bin")).exists()), cands[0])
    if not (p / "bin" / launcher_name(p / "bin")).exists() or not (p / "lib").is_dir():
        raise SystemExit(f"ObjectManager client not found in {p} (needs bin/{launcher_name(p / 'bin')} and lib/). Set om_client_dir "
                         "in config/environments.yaml or $OP_OM_CLIENT (references/packaging.md: desktop client)")
    return p


def java_home(env) -> str:
    jh = env.extra.get("om_java_home")
    if jh:
        return os.path.expanduser(str(jh))
    if Path("/usr/libexec/java_home").exists():
        r = subprocess.run(["/usr/libexec/java_home", "-v", "21"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    if os.environ.get("JAVA_HOME"):
        return os.environ["JAVA_HOME"]
    if IS_WINDOWS:   # usual install folders of IBM Semeru / Temurin 21
        for pat in ("Semeru/jdk-21*", "IBM/Semeru*/jdk-21*", "Eclipse Adoptium/jdk-21*", "Java/jdk-21*"):
            hits = sorted(Path(os.environ.get("ProgramFiles", r"C:\Program Files")).glob(pat))
            if hits:
                return str(hits[-1])
    raise SystemExit("No Java 21 found: install IBM Semeru 21 or set om_java_home in config/environments.yaml")


def credentials(env, prompt: bool = True) -> tuple[str, str, str]:
    """(user-or-client-id, password-or-secret, kind)."""
    if env.auth == "oauth":
        names = (env.client_id_env, env.client_secret_env)
        kind = "oauth"
    elif env.auth == "basic":
        names = (env.username_env, env.password_env)
        kind = "basic"
    else:
        raise SystemExit(f"auth '{env.auth}' is not supported by ObjectManager on premises (use basic or oauth)")
    vals = []
    for n in names:
        v = os.environ.get(n)
        if not v:
            if not prompt:
                v = f"<{n}>"
            elif "SECRET" in n or "PASSWORD" in n:
                v = getpass.getpass(f"{n}: ")
            else:
                v = input(f"{n}: ")
        vals.append(v)
    return vals[0], vals[1], kind


def build_overlay(client: Path, env, kind: str, dump_kind: str | None, filter_file: Path | None) -> Path:
    """Temporary <tmp>/bin (this run's settings) + <tmp>/lib -> client lib. Returns <tmp>."""
    tmp = Path(tempfile.mkdtemp(prefix="om-"))
    (tmp / "bin").mkdir()
    for f in (client / "bin").iterdir():
        if f.is_file() and f.name != "ObjectManagerExportFilters.xml":
            shutil.copy2(f, tmp / "bin" / f.name)
    try:
        os.symlink(client / "lib", tmp / "lib", target_is_directory=True)
    except (OSError, NotImplementedError):   # Windows without symlink rights: copy (never a junction: rmtree risk)
        shutil.copytree(client / "lib", tmp / "lib")
    sh = tmp / "bin" / launcher_name(tmp / "bin")
    # never let a copied launcher pin the server's Java path (sh: JAVA_HOME=...; cmd/bat: set JAVA_HOME=...)
    if sh.suffix == ".sh":
        sh.write_text(re.sub(r"(?m)^JAVA_HOME=.*\n", "", sh.read_text()))
        sh.chmod(0o755)
    else:
        sh.write_text(re.sub(r'(?im)^\s*set\s+"?JAVA_HOME=.*\r?\n', "", sh.read_text()))
    base = env.base_url.rstrip("/")
    tp = tmp / "bin" / "openpages-tools-client.properties"
    t = tp.read_text() if tp.exists() else ""
    t = set_prop(t, "rest.url.path", env.extra.get("om_rest_url") or f"{base}/grc/api")
    insecure = env.extra.get("om_insecure_tls")
    if insecure is None:
        insecure = not env.verify_tls
    t = set_prop(t, "insecure.skip.tls.verify", "true" if insecure else "false")
    t = set_prop(t, "was_auth_server_url",
                 (env.extra.get("om_oauth_url") or f"{base}/oauth2/endpoint/OPOauthProvider") if kind == "oauth" else "")
    tp.write_text(t)
    if dump_kind:
        on, all_off, _ = DUMP_KINDS[dump_kind]
        op = tmp / "bin" / "ObjectManager.properties"
        op.write_text(dump_options(op.read_text() if op.exists() else "", on, all_off))
        if filter_file:
            shutil.copy2(filter_file, tmp / "bin" / "ObjectManagerExportFilters.xml")
    return tmp


def default_filter() -> Path | None:
    hits = sorted(project_root().glob("build/*/template/ObjectManagerExportFilters-*-reference.xml"))
    return hits[0] if len(hits) == 1 else None


def audit(env, cmd: str, target: str, rc: int, user: str):
    p = project_root() / "runs" / "audit.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "env": env.name, "tier": env.tier,
                            "user": user, "tool": "ObjectManager", "command": cmd, "target": target, "rc": rc}) + "\n")


# ------------------------------------------------------------------ main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["validate", "load", "dump"])
    ap.add_argument("args", nargs="*", help="validate/load: <dir> <prefix>; dump: <reference|relationships|custom|filter>")
    ap.add_argument("--env")
    ap.add_argument("--filter", help="filter file for dump reference/filter")
    ap.add_argument("--out", help="dump output dir (default build/_om/<env>/)")
    ap.add_argument("--prefix", help="dump prefix (default <env>-<kind>)")
    ap.add_argument("--yes", action="store_true", help="load without the interactive confirmation")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    env = load_env(a.env)
    root = project_root()

    dump_kind, filt = None, None
    if a.command in ("validate", "load"):
        if len(a.args) != 2:
            ap.error(f"{a.command} needs <dir> <prefix>")
        work = Path(a.args[0]).expanduser().resolve()
        prefix = a.args[1]
        if not (work / f"{prefix}-op-config.xml").exists():
            raise SystemExit(f"{work / (prefix + '-op-config.xml')} not found")
        om_cmd = "v" if a.command == "validate" else "l"
    else:
        if len(a.args) != 1 or a.args[0] not in DUMP_KINDS:
            ap.error(f"dump needs one of {sorted(DUMP_KINDS)}")
        dump_kind = a.args[0]
        if DUMP_KINDS[dump_kind][2]:
            filt = Path(a.filter).expanduser().resolve() if a.filter else default_filter()
            if not filt or not filt.exists():
                raise SystemExit(f"dump {dump_kind} needs --filter <ObjectManagerExportFilters file>")
        elif a.filter:
            raise SystemExit(f"dump {dump_kind} runs without a filter file (it lists everything of its kind)")
        work = Path(a.out).expanduser().resolve() if a.out else root / "build" / "_om" / env.name
        work.mkdir(parents=True, exist_ok=True)
        prefix = a.prefix or f"{env.name}-{dump_kind}"
        om_cmd = "d"

    if a.command == "load":
        if env.tier == "prod":
            raise SystemExit("REFUSED: loads are never run against tier prod from this tooling")
        if not env.allow_writes:
            raise SystemExit(f"REFUSED: env '{env.name}' has allow_writes: false")

    client = client_dir(env)
    jh = java_home(env)
    user, secret, kind = credentials(env, prompt=not a.dry_run)
    tmp = build_overlay(client, env, kind, dump_kind, filt)
    try:
        name = launcher_name(tmp / "bin")
        exe = str(tmp / "bin" / name) if IS_WINDOWS else f"./{name}"
        cmdline = [exe, om_cmd, "c", user, secret, str(work), prefix]
        shown = " ".join(cmdline[:4] + ["********"] + cmdline[5:])
        props = (tmp / "bin" / "openpages-tools-client.properties").read_text()
        print(f"env {env.name} ({env.tier}) | {kind} | rest.url.path = {get_prop(props, 'rest.url.path')} | "
              f"insecure.skip.tls.verify = {get_prop(props, 'insecure.skip.tls.verify')} | JAVA_HOME = {jh}")
        if dump_kind:
            on = sorted(DUMP_KINDS[dump_kind][0])
            print(f"dump {dump_kind}: options on {on or '(client defaults)'}"
                  + (", all other dump options off" if DUMP_KINDS[dump_kind][1] else "")
                  + (f", filter {filt}" if filt else ", no filter file"))
        print(f"$ {shown}   (in a temporary copy of {client}/bin)")
        if a.dry_run:
            return 0
        if a.command == "load" and not a.yes:
            ans = input(f"LOAD {prefix}-op-config.xml into '{env.name}' ({env.base_url})? Type the prefix to confirm: ")
            if ans.strip() != prefix:
                print("not confirmed; nothing loaded")
                return 1
        log = root / "runs" / f"om-{env.name}-{a.command}{'-' + dump_kind if dump_kind else ''}-{time.strftime('%Y%m%d-%H%M%S')}.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        status_error = False
        with log.open("w") as lf:
            p = subprocess.Popen(cmdline, cwd=tmp / "bin", env=dict(os.environ, JAVA_HOME=jh),
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for ln in p.stdout:
                sys.stdout.write(ln)
                lf.write(ln.replace(secret, "********") if secret else ln)
                if "STATUS_FINISHED_ERROR" in ln or "Completed with validation errors" in ln:
                    status_error = True
            p.stdout.close()
            rc = p.wait()
        if rc == 0 and status_error:
            rc = 2
        client_logs = tmp / "bin" / "logs"
        if client_logs.is_dir():                      # the overlay is deleted: keep the client's own log with ours
            with log.open("a") as lf:
                for f in sorted(client_logs.glob("*.log")):
                    lf.write(f"\n===== {f.name} =====\n")
                    lf.write(f.read_text(errors="replace").replace(secret, "********") if secret else f.read_text(errors="replace"))
        if a.command == "load":
            audit(env, "load", f"{work}/{prefix}-op-config.xml", rc, user if kind == "basic" else "oauth-client")
        out = work / f"{prefix}-op-config.xml"
        print(f"-> log {log}")
        if dump_kind and out.exists():
            print(f"-> {out} ({out.stat().st_size:,} bytes)")
        print("OK" if rc == 0 else f"FAILED (exit {rc}) - see the log")
        return rc
    finally:
        lib = tmp / "lib"
        if lib.is_symlink():          # remove the link itself first: never touch the client's real lib/
            try:
                os.unlink(lib)
            except OSError:
                os.rmdir(lib)         # Windows directory symlink
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
