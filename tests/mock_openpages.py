"""
mock_openpages.py - tiny in-memory OpenPages REST V2 stand-in used to test the skill's scripts.
Shapes follow the IBM OpenPages REST API V2 OpenAPI examples. Not a product emulator.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

P = "/opgrc/api/v2"


def fd(i, name, dt, req=False, enums=()):
    return {"id": str(i), "name": name, "localized_label": name.split(":")[-1], "data_type": dt, "required": req,
            "computed": False, "read_only": False, "dependencies": [], "is_hierarchical": False,
            "enum_values": [{"id": str(900 + n), "name": e, "localized_label": e} for n, e in enumerate(enums)]}


class State:
    def __init__(self):
        self.types = {
            "SOXIssue": {"id": "6", "name": "SOXIssue", "localized_label": "Issue", "root_folder_path": "/_op_sox/Project/Default/Issue",
                         "field_definitions": [fd(28, "Resource ID", "ID_TYPE", True), fd(1, "Name", "STRING_TYPE", True)]},
            "TPRRemediation": {"id": "501", "name": "TPRRemediation", "localized_label": "Remediation", "root_folder_path": "/x",
                               "field_definitions": [fd(28, "Resource ID", "ID_TYPE", True),
                                                     fd(10, "TPR-Rem:Status", "ENUM_TYPE", True, ["Draft", "In Review", "Approved", "Closed"]),
                                                     fd(11, "TPR-Rem:Severity", "ENUM_TYPE", True, ["Low", "Medium", "High", "Critical"]),
                                                     fd(12, "TPR-Rem:Target Date", "DATE_TYPE", True),
                                                     fd(13, "TPR-Rem:Remediation Owner", "STRING_TYPE", True),
                                                     fd(14, "TPR-Rem:Plan Summary", "LARGE_STRING_TYPE"),
                                                     fd(15, "TPR-Rem:Estimated Cost", "CURRENCY_TYPE"),
                                                     fd(16, "TPR-Rem:Vendor Confirmed", "BOOLEAN_TYPE"),
                                                     fd(17, "TPR-Rem:Open Milestones", "INTEGER_TYPE"),
                                                     fd(18, "TPR-Rem:Total Milestones", "INTEGER_TYPE")]},
            "TPRMilestone": {"id": "502", "name": "TPRMilestone", "localized_label": "Milestone", "root_folder_path": "/y",
                             "field_definitions": [fd(28, "Resource ID", "ID_TYPE", True),
                                                   fd(20, "TPR-Ms:Status", "ENUM_TYPE", True, ["Not Started", "In Progress", "Done"]),
                                                   fd(21, "TPR-Ms:Due Date", "DATE_TYPE", True),
                                                   fd(22, "TPR-Ms:Percent Complete", "INTEGER_TYPE")]},
        }
        self.types["QuestionnaireAssessment"] = {"id": "700", "name": "QuestionnaireAssessment", "localized_label": "Questionnaire Assessment", "root_folder_path": "/qa",
            "field_definitions": [fd(70, "OPLC-QAssessment:LCStage", "ENUM_TYPE", True, ["Information Gathering", "Review", "Approval"]),
                                  fd(71, "OPLC-QAssessment:LCName", "ENUM_TYPE", True, ["2 Stage Lifecycle (no review)", "3 Stage Lifecycle (with review)", "4 Stage Lifecycle (with review and approval)"]),
                                  fd(72, "OPLC-Std:LCReadOnly", "BOOLEAN_TYPE"), fd(73, "OPLC-Std:LCInReview", "BOOLEAN_TYPE")]}
        self.types["Vendor"] = {"id": "710", "name": "Vendor", "localized_label": "Vendor", "root_folder_path": "/v", "field_definitions": []}
        self.assoc = {
            "TPRRemediation": [{"id": "6", "name": "SOXIssue", "relationship": "Parent", "is_enabled": True, "min": 1, "max": 1},
                               {"id": "502", "name": "TPRMilestone", "relationship": "Child", "is_enabled": True, "min": 0, "max": 99}],
            "TPRMilestone": [{"id": "501", "name": "TPRRemediation", "relationship": "Parent", "is_enabled": True, "min": 1, "max": 1}],
            "SOXIssue": [{"id": "710", "name": "Vendor", "relationship": "Parent", "is_enabled": True}],
            "QuestionnaireAssessment": [{"id": "710", "name": "Vendor", "relationship": "Parent", "is_enabled": True}],
            "Vendor": [],
        }
        tr = lambda n, t: {"name": n, "label": n, "target": t}
        self.wf = [{"id": "36", "name": "TPR Remediation Lifecycle", "type_definition_name": "TPRRemediation", "state": "published",
                    "version_number": "2", "is_enabled": True, "activities": [
                        {"name": "Start", "label": "Start", "type": "start", "transitions": [tr("Begin", "Draft")]},
                        {"name": "Draft", "label": "Draft", "type": "standard", "transitions": [tr("Submit", "Review")]},
                        {"name": "Review", "label": "Review", "type": "standard", "transitions": [tr("Approve", "Approved"), tr("Rework", "Draft")]},
                        {"name": "Approved", "label": "Approved", "type": "standard", "transitions": [tr("Close", "End")]},
                        {"name": "End", "label": "End", "type": "end", "transitions": []}]}]
        self.wf.append({"id": "40", "name": "TPR Questionnaire Assessment Workflow", "type_definition_name": "QuestionnaireAssessment", "state": "published",
                        "version_number": "1", "is_enabled": True, "activities": [
                            {"name": "Start", "type": "start", "transitions": [tr("Begin", "Information Gathering")]},
                            {"name": "Information Gathering", "type": "standard", "transitions": [tr("Submit for Review", "In Review")]},
                            {"name": "In Review", "type": "standard", "transitions": [tr("Accept", "Closed"), tr("Reject", "Information Gathering")]},
                            {"name": "Closed", "type": "end", "transitions": []}]})
        self.objects = {"7000": {"id": "7000", "name": "issue2", "type_definition_id": "6", "fields": [],
                                 "path": "/_op_sox/Project/Default/Issue/Test 01/issue2.txt"}}
        self.inst = {}  # instance id -> {obj, stage, done}
        self.next = 8000
        self.writes = []
        self.admin_mode = False


S = State()
SETS = {"Submit": "In Review", "Approve": "Approved", "Close": "Closed"}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body=None):
        data = json.dumps(body).encode() if body is not None else b""
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _err(self, code, opcode, msg):
        self._send(code, {"status_code": str(code), "errors": [{"code": opcode, "message": msg}], "trace": "t-123"})

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n)) if n else None

    def _route(self, method):
        if not self.headers.get("Authorization", "").startswith("Basic "):
            return self._err(401, "OP-00401", "unauthorized")
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        path = unquote(u.path)
        p = path[len(P):] if path.startswith(P) else None
        if p is None:
            return self._err(404, "OP-404", "not found")
        parts = [x for x in p.split("/") if x]
        body = self._body() if method in ("POST", "PUT", "DELETE") else None
        if method != "GET":
            S.writes.append((method, p, q, body))
        if parts == ["types"]:
            return self._send(200, {"types": [{k: v for k, v in t.items() if k != "field_definitions"} for t in S.types.values()]})
        if len(parts) == 2 and parts[0] == "types":
            t = S.types.get(parts[1]) or next((x for x in S.types.values() if x["id"] == parts[1]), None)
            return self._send(200, t) if t else self._err(404, "OP-10404", "type not found")
        if len(parts) == 3 and parts[0] == "types" and parts[2] == "associations":
            return self._send(200, {"associations": S.assoc.get(parts[1], [])})
        if parts == ["configuration", "admin_mode"]:
            return self._send(200, {"enabled": S.admin_mode})
        if parts == ["workflows", "definitions"]:
            return self._send(200, {"definitions": S.wf})
        if parts == ["query"] and method == "POST":
            rows = [{"fields": [{"name": "Resource ID", "value": o["id"]}, {"name": "Name", "value": o["name"]}]} for o in S.objects.values()]
            off, lim = body["offset"], body["limit"]
            return self._send(200, {"definitions": [], "rows": rows[off:off + lim]})
        if parts == ["contents"] and method == "POST":
            tname = body["type_definition_id"]
            t = S.types.get(tname)
            if not t:
                return self._err(400, "OP-10001", "bad type")
            fields = {f["name"]: f["value"] for f in body.get("fields", [])}
            for fdef in t["field_definitions"]:
                if fdef["enum_values"] and fdef["name"] in fields:
                    if fields[fdef["name"]].get("name") not in {e["name"] for e in fdef["enum_values"]}:
                        return self._err(400, "OP-63003", "invalid enum")
            oid = str(S.next); S.next += 1
            obj = {"id": oid, "name": body["name"], "type_definition_id": t["id"], "primary_parent_id": body.get("primary_parent_id"),
                   "fields": [{"name": k, "value": v} for k, v in fields.items()]}
            if tname == "TPRRemediation":
                iid = str(S.next); S.next += 1
                S.inst[iid] = {"obj": oid, "stage": "Draft", "done": False}
                obj["workflow_activity_ids"] = [iid]
                self._setf(obj, "TPR-Rem:Status", {"name": "Draft"})
            S.objects[oid] = obj
            return self._send(200, obj)
        if len(parts) >= 2 and parts[0] == "contents":
            oid = parts[1]
            obj = S.objects.get(oid) or next((o for o in S.objects.values() if o.get("path") == "/" + "/".join(parts[1:])), None)
            if len(parts) == 3 and parts[2] == "associations":
                return self._send(200, {"associations": []} if method == "GET" else None)
            if not obj:
                return self._err(404, "OP-10404", "object not found")
            if method == "GET":
                return self._send(200, obj)
            if method == "DELETE":
                S.objects.pop(obj["id"], None)
                return self._send(204)
        if parts and parts[0] == "questionnaire" and len(parts) == 3:
            return self._send(200, {"id": parts[1], "kind": parts[2], "complianceScore": 25.0, "riskScore": 15.0})
        if parts[:2] == ["workflows", "instances"] and len(parts) == 3:
            i = S.inst.get(parts[2])
            if not i:
                return self._err(404, "OP-WF404", "no instance")
            return self._send(200, {"id": parts[2], "status": "completed" if i["done"] else i["stage"],
                                    "workflow": {"id": "36", "name": "TPR Remediation Lifecycle", "version": "2", "activity": {"id": "1", "name": i["stage"], "label": i["stage"]}}})
        if parts[:2] == ["workflows", "instances"] and len(parts) == 5 and parts[3] == "transition":
            i = S.inst.get(parts[2]); act = parts[4]
            wf = S.wf[0]
            st = next(a for a in wf["activities"] if a["name"] == i["stage"])
            tr = next((t for t in st["transitions"] if t["name"] == act), None)
            if not tr:
                return self._err(400, "OP-WF100", f"action {act} not available")
            obj = S.objects[i["obj"]]
            if act == "Submit" and not any(f["name"] == "TPR-Rem:Plan Summary" and f["value"] for f in obj["fields"]):
                return self._err(400, "OP-WF200", "Validation failed: Plan Summary is required")
            i["stage"] = tr["target"]
            if tr["target"] == "End":
                i["done"] = True
                obj["workflow_activity_ids"] = []
            if act in SETS:
                self._setf(obj, "TPR-Rem:Status", {"name": SETS[act]})
            return self._send(200, {"grc_object_id": obj["id"], "workflow_id": "36", "process_state": "completed" if i["done"] else "open",
                                    "activity_instance_id": parts[2], "activity_name": i["stage"], "activity_label": i["stage"]})
        return self._err(404, "OP-404", f"no route {method} {p}")

    @staticmethod
    def _setf(obj, name, value):
        for f in obj["fields"]:
            if f["name"] == name:
                f["value"] = value
                return
        obj["fields"].append({"name": name, "value": value})

    def do_GET(self):
        self._route("GET")

    def do_POST(self):
        self._route("POST")

    def do_PUT(self):
        self._route("PUT")

    def do_DELETE(self):
        self._route("DELETE")


def start(port=0):
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv
