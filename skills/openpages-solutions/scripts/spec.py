"""
spec.py - load + validate a solution spec (templates/solution-spec.example.yaml) and shared helpers.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from opclient import load_file, project_root

FIELD_TYPES = {
    "boolean", "date", "integer", "decimal", "currency", "enum", "multi_enum",
    "simple_string", "medium_string", "long_string", "user_group", "business_entity",
}

# Spec type -> REST V2 `data_type` values.
#   CONFIRMED: seen in the IBM REST API V2 OpenAPI spec (STRING/MEDIUM_STRING/LARGE_STRING/ENUM/MULTI_VALUE_ENUM/DATE)
#   and/or observed live on a 9.2.1 server (BOOLEAN_TYPE, INTEGER_TYPE, FLOAT_TYPE, ID_TYPE).
#   CANDIDATES: plausible names not yet confirmed; verify_spec reports a WARN (not an error) when the live value
#   differs, and tells you to pin the real value in config/type_map.yaml after running dump_schema.py.
CONFIRMED = {
    "simple_string": {"STRING_TYPE"},
    "medium_string": {"MEDIUM_STRING_TYPE"},
    "long_string": {"MEDIUM_STRING_TYPE", "LARGE_STRING_TYPE"},   # UI "Long String" came back as MEDIUM_STRING_TYPE on 9.2.1
    "enum": {"ENUM_TYPE"},
    "multi_enum": {"MULTI_VALUE_ENUM"},
    "date": {"DATE_TYPE"},
    "boolean": {"BOOLEAN_TYPE"},      # observed live, 9.2.1
    "integer": {"INTEGER_TYPE"},      # observed live, 9.2.1
    "decimal": {"FLOAT_TYPE"},        # observed live, 9.2.1
    "currency": {"CURRENCY_TYPE"},    # observed live on a TPRRemediation field, 9.2.1
    "user_group": {"STRING_TYPE"},    # observed live: owner fields (e.g. OPLC-Owners:PrimaryOwner) are STRING_TYPE
}
CANDIDATES = {
    "user_group_multi": {"MULTI_VALUE_ACTOR"},
    "business_entity": {"ENTITY_TYPE", "BUSINESS_ENTITY_TYPE", "ID_TYPE"},
}

NAME_RE_TYPE = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")
NAME_RE_FIELD = re.compile(r"^[A-Za-z][A-Za-z0-9 _-]*$")
FASTMAP_RESERVED_LABELS = {"Delete", "Parent Path", "Parent Object Types", "Parent Objects", "Folder Path", "Tags"}


def type_map() -> dict[str, set[str]]:
    m = {k: set(v) for k, v in CONFIRMED.items()}
    try:
        p = project_root() / "config" / "type_map.yaml"
        if p.exists():
            for k, v in (load_file(p) or {}).items():
                m[k] = set(v if isinstance(v, list) else [v])
    except SystemExit:
        pass
    return m


def load_spec(path: str | Path) -> dict:
    spec = load_file(path)
    errors = lint_spec(spec)
    if errors:
        raise SystemExit("Spec lint failed:\n  - " + "\n  - ".join(errors))
    return spec


def lint_spec(spec: dict) -> list[str]:
    errs: list[str] = []
    key = (spec.get("solution") or {}).get("key")
    seen_types = set()
    for t in spec.get("object_types", []):
        n = t.get("name", "")
        if not NAME_RE_TYPE.match(n):
            errs.append(f"object type '{n}': system name must be letters/digits, starting with a letter")
        existing = bool((spec.get("solution") or {}).get("existing"))   # brownfield spec from reverse_spec.py
        if key and not n.startswith(key) and not existing:
            errs.append(f"object type '{n}': should start with solution key '{key}'")
        if n in seen_types:
            errs.append(f"duplicate object type '{n}'")
        seen_types.add(n)
        tpl = t.get("template")
        if tpl == "existing" and not existing:
            errs.append(f"object type '{n}': template 'existing' needs solution.existing: true")
        elif tpl and tpl != "existing" and tpl not in ("SOXIssue", "SOXTask", "SOXDocument", "SOXExternalDocument"):
            errs.append(f"object type '{n}': template '{tpl}' not allowed (use SOXIssue, SOXTask, SOXDocument or SOXExternalDocument)")
        if not t.get("parents"):
            errs.append(f"object type '{n}': no parents declared (most types need a primary parent)")
        prim = [p for p in t.get("parents", []) if isinstance(p, dict) and p.get("primary")]
        if len(prim) > 1:
            errs.append(f"object type '{n}': more than one primary parent")
        for g in t.get("field_groups", []):
            gn = g.get("name", "")
            if not NAME_RE_FIELD.match(gn):
                errs.append(f"field group '{gn}': invalid name")
            for f in g.get("fields", []):
                fn = f.get("name", "")
                if not NAME_RE_FIELD.match(fn):
                    errs.append(f"field '{gn}:{fn}': invalid name")
                if f.get("type") not in FIELD_TYPES:
                    errs.append(f"field '{gn}:{fn}': unknown type '{f.get('type')}' (use one of {sorted(FIELD_TYPES)})")
                if f.get("type") in ("enum", "multi_enum") and not f.get("values"):
                    errs.append(f"field '{gn}:{fn}': enum without values")
                if f.get("label", fn) in FASTMAP_RESERVED_LABELS:
                    errs.append(f"field '{gn}:{fn}': label '{f.get('label', fn)}' breaks FastMap import/export")
    all_types = seen_types | BUILTIN_TYPES | {p["type"] if isinstance(p, dict) else p for t in spec.get("object_types", []) for p in t.get("parents", [])}
    errs += lint_relationships(spec)
    errs += lint_extensions(spec, seen_types)
    errs += lint_questionnaires(spec, seen_types)
    errs += lint_calculations(spec, seen_types)
    for w in spec.get("workflows", []):
        if w.get("object_type") not in all_types:
            errs.append(f"workflow '{w.get('name')}': object_type '{w.get('object_type')}' not in spec")
        stages = {s["name"] for s in w.get("stages", [])}
        for s in w.get("stages", []):
            for a in s.get("actions", []):
                if a.get("to") not in stages:
                    errs.append(f"workflow '{w.get('name')}': action '{a.get('name')}' targets unknown stage '{a.get('to')}'")
        if not any(s.get("type") == "start" for s in w.get("stages", [])):
            errs.append(f"workflow '{w.get('name')}': no start stage")
        if not any(s.get("type") == "end" for s in w.get("stages", [])):
            errs.append(f"workflow '{w.get('name')}': no end stage")
    return errs


def lint_relationships(spec: dict) -> list[str]:
    """Top-level `relationships:` = links between EXISTING (non-spec) types the solution needs, e.g. Vendor -> Finding
    so a questionnaire response action can create a Finding under a Vendor. Added in the UI (Object Types > <child> >
    Relationships > New Relationship, SAM on); not part of the object_types parents/children."""
    errs, seen = [], set()
    for r in spec.get("relationships", []) or []:
        p, c = r.get("parent"), r.get("child")
        if not p or not c:
            errs.append(f"relationship {r}: parent and child are required")
            continue
        if p == c:
            errs.append(f"relationship {p} -> {c}: a type cannot be its own parent")
        if (p, c) in seen:
            errs.append(f"relationship {p} -> {c}: duplicate")
        if (c, p) in seen:
            errs.append(f"relationship {p} -> {c}: circular with {c} -> {p} (9.2.x rejects circular relationships)")
        seen.add((p, c))
        if not r.get("reason"):
            errs.append(f"relationship {p} -> {c}: add a reason (it changes a shared, non-solution type)")
    return errs


def lint_extensions(spec: dict, spec_types: set) -> list[str]:
    """`type_extensions:` = field groups the solution adds to EXISTING types (e.g. TPR-Fnd on Finding).
    `workflow_changes:` = edits to existing workflows (e.g. Applicability on Sys-Workflow-Finding)."""
    errs = []
    for e in spec.get("type_extensions", []) or []:
        tn = e.get("type", "")
        if not tn:
            errs.append(f"type_extensions entry {e}: type is required")
            continue
        if tn in spec_types:
            errs.append(f"type_extensions {tn}: is a spec object type; put the field groups under object_types")
        if not e.get("reason"):
            errs.append(f"type_extensions {tn}: add a reason (it changes a shared, non-solution type)")
        key = (spec.get("solution") or {}).get("key")
        for g in e.get("field_groups", []):
            gn = g.get("name", "")
            if not NAME_RE_FIELD.match(gn):
                errs.append(f"type_extensions {tn}: field group '{gn}': invalid name")
            if key and not gn.startswith(key) and not (spec.get("solution") or {}).get("existing"):
                errs.append(f"type_extensions {tn}: field group '{gn}' should start with solution key '{key}' (keeps it apart from IBM groups)")
            for f in g.get("fields", []):
                fn = f.get("name", "")
                if f.get("type") not in FIELD_TYPES:
                    errs.append(f"field '{gn}:{fn}': unknown type '{f.get('type')}'")
                if f.get("type") in ("enum", "multi_enum") and not f.get("values"):
                    errs.append(f"field '{gn}:{fn}': enum without values")
                if f.get("required"):
                    errs.append(f"field '{gn}:{fn}': do not make an added field required on a shared type (breaks existing creation paths)")
    for w in spec.get("workflow_changes", []) or []:
        if not w.get("workflow") or not w.get("change"):
            errs.append(f"workflow_changes entry {w}: workflow and change are required")
        if not w.get("reason"):
            errs.append(f"workflow_changes {w.get('workflow')}: add a reason")
    return errs


def extra_parents(spec: dict, child: str) -> set:
    return {r.get("parent") for r in spec.get("relationships", []) or [] if r.get("child") == child}


QUESTIONNAIRE_TYPES = {"QuestionnaireTemplate", "SectionTemplate", "SubSectionTemplate", "QuestionTemplate", "Program", "QuestionnaireAssessment"}
ASSET_TYPES = {"Resource", "SOXProcess", "SOXSubprocess", "Vendor", "Engagement", "Employee"}
BUILTIN_TYPES = QUESTIONNAIRE_TYPES | ASSET_TYPES | {"SOXBusEntity", "SOXIssue", "SOXTask", "SOXDocument", "SOXExternalDocument", "SOXSignature"}
Q_TYPES = {"single", "multiple", "short_text", "long_text", "table", "email", "url", "user_group", "user", "group", "date",
           "decimal", "integer", "object_selector"}   # User Guide 9.2.x ch.9 p.108-109
LIFECYCLES = {"2 Stage Lifecycle (no review)", "3 Stage Lifecycle (with review)", "4 Stage Lifecycle (with review and approval)"}


def lint_questionnaires(spec: dict, custom_types: set) -> list[str]:
    """IBM 9.2.x limits and rules: 1000 q/template, 199 items/section, 50 q/subsection, dependency depth <= 6,
    controlling questions single/multiple only, no cycles, scores -1..9999, weights 0..9999, table <= 15 columns."""
    errs: list[str] = []
    ct = {t["name"]: t for t in spec.get("object_types", [])}
    for qn in spec.get("questionnaires", []):
        n = qn.get("name", "?")
        E = lambda m: errs.append(f"questionnaire '{n}': {m}")
        if qn.get("scoring", "simple") not in ("simple", "weighted_average"):
            E("scoring must be simple or weighted_average")
        if qn.get("lifecycle") not in LIFECYCLES:
            E(f"lifecycle must be one of {sorted(LIFECYCLES)}")
        for a in qn.get("asset_types", []):
            if a not in ASSET_TYPES:
                E(f"asset type '{a}' not a questionnaire asset type {sorted(ASSET_TYPES)}")
        if not qn.get("asset_types"):
            E("no asset_types")
        qmap, where, total = {}, {}, 0
        for si, s in enumerate(qn.get("sections", [])):
            sec_items = 0
            for ssi, ss in enumerate(s.get("subsections", [])):
                qs = ss.get("questions", [])
                sec_items += 1 + len(qs)
                total += len(qs)
                if len(qs) > 50:
                    E(f"subsection '{ss.get('title')}' has {len(qs)} questions (max 50)")
                if not (0 <= ss.get("weight", 1) <= 9999):
                    E(f"subsection '{ss.get('title')}' weight out of 0..9999")
                for q in qs:
                    qid = q.get("id")
                    if not qid or qid in qmap:
                        E(f"missing or duplicate question id '{qid}'")
                        continue
                    qmap[qid] = q
                    where[qid] = (si, ssi)
                    if q.get("type") not in Q_TYPES:
                        E(f"{qid}: type '{q.get('type')}' not in {sorted(Q_TYPES)}")
                    if not (0 <= q.get("weight", 1) <= 9999):
                        E(f"{qid}: weight out of 0..9999")
                    if len(q.get("text", "")) > 2048:
                        E(f"{qid}: question text > 2048 chars")
                    if q.get("type") in ("single", "multiple"):
                        ans = q.get("answers") or []
                        if len(ans) < 2:
                            E(f"{qid}: choice question needs >= 2 answers")
                        texts = [a.get("text") for a in ans]
                        if len(set(texts)) != len(texts):
                            E(f"{qid}: duplicate answer texts")
                        for a in ans:
                            if not (-1 <= a.get("score", 0) <= 9999):
                                E(f"{qid}: answer '{a.get('text')}' score out of -1..9999")
                            if a.get("exclusive") and q["type"] != "multiple":
                                E(f"{qid}: 'exclusive' only applies to multiple choice")
                    elif q.get("answers"):
                        E(f"{qid}: answers only allowed on single/multiple choice")
                    if q.get("type") == "table" and len(q.get("columns", [])) > 15:
                        E(f"{qid}: table has more than 15 columns")
            if sec_items > 199:
                E(f"section '{s.get('title')}' has {sec_items} subsections+questions (max 199)")
            if not (0 <= s.get("weight", 1) <= 9999):
                E(f"section '{s.get('title')}' weight out of 0..9999")
        if total > 1000:
            E(f"{total} questions (max 1000)")

        def check_conds(label, conds):
            for c in conds:
                if "question" in c:
                    cq = qmap.get(c["question"])
                    if not cq:
                        E(f"{label}: unknown controlling question '{c['question']}'")
                    elif cq.get("type") not in ("single", "multiple"):
                        E(f"{label}: controlling question '{c['question']}' must be single/multiple choice")
                    else:
                        bad = set(c.get("in", [])) - {a.get("text") for a in cq.get("answers", [])}
                        if bad or not c.get("in"):
                            E(f"{label}: condition values {sorted(bad) or '[]'} not answers of '{c['question']}'")
                elif "field" not in c:
                    E(f"{label}: condition needs 'question' or 'field'")

        deps = {}
        for qid, q in qmap.items():
            sw = q.get("show_when")
            if sw:
                check_conds(qid, sw.get("conditions", []))
                deps[qid] = [c["question"] for c in sw.get("conditions", []) if c.get("question") in qmap]
        def depth(q, seen=()):
            if q in seen:
                return None
            ds = [depth(p, seen + (q,)) for p in deps.get(q, [])]
            if any(d is None for d in ds):
                return None
            return 1 + max(ds, default=0)
        for qid in deps:
            d = depth(qid)
            if d is None:
                E(f"{qid}: circular question dependency")
            elif d > 6:
                E(f"{qid}: dependency depth {d} levels (max 6)")
        for ra in qn.get("response_actions", []):
            lab = f"response action '{ra.get('name')}'"
            check_conds(lab, (ra.get("when") or {}).get("conditions", []))
            op = ra.get("operation")
            if op not in ("set_fields", "create_object", "copy_object"):
                E(f"{lab}: operation must be set_fields, create_object or copy_object")
            if op in ("create_object", "copy_object"):
                child = ra.get("child_type")
                if not child:
                    E(f"{lab}: child_type required")
                elif child in ("SOXDocument", "SOXExternalDocument") and op == "create_object":
                    E(f"{lab}: cannot create File/Link objects")
                elif child in ct and not (set(parent_types(ct[child])) | extra_parents(spec, child)) & set(qn.get("asset_types", [])):
                    E(f"{lab}: {child} must have an asset type ({', '.join(qn.get('asset_types', []))}) as parent")
                if "${" in str(ra.get("object_name", "")):
                    E(f"{lab}: object_name uses a ${{...}} variable; the User Guide (9.2.x p.122) documents variables only in "
                      "section/subsection descriptions and question/rationale text, so the name would be literal")
                if op == "create_object" and not ra.get("skip_if_exists"):
                    E(f"{lab}: set skip_if_exists: true (reject -> resubmit re-runs the action and fails on the duplicate)")
            for v in (ra.get("set") or {}).values():
                if isinstance(v, str) and v.startswith("@answer:") and v[8:] not in qmap:
                    E(f"{lab}: set uses unknown question {v}")
        ops = {o.get("operation") for o in (qn.get("workflow") or {}).get("operations", []) or []}
        if any(q.get("type") == "object_selector" for q in qmap.values()) and "associate_object_selector" not in ops:
            E("object_selector questions only associate the chosen objects when the workflow has the "
              "'Associate questionnaire object selector responses' operation (operation: associate_object_selector)")
        lso = qn.get("low_score_objects")
        if lso and lso.get("object_type") in ("SOXDocument", "SOXExternalDocument"):
            E("low_score_objects.object_type cannot be File/Link")
        for tc in qn.get("tests", []):
            for qid, a in (tc.get("answers") or {}).items():
                q = qmap.get(qid)
                if not q:
                    E(f"test '{tc.get('name')}': unknown question {qid}")
                elif q.get("type") in ("single", "multiple"):
                    texts = {x.get("text") for x in q.get("answers", [])}
                    for v in (a if isinstance(a, list) else [a]):
                        if v not in texts:
                            E(f"test '{tc.get('name')}': '{v}' is not an answer of {qid}")
                    if q["type"] == "single" and isinstance(a, list):
                        E(f"test '{tc.get('name')}': {qid} is single choice")
                    if q["type"] == "multiple" and isinstance(a, list) and len(a) > 1 and any(x.get("exclusive") and x.get("text") in a for x in q.get("answers", [])):
                        E(f"test '{tc.get('name')}': {qid} combines an exclusive answer with others")
    return errs


def iter_fields(t: dict):
    for g in t.get("field_groups", []):
        for f in g.get("fields", []):
            yield f"{g['name']}:{f['name']}", f


def parent_types(t: dict) -> list[str]:
    return [p["type"] if isinstance(p, dict) else p for p in t.get("parents", [])]


def primary_parent(t: dict) -> str | None:
    for p in t.get("parents", []):
        if isinstance(p, dict) and p.get("primary"):
            return p["type"]
    ps = parent_types(t)
    return ps[0] if ps else None


def custom_types(spec: dict) -> list[str]:
    return [t["name"] for t in spec.get("object_types", [])]


def enum_names(fdef: dict) -> set[str]:
    return {(e.get("name") or e.get("localized_label") or "") for e in fdef.get("enum_values", []) if not e.get("hidden")}


def resolve_template(s: Any, ctx: dict) -> Any:
    if isinstance(s, str):
        return s.format(**ctx) if "{" in s else s
    if isinstance(s, dict):
        return {k: resolve_template(v, ctx) for k, v in s.items()}
    if isinstance(s, list):
        return [resolve_template(v, ctx) for v in s]
    return s


# ---- GRC Calculations (Admin Guide 9.2.x ch.14; see references/calculations.md)
CALC_TYPES = {"manual", "automatic", "runtime"}
CALC_RELATIONSHIPS = {"self", "child", "parent", "ancestor", "descendant", "preference"}
CALC_FUNCTIONS = {
    # strings
    "format", "indexof", "lastindexof", "length", "substring", "split", "join",
    # lists / numbers
    "append", "at", "avg", "count", "list", "max", "min", "remove", "round", "sqrt", "square", "sum",
    # dates
    "add_days", "add_months", "add_years", "end_of_month", "end_of_quarter", "end_of_year", "today", "tomorrow", "yesterday",
    # currency
    "base_amount_of", "base_code_of", "currency", "local_amount_of", "local_code_of", "ex_rate_of", "system_ex_rate_of",
    # condition functions
    "exists", "contains", "regex",
}
CALC_KEYWORDS = {"if", "then", "elif", "else", "endif", "and", "or", "not", "in", "in_group", "matches_any", "in_hierarchy"}
CALC_SYSVARS = {"TODAY", "END_USER", "APPLICATION_URL", "COGNOS_URL", "TASK_VIEW_URL"}
CALC_OP_NAME_RE = re.compile(r"^[A-Za-z_\-][A-Za-z0-9_\- ]*$")


def _strip_comments_and_strings(expr: str):
    """Return (code_without_strings_and_comments, errors). Strings become '' placeholders."""
    out, errs, i, n = [], [], 0, len(expr)
    while i < n:
        c = expr[i]
        if expr.startswith("/*", i):
            j = expr.find("*/", i + 2)
            if j < 0:
                errs.append("unterminated /* comment"); break
            i = j + 2; continue
        if expr.startswith("//", i):
            j = expr.find("\n", i)
            i = n if j < 0 else j; continue
        if c in "'\"":
            j = expr.find(c, i + 1)
            if j < 0:
                errs.append(f"unterminated string starting at position {i}"); break
            out.append("''"); i = j + 1; continue
        out.append(c); i += 1
    return "".join(out), errs


def lint_expression(expr: str, known_refs: set | None = None) -> list[str]:
    """Static checks for a GRC Calculation expression (syntax rules, Admin Guide 9.2.x p.366-368, 382-385).
    Not a full parser: catches the mistakes that block saving or cause 'Insufficient information'."""
    errs = []
    code, e = _strip_comments_and_strings(expr or "")
    errs += e
    refs = re.findall(r"\[\$(.*?)\$\]", code)
    if code.count("[$") != len(refs) or code.count("$]") != len(refs):
        errs.append("unbalanced [$ ... $] reference")
    bare = re.sub(r"\[\$.*?\$\]", " REF ", code)
    depth = 0
    for ch in bare:
        depth += ch == "("
        depth -= ch == ")"
        if depth < 0:
            errs.append("')' without matching '('"); break
    if depth > 0:
        errs.append("missing ')'")
    words = [w.lower() for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", bare)]
    ifs, endifs, elses = words.count("if"), words.count("endif"), words.count("else")
    if ifs != endifs:
        errs.append(f"{ifs} 'if' vs {endifs} 'endif'")
    if elses < ifs:
        errs.append("every if/elif chain needs a final 'else' (otherwise 'Insufficient information' at runtime)")
    for fn in re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(", bare):
        if fn.lower() not in CALC_FUNCTIONS and fn.lower() not in CALC_KEYWORDS:
            errs.append(f"unknown function '{fn}'")
    for fn in ("today", "tomorrow", "yesterday"):
        if re.search(rf"\b{fn}\b(?!\s*\()", bare, re.I):
            errs.append(f"'{fn}': syntax rules require {fn}() (some guide examples show ({fn}); prefer {fn}())")
    for r in refs:
        head = r.split("/", 1)[0]
        if r in CALC_SYSVARS or head in ("DaysFromNow", "Setting", "ApplicationText", "Preference"):
            continue
        if head.startswith(("Child:", "Parent:")):
            if not re.match(r"^(Child|Parent):[A-Za-z][A-Za-z0-9]*/[^/]+:[^/]+(/(AscBy|DescBy):[^/]+:[^/]+)?$", r):
                errs.append(f"related reference '[${r}$]' should be [$Child:Type/Group:Field$] (optionally /AscBy: or /DescBy:Group:Field)")
            continue
        if head.lower().startswith(("child:", "parent:")):
            errs.append(f"'[${r}$]': write Child:/Parent: with a capital letter")
            continue
        if ":" in r:
            continue            # Field Group:Field on the current object
        if known_refs is not None and r not in known_refs:
            errs.append(f"'[${r}$]' is not an earlier operation of this calculation (names are case-sensitive)")
    if re.search(r"System Fields:Comment", expr or ""):
        errs.append("do not use System Fields:Comment in calculations (reserved field)")
    return errs


def lint_calculations(spec: dict, custom_types: set) -> list[str]:
    errs = []
    names = set()
    for c in spec.get("calculations", []) or []:
        cn = c.get("name", "")
        where = f"calculation '{cn}'"
        if not CALC_OP_NAME_RE.match(cn or "?"):
            errs.append(f"{where}: invalid name (A-Z a-z 0-9 _ - space)")
        if cn in names:
            errs.append(f"duplicate calculation '{cn}'")
        names.add(cn)
        if c.get("object_type") not in custom_types | BUILTIN_TYPES:
            errs.append(f"{where}: object_type '{c.get('object_type')}' not in spec")
        if str(c.get("type", "")).lower() not in CALC_TYPES:
            errs.append(f"{where}: type must be one of {sorted(CALC_TYPES)}")
        ops = []
        for op in c.get("inputs", []) or []:
            on = op.get("name", "")
            if not CALC_OP_NAME_RE.match(on or "?") or on[:1].isdigit():
                errs.append(f"{where}: input '{on}': invalid operation name")
            if str(op.get("relationship", "self")).lower() not in CALC_RELATIONSHIPS:
                errs.append(f"{where}: input '{on}': relationship must be one of {sorted(CALC_RELATIONSHIPS)} (no siblings)")
            if ":" not in str(op.get("field", "")):
                errs.append(f"{where}: input '{on}': field must be 'Field Group:Field'")
            ops.append(on)
        sets = c.get("variables", []) or []
        outs = c.get("set", []) or []
        if not outs:
            errs.append(f"{where}: needs at least one 'set' operation")
        for v in sets + outs:
            label = v.get("name") or v.get("field")
            for m in lint_expression(v.get("expression", ""), set(ops)):
                errs.append(f"{where}: '{label}': {m}")
            if v.get("name"):
                ops.append(v["name"])
        for o in outs:
            f = str(o.get("field", ""))
            if f.startswith("System Fields:"):
                errs.append(f"{where}: cannot set system field '{f}'")
    return errs
