#!/usr/bin/env python3
"""
qr_score.py - expected questionnaire scores from a spec (offline).

For each questionnaire in the spec's `questionnaires:` section and each of its `tests:` cases, evaluates
question visibility (display logic), then computes Compliance and Risk scores with IBM's 9.2.x formulas
(see references/questionnaires.md, "Scoring formulas"). Compares with `expect:` when present.

  qr_score.py specs/tpr.yaml                  # all questionnaires, all test cases
  qr_score.py specs/tpr.yaml --json           # machine-readable
  qr_score.py specs/tpr.yaml --detail         # per-question breakdown

Exit 1 if any expectation fails. Assumption to calibrate once against a live assessment: unanswered
questions are excluded from both total and max score.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

CHOICE = {"single", "multiple"}


def _cond_true(c, answers, context):
    if "question" in c:
        a = answers.get(c["question"])
        vals = set(c.get("in", []))
        if a is None:
            return False
        chosen = set(a) if isinstance(a, list) else {a}
        return bool(chosen & vals)
    if "field" in c:  # attribute-based: value comes from test case context; unknown field => False (IBM: unrelated type -> false)
        if c["field"] not in context:
            return False
        v = context[c["field"]]
        op = c.get("op", "equal")
        t = c.get("value")
        if op == "equal":
            return v == t
        if op == "not equal":
            return v != t
        if op == "in":
            return v in (t or [])
        if op == "not in":
            return v not in (t or [])
        if op == "empty":
            return v in (None, "", [])
        if op == "not empty":
            return v not in (None, "", [])
        if op in ("greater than", "less than", "greater than or equal", "less than or equal"):
            v, t = float(v), float(t)
            return {"greater than": v > t, "less than": v < t, "greater than or equal": v >= t, "less than or equal": v <= t}[op]
        raise ValueError(f"unsupported operator in qr_score: {op}")
    raise ValueError(f"bad condition {c}")


def eval_logic(conds, logic, answers, context):
    vals = [_cond_true(c, answers, context) for c in conds]
    if not logic:
        return all(vals)
    expr = logic.lower()
    if not re.fullmatch(r"[\d\s()andornt]+", expr):
        raise ValueError(f"bad advanced logic: {logic}")
    expr = re.sub(r"(\d|\))\s+not\s", r"\1 and not ", expr)  # IBM: "1 not (2 or 3)" == 1 AND NOT (2 or 3)
    expr = re.sub(r"\d+", lambda m: f"v[{int(m.group()) - 1}]", expr)
    return bool(eval(expr, {"__builtins__": {}}, {"v": vals}))


def visible(q, answers, context, qmap, _seen=None):
    sw = q.get("show_when")
    if not sw:
        return True
    _seen = (_seen or set()) | {q["id"]}
    # a question controlled by a hidden question is hidden too
    for c in sw.get("conditions", []):
        cq = c.get("question")
        if cq and cq not in _seen and not visible(qmap[cq], answers, context, qmap, _seen):
            return False
    return eval_logic(sw.get("conditions", []), sw.get("logic"), answers, context)


def question_score(q, answer):
    """QS (0-10) or None if excluded."""
    if q.get("type") not in CHOICE or answer is None:
        return None
    scores = {a["text"]: a.get("score", 0) for a in q.get("answers", [])}
    valid = [s for s in scores.values() if s >= 0]
    if not valid:
        return None
    if q["type"] == "single":
        s = scores.get(answer)
        if s is None or s < 0:
            return None
        mx = max(valid)
        return 0.0 if mx == 0 else s / mx * 10
    chosen = answer if isinstance(answer, list) else [answer]
    sel = [scores[a] for a in chosen if a in scores]
    if any(s < 0 for s in sel):   # an excluded (-1) answer such as "None of the above" excludes the question
        return None
    tot = sum(valid)
    return 0.0 if tot == 0 else sum(sel) / tot * 10


def compute(qn, answers, context=None):
    context = context or {}
    method = qn.get("scoring", "simple")
    qmap = {q["id"]: q for s in qn.get("sections", []) for ss in s.get("subsections", []) for q in ss.get("questions", [])}
    TS = MS = 0.0
    detail = []
    for s in qn.get("sections", []):
        SW = s.get("weight", 1)
        if SW == 0:
            continue
        sec_tot = sec_max = 0.0
        for ss in s.get("subsections", []):
            SSW = ss.get("weight", 1)
            if SSW == 0:
                continue
            wqs = qw = 0.0
            for q in ss.get("questions", []):
                QW = q.get("weight", 1)
                vis = visible(q, answers, context, qmap)
                qs = question_score(q, answers.get(q["id"])) if vis else None
                detail.append({"q": q["id"], "visible": vis, "qs": None if qs is None else round(qs, 4), "weight": QW})
                if qs is None or QW == 0:
                    continue
                wqs += qs * QW
                qw += QW
            if qw == 0:
                continue
            if method == "weighted_average":
                sss, msss = SSW * (wqs / qw), SSW * 10
            else:
                sss, msss = SSW * wqs, SSW * qw * 10
            sec_tot += sss
            sec_max += msss
        TS += SW * sec_tot
        MS += SW * sec_max
    cs = None if MS == 0 else TS / MS * 100
    return {"total": round(TS, 4), "max": round(MS, 4), "compliance": None if cs is None else round(cs, 2),
            "risk": round(MS - TS, 2), "detail": detail}


def main(argv=None):
    from spec import load_file
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec"); ap.add_argument("--json", action="store_true"); ap.add_argument("--detail", action="store_true")
    args = ap.parse_args(argv)
    spec = load_file(args.spec)
    out, failed = [], 0
    for qn in spec.get("questionnaires", []):
        for tc in qn.get("tests", []):
            r = compute(qn, tc.get("answers", {}), tc.get("context", {}))
            exp = tc.get("expect", {})
            bad = [f"{k}: got {r[k]}, expected {v}" for k, v in exp.items() if k in ("compliance", "risk", "total", "max")
                   and (r[k] is None or abs(r[k] - v) > 0.01)]
            hidden_exp = set(exp.get("hidden", []))
            hidden_got = {d["q"] for d in r["detail"] if not d["visible"]}
            if "hidden" in exp and hidden_exp != hidden_got:
                bad.append(f"hidden: got {sorted(hidden_got)}, expected {sorted(hidden_exp)}")
            failed += bool(bad)
            out.append({"questionnaire": qn["name"], "test": tc["name"], **{k: r[k] for k in ("compliance", "risk", "total", "max")},
                        "hidden": sorted(hidden_got), "ok": not bad, "problems": bad, **({"detail": r["detail"]} if args.detail else {})})
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        for o in out:
            print(f"{'PASS' if o['ok'] else 'FAIL'}  {o['questionnaire']} / {o['test']}: compliance={o['compliance']} risk={o['risk']} (total={o['total']}, max={o['max']}) hidden={o['hidden']}")
            for p in o["problems"]:
                print(f"      {p}")
            for d in o.get("detail", []):
                print(f"      {d}")
        if not out:
            print("no questionnaire tests in spec")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
