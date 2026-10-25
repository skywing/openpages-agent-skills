"""
opclient.py - Minimal, dependency-free client for the IBM OpenPages GRC REST API V2 (9.2.x).

Design rules (governance):
  * Read-only by default. Every mutating call goes through _write(), which refuses unless
    the caller passed apply=True AND the target environment allows writes.
  * Environments tagged tier=prod NEVER accept writes from this tooling.
  * Every write is appended to an audit log (runs/audit.jsonl) with env, user, method, path.
  * Secrets come from environment variables named in config, never from the config file itself.

Config: config/environments.yaml (or .json), found by walking up from CWD, or via $OP_CONFIG.
Select env with --env / $OP_ENV (default: first entry).

Endpoints used (verified against the IBM OpenPages REST API V2 OpenAPI spec, 9.1 edition,
which states it "may also apply to subsequent releases"; re-verify on 9.2.1):
  GET  /v2/types                          GET  /v2/types/{id}?include_field_definitions=true
  GET  /v2/types/{id}/associations        GET/POST /v2/query
  GET/POST/PUT/DELETE /v2/contents[/{id}] POST /v2/contents/bulk (max 100)
  GET/POST/DELETE /v2/contents/{id}/associations
  GET  /v2/contents/template?type_id=     GET/PUT /v2/configuration/admin_mode
  GET  /v2/workflows/definitions          GET  /v2/workflows/instances/{id}
  GET  /v2/questionnaire/{id}/assessment  GET  /v2/questionnaire/{id}/template
  POST /v2/workflows/instances/{id}/transition/{action}
  POST /v2/workflows/definitions/{id}/start/{grc_object_id}
"""
from __future__ import annotations

import base64
import datetime as _dt
import getpass
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

API_PREFIX = "/opgrc/api/v2"


# --------------------------------------------------------------------------- config
def _load_structured(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise SystemExit("PyYAML is required for YAML files: pip install pyyaml") from e
        return yaml.safe_load(text)
    return json.loads(text)


def load_file(path: str | Path) -> Any:
    return _load_structured(Path(path))


def find_config() -> Path:
    if os.environ.get("OP_CONFIG"):
        return Path(os.environ["OP_CONFIG"])
    here = Path.cwd()
    for d in [here, *here.parents]:
        for name in ("environments.yaml", "environments.yml", "environments.json"):
            p = d / "config" / name
            if p.exists():
                return p
    raise SystemExit(
        "No config/environments.yaml found (walked up from CWD). "
        "Copy templates/environments.example.yaml to <project>/config/environments.yaml or set OP_CONFIG."
    )


def project_root() -> Path:
    return find_config().parent.parent


@dataclass
class EnvConfig:
    name: str
    base_url: str
    auth: str = "basic"  # basic | bearer | oauth
    tier: str = "dev"  # dev | test | uat | prod
    allow_writes: bool = False
    verify_tls: bool = True
    ca_file: str = ""  # PEM to trust (e.g. a dev container's self-signed cert); relative to project root
    username_env: str = "OP_USER"
    password_env: str = "OP_PASSWORD"
    token_env: str = "OP_TOKEN"
    client_id_env: str = "OP_CLIENT_ID"
    client_secret_env: str = "OP_CLIENT_SECRET"
    timeout: int = 60
    timezone: str = ""  # IANA zone the server shows dates in (e.g. America/New_York); "" = this machine's zone
    extra: dict = field(default_factory=dict)


def load_env(name: str | None = None) -> EnvConfig:
    raw = _load_structured(find_config())
    envs = raw.get("environments", raw)
    if not envs:
        raise SystemExit("environments config is empty")
    name = name or os.environ.get("OP_ENV") or next(iter(envs))
    if name not in envs:
        raise SystemExit(f"Unknown env '{name}'. Known: {', '.join(envs)}")
    e = dict(envs[name])
    known = set(EnvConfig.__dataclass_fields__) - {"name", "extra"}
    cfg = EnvConfig(name=name, **{k: v for k, v in e.items() if k in known})
    cfg.extra = {k: v for k, v in e.items() if k not in known}
    cfg.base_url = cfg.base_url.rstrip("/")
    if cfg.tier == "prod":
        cfg.allow_writes = False  # hard rule, cannot be overridden from config
    return cfg


# --------------------------------------------------------------------------- dates
# OpenPages stores DATE_TYPE values as instants (UTC). A bare "2026-12-31" sent as-is is taken as UTC midnight and
# shows as 2026-12-30 19:00 in New York. Send midnight in the zone the users see instead, as a UTC instant.
_BARE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _zone(tz_name: str):
    if tz_name:
        from zoneinfo import ZoneInfo  # stdlib, Python 3.9+
        return ZoneInfo(tz_name)
    return None  # None = this machine's local rules (DST-aware via naive .astimezone())


def to_api_date(value: Any, tz_name: str = "") -> Any:
    """'YYYY-MM-DD' (or a datetime.date from unquoted YAML) -> local midnight as 'YYYY-MM-DDTHH:MM:SS.000Z'.
    Anything else (already a timestamp, None) is returned unchanged."""
    if isinstance(value, _dt.datetime):
        return value
    if isinstance(value, _dt.date):
        d = value
    elif isinstance(value, str) and _BARE_DATE.match(value.strip()):
        d = _dt.date.fromisoformat(value.strip())
    else:
        return value
    tz = _zone(tz_name)
    midnight = _dt.datetime(d.year, d.month, d.day, tzinfo=tz) if tz else _dt.datetime(d.year, d.month, d.day).astimezone()
    return midnight.astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def from_api_date(value: Any, tz_name: str = "") -> Any:
    """A timestamp from the API -> 'YYYY-MM-DD' in the display zone (for comparing with spec dates)."""
    if not isinstance(value, str) or "T" not in value:
        return value
    try:
        t = _dt.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return value
    if t.tzinfo is None:
        t = t.replace(tzinfo=_dt.timezone.utc)
    tz = _zone(tz_name)
    return (t.astimezone(tz) if tz else t.astimezone()).date().isoformat()


# --------------------------------------------------------------------------- errors
class OPError(Exception):
    def __init__(self, status: int, method: str, path: str, body: Any):
        self.status, self.method, self.path, self.body = status, method, path, body
        super().__init__(self.summary())

    @property
    def codes(self) -> list[str]:
        if isinstance(self.body, dict):
            return [e.get("code", "") for e in self.body.get("errors", []) if isinstance(e, dict)]
        return []

    def summary(self) -> str:
        msgs = []
        if isinstance(self.body, dict) and self.body.get("errors"):
            for e in self.body["errors"]:
                msgs.append(f"{e.get('code','?')}: {e.get('message') or e.get('text') or ''} {e.get('data') or ''}".strip())
            trace = self.body.get("trace")
            if trace:
                msgs.append(f"trace={trace}")
        else:
            msgs.append(str(self.body)[:500])
        return f"HTTP {self.status} {self.method} {self.path} -> " + " | ".join(msgs)


class WriteRefused(Exception):
    pass


# --------------------------------------------------------------------------- client
class OpenPagesClient:
    def __init__(self, env: EnvConfig, apply: bool = False, audit_path: Path | None = None, verbose: bool = False):
        self.env = env
        self.apply = apply
        self.verbose = verbose
        self._token: str | None = None
        self._ctx = None
        if env.base_url.startswith("https"):
            if env.ca_file:
                ca = Path(env.ca_file)
                if not ca.is_absolute():
                    ca = project_root() / ca
                if not ca.exists():
                    raise SystemExit(f"ca_file not found: {ca}")
                self._ctx = ssl.create_default_context(cafile=str(ca))  # verified against the pinned cert
            elif not env.verify_tls:
                self._ctx = ssl._create_unverified_context()  # last resort for a local container
        self.audit_path = audit_path

    # ---- auth
    def _auth_header(self) -> str:
        a = self.env.auth
        if a == "basic":
            user = os.environ.get(self.env.username_env) or input(f"{self.env.username_env}: ")
            pw = os.environ.get(self.env.password_env) or getpass.getpass(f"{self.env.password_env}: ")
            os.environ[self.env.username_env], os.environ[self.env.password_env] = user, pw
            return "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()
        if a == "bearer":
            tok = os.environ.get(self.env.token_env)
            if not tok:
                raise SystemExit(f"Set ${self.env.token_env} for bearer auth")
            return "Bearer " + tok
        if a == "oauth":
            if not self._token:
                self._token = self._oauth_token()
            return "Bearer " + self._token
        raise SystemExit(f"Unsupported auth '{a}'")

    def _oauth_token(self) -> str:
        # Native OAuth 2.0 client-credentials (9.2.x): /oauth2/endpoint/OPOauthProvider/token
        cid = os.environ.get(self.env.client_id_env)
        sec = os.environ.get(self.env.client_secret_env)
        if not cid or not sec:
            raise SystemExit(f"Set ${self.env.client_id_env} and ${self.env.client_secret_env}")
        data = urllib.parse.urlencode({"client_id": cid, "client_secret": sec, "grant_type": "client_credentials"}).encode()
        req = urllib.request.Request(self.env.base_url + "/oauth2/endpoint/OPOauthProvider/token", data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(req, context=self._ctx, timeout=self.env.timeout) as r:
            return json.loads(r.read())["access_token"]

    # ---- transport
    def request(self, method: str, path: str, params: dict | None = None, body: Any = None, raw: bool = False) -> Any:
        url = self.env.base_url + API_PREFIX + path
        if params:
            url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None}, doseq=True)
        data = json.dumps(body).encode() if body is not None else None
        for attempt in range(4):
            req = urllib.request.Request(url, data=data, method=method)
            req.add_header("Accept", "application/json")
            req.add_header("Authorization", self._auth_header())
            if data is not None:
                req.add_header("Content-Type", "application/json")
            if self.verbose:
                print(f"> {method} {url}", file=sys.stderr)
            try:
                with urllib.request.urlopen(req, context=self._ctx, timeout=self.env.timeout) as r:
                    payload = r.read()
                    if raw:
                        return payload
                    return json.loads(payload) if payload else None
            except urllib.error.HTTPError as e:
                payload = e.read()
                try:
                    parsed = json.loads(payload)
                except Exception:
                    parsed = payload.decode(errors="replace")
                if e.code in (429, 502, 503, 504) and attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                raise OPError(e.code, method, path, parsed) from None
            except urllib.error.URLError as e:
                if attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                raise SystemExit(f"Cannot reach {self.env.base_url}: {e.reason}") from None

    def get(self, path: str, **params) -> Any:
        return self.request("GET", path, params=params or None)

    def _write(self, method: str, path: str, params: dict | None = None, body: Any = None) -> Any:
        if not self.env.allow_writes:
            raise WriteRefused(f"Env '{self.env.name}' (tier={self.env.tier}) does not allow writes.")
        if not self.apply:
            print(f"[dry-run] {method} {API_PREFIX}{path} params={params or {}}\n{json.dumps(body, indent=2)[:4000] if body is not None else ''}")
            return None
        result = self.request(method, path, params=params, body=body)
        self._audit(method, path, params, body, result)
        return result

    def _audit(self, method, path, params, body, result) -> None:
        p = self.audit_path or (project_root() / "runs" / "audit.jsonl")
        p.parent.mkdir(parents=True, exist_ok=True)
        rec = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "env": self.env.name,
            "tier": self.env.tier,
            "user": os.environ.get(self.env.username_env) or os.environ.get("USER"),
            "method": method,
            "path": path,
            "params": params,
            "request": body,
            "result_id": result.get("id") if isinstance(result, dict) else None,
        }
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str) + "\n")

    # ---- payload shaping
    def shape_fields(self, type_id: str, values: dict[str, Any]) -> list[dict]:
        """Build a REST `fields` list using the live type definition:
        ENUM_TYPE -> {'name': v}; MULTI_VALUE_ENUM / actor-like list fields -> [{'name': x}, ...].
        Raises ValueError for field names the type does not have (catches typos before the API does)."""
        cache = self.__dict__.setdefault("_typedefs", {})
        if type_id not in cache:
            cache[type_id] = {f["name"]: f for f in self.type_def(type_id, fields=True).get("field_definitions", [])}
        defs = cache[type_id]
        out = []
        for k, v in values.items():
            fdef = defs.get(k)
            if fdef is None:
                close = [n for n in defs if n.lower().split(":")[-1] == k.lower().split(":")[-1]]
                raise ValueError(f"Field '{k}' not on type {type_id}" + (f"; did you mean {close}?" if close else ""))
            dt = str(fdef.get("data_type", ""))
            if isinstance(v, list) and dt in ("STRING_TYPE", "MEDIUM_STRING_TYPE", "LARGE_STRING_TYPE"):
                # live 9.2.1: user/group owner fields are STRING_TYPE and take a plain string (a list gives
                # HTTP 400 "Cannot deserialize String from Array"); several users are comma-separated
                names = [str(x.get("name") if isinstance(x, dict) else x) for x in v]
                v = names[0] if len(names) == 1 else ", ".join(names)
            elif isinstance(v, list):
                v = [x if isinstance(x, dict) else {"name": x} for x in v]
            elif dt == "DATE_TYPE":
                v = to_api_date(v, self.env.timezone)
            elif dt == "ENUM_TYPE" and isinstance(v, str):
                v = {"name": v}
            elif dt == "MULTI_VALUE_ENUM" and isinstance(v, str):
                v = [{"name": v}]
            out.append({"name": k, "value": v})
        return out

    # ---- metadata (read)
    def types(self) -> list[dict]:
        return self.get("/types").get("types", [])

    def type_def(self, type_id: str, fields: bool = True) -> dict:
        return self.get(f"/types/{urllib.parse.quote(str(type_id))}", include_field_definitions=str(fields).lower())

    def type_associations(self, type_id: str, association_type: str | None = None) -> list[dict]:
        return self.get(f"/types/{urllib.parse.quote(str(type_id))}/associations", association_type=association_type).get("associations", [])

    def workflow_definitions(self, object_type: str | None = None, include_activities: bool = True) -> list[dict]:
        return self.get("/workflows/definitions", object_type=object_type, include_activities=str(include_activities).lower()).get("definitions", [])

    def questionnaire_assessment(self, qa_id: str) -> Any:
        """GET /v2/questionnaire/{id}/assessment - questionnaire assessment JSON (read-only)."""
        return self.get(f"/questionnaire/{qa_id}/assessment")

    def questionnaire_template(self, qa_id: str) -> Any:
        """GET /v2/questionnaire/{id}/template - template JSON for an assessment/template id (read-only)."""
        return self.get(f"/questionnaire/{qa_id}/template")

    def admin_mode(self) -> Any:
        return self.get("/configuration/admin_mode")

    # ---- query
    def query(self, statement: str, page_size: int = 200, max_rows: int = 0, case_insensitive: bool = False) -> Iterator[dict]:
        """Yields rows as {column_name: value}. Pages through results with offset/limit."""
        offset = 0
        while True:
            body = {"statement": statement, "offset": offset, "limit": page_size, "max_rows": max_rows, "case_insensitive": case_insensitive}
            res = self.request("POST", "/query", body=body) or {}
            rows = res.get("rows", [])
            for r in rows:
                yield {f.get("name"): f.get("value") for f in r.get("fields", [])}
            if len(rows) < page_size:
                return
            offset += page_size

    # ---- contents (read)
    def get_object(self, id_or_path: str, include_workflow: bool = False, include_associations: str | None = None, fields: str | None = None) -> dict:
        return self.get(
            f"/contents/{urllib.parse.quote(str(id_or_path), safe='/')}",
            include_workflow=str(include_workflow).lower() if include_workflow else None,
            include_associations=include_associations,
            field_filters=fields,
        )

    def associations(self, obj_id: str) -> list[dict]:
        return self.get(f"/contents/{obj_id}/associations").get("associations", [])

    def template(self, type_id: str) -> dict:
        return self.get("/contents/template", type_id=type_id)

    # ---- contents (write)
    def create_object(self, type_id: str, name: str, fields: list[dict] | None = None, primary_parent_id: str | None = None,
                      description: str | None = None, append_enum_vals: bool = False) -> dict | None:
        body: dict[str, Any] = {"type_definition_id": type_id, "name": name, "fields": fields or []}
        if primary_parent_id:
            body["primary_parent_id"] = str(primary_parent_id)
        if description:
            body["description"] = description
        return self._write("POST", "/contents", params={"append_enum_vals": "true"} if append_enum_vals else None, body=body)

    def update_object(self, obj_id: str, type_id: str, fields: list[dict], name: str | None = None) -> dict | None:
        body: dict[str, Any] = {"type_definition_id": type_id, "fields": fields}
        if name:
            body["name"] = name
        return self._write("PUT", f"/contents/{obj_id}", body=body)

    def associate(self, obj_id: str, other_ids: list[str], relation: str) -> Any:
        """relation: 'child' => other_ids become children of obj_id; 'parent' => parents."""
        assert relation in ("child", "parent")
        body = {"associations": [{"id": str(i), "type": relation} for i in other_ids]}
        return self._write("POST", f"/contents/{obj_id}/associations", body=body)

    def disassociate(self, obj_id: str, other_ids: list[str], relation: str) -> Any:
        """DELETE /contents/{id}/associations takes ?parents=1,2 / ?children=3,4 (no body)."""
        assert relation in ("child", "parent")
        key = "children" if relation == "child" else "parents"
        return self._write("DELETE", f"/contents/{obj_id}/associations", params={key: ",".join(map(str, other_ids))})

    def delete_object(self, obj_id: str) -> Any:
        """Soft delete (recoverable via GET /contents/deletedresources). This tool never purges."""
        return self._write("DELETE", f"/contents/{obj_id}")

    # ---- workflow (write)
    def activity_instances(self, **params) -> list[dict]:
        """GET /workflows/instances/search -> {"activity_instances": [{id, status (= stage label), assignees,
        grc_object: {id, name, path, type_definition}}, ...]}. Live 9.2.1: object_id/grc_object_id params are
        ignored, so callers filter on grc_object.id. The `id` here is the ACTIVITY instance id that
        GET/transition /workflows/instances/{id} expect (unlike content.workflow_activity_ids)."""
        # Paged: {"paging": {"total_count": N, "offset": 1, "limit": 50}}. The meaning of `offset` is unclear on 9.2.1
        # (stepping it skipped/duplicated rows), but `limit` is honoured, so read everything in ONE call:
        # ask for a large page, and if total_count is larger, ask again with limit=total_count.
        limit = int(params.pop("limit", 2000))
        res = self.get("/workflows/instances/search", limit=limit, **params) or {}
        out = res.get("activity_instances", []) if isinstance(res, dict) else []
        total = int(((res.get("paging") or {}) if isinstance(res, dict) else {}).get("total_count") or 0)
        if total > len(out):
            res = self.get("/workflows/instances/search", limit=total, **params) or {}
            out = res.get("activity_instances", []) if isinstance(res, dict) else []
            if len(out) < total:
                print(f"warning: activity search returned {len(out)} of {total} rows", file=sys.stderr)
        seen, uniq = set(), []
        for a in out:
            if a.get("id") not in seen:
                seen.add(a.get("id")); uniq.append(a)
        return uniq

    def workflow_instance(self, instance_id: str) -> dict:
        return self.get(f"/workflows/instances/{instance_id}")

    # Candidate ways to pass an action comment. 9.2.1 rejects a missing comment with OP-08557
    # "[Action Comment] is required"; the field name is not in IBM's public docs, so transition() tries these in
    # order (a rejected attempt changes nothing) and remembers the first one the server accepts.
    COMMENT_SHAPES = [
        # the UI's own response stores it as processContext.transitionComment.commentValue (seen live on 9.2.1)
        ("nested", "transitionComment.commentValue"), ("body", "commentValue"), ("body", "transitionComment"),
        ("nested", "transition_comment.comment_value"), ("body", "transition_comment"),
        ("body", "comment"), ("body", "comments"), ("body", "action_comment"), ("body", "actionComment"),
        ("query", "comment"), ("query", "comments"), ("query", "action_comment"),
        # the transition body may be a GRC-object payload: pass the comment as a field update
        ("fields", "Comment"), ("fields", "System Fields:Comment"), ("fields", "Action Comment"),
        ("fields", "System Workflow Fields:Action Comment"),
    ]

    def transition(self, instance_id: str, action_name: str, comment: str | None = None) -> Any:
        path = f"/workflows/instances/{instance_id}/transition/{urllib.parse.quote(action_name)}"
        if not comment:
            return self._write("POST", path)
        known = self.__dict__.get("_comment_shape")
        shapes = [known] if known else self.COMMENT_SHAPES
        last = None
        for where, key in shapes:
            try:
                if where == "body":
                    r = self._write("POST", path, body={key: comment})
                elif where == "nested":
                    outer, inner = key.split(".", 1)
                    r = self._write("POST", path, body={outer: {inner: comment}})
                elif where == "fields":
                    r = self._write("POST", path, body={"fields": [{"name": key, "value": comment}]})
                else:
                    r = self._write("POST", path, params={key: comment})
                self._comment_shape = (where, key)
                if self.apply:
                    # success does NOT prove the comment was stored: an action with an optional comment ignores unknown input
                    print(f"   (transition succeeded with the comment sent as {where} '{key}'; check the record's history to see if it was stored)", file=sys.stderr)
                return r
            except OPError as e:
                # OP-08571 "A comment must be provided when performing action X" = comment not recognised;
                # OP-08557 = a validation failed (kept for older workflow designs that validate the comment field)
                if not ({"-8571", "-8557"} & set(e.codes)) and "OP-08571" not in str(e.body) and "OP-08557" not in str(e.body):
                    if (where in ("fields", "nested") and e.status in (400, 500)) or (where == "body" and e.status == 400):
                        last = e; continue   # body shape not understood: try the next candidate
                    raise          # a different error: not a comment-shape problem
                last = e
        tried = ", ".join(f"{w}:{k}" for w, k in shapes)
        print(f"   action comment not accepted in any known form ({tried})", file=sys.stderr)
        raise last

    def start_workflow(self, definition_id: str, obj_id: str) -> Any:
        return self._write("POST", f"/workflows/definitions/{definition_id}/start/{obj_id}")


# --------------------------------------------------------------------------- helpers
def field_value(obj: dict, name: str) -> Any:
    for f in obj.get("fields", []):
        if f.get("name") == name:
            return f.get("value")
    return None


def to_field_payload(values: dict[str, Any]) -> list[dict]:
    """{'OPSS-Iss:Status': 'Open', 'X:Owner': ['jdoe']} -> REST field list.
    Enumerations accept a plain string (wrapped as {'name': v}); lists of strings for multi-select/actor fields."""
    out = []
    for k, v in values.items():
        if isinstance(v, list):
            v = [x if isinstance(x, dict) else {"name": x} for x in v]
        out.append({"name": k, "value": v})
    return out


def common_args(p) -> None:
    p.add_argument("--env", help="environment name from config/environments.yaml (default $OP_ENV or first)")
    p.add_argument("-v", "--verbose", action="store_true")


def write_args(p) -> None:
    p.add_argument("--apply", action="store_true", help="actually perform writes (default is dry-run)")


def client_from_args(args, apply: bool = False) -> OpenPagesClient:
    return OpenPagesClient(load_env(args.env), apply=apply, verbose=getattr(args, "verbose", False))
