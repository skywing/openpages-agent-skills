# Troubleshooting (symptom → cause → fix)

Add a row every time something costs more than 15 minutes. Keep the OP-code, the trace id pattern and the fix.

## Configuration

| Symptom | Likely cause | Fix |
|---|---|---|
| Can't create field / relationship; buttons disabled or error | SAM off | Enable System Admin Mode |
| Export Configuration fails immediately | SAM on, or invalid triggers | Disable SAM; disable invalid triggers |
| "wait until processing is complete" | Another import/export/validate job running | Wait; one configuration job at a time |
| Import validation: `...is not defined in the migration package or in the target system!: Group Missing!` | Security domain group referenced by a profile user field is missing in target | Create/migrate the group (FastMap for business entities) first |
| Import log: `VALIDATION ERROR: 'businessUnit "<path>" does not exist.'` | Role assignment refers to a missing business entity | Migrate business entities first |
| Filter import fails | Filter criteria reference types/fields not in file or target | Include them in the package |
| Computed field blank after migration; profile imported fine | Namespace not migrated (not an auto dependency) | Include namespaces |
| Calculation import fails | Input/output field conflicts with existing target calculations | Disable target calculations, re-import |
| Wrong view shown after import | View Priority conflicts | Re-order priorities |
| New fields/types don't appear in Cognos | Reporting framework not regenerated, or new type missing from Object Prefix | Add `TYPE=Z<n>` to Object Prefix; Cognos Analytics > Reporting Framework Generation > Update; existing reports still need editing to show new fields |
| Profile imported but reporting looks stale | Profile import requires a reporting schema Update | SAM on → System Configuration > Reporting Schema > **Update** (not Re-Create) |
| A change needs a schema re-create (removed type/field, security model, past periods, URL settings, triangles) | IBM requires Re-Create, which drops the schema | Out of policy: redesign (disable instead of remove) or hand to platform owner/DBA via change management |
| Reporting schema create/recreate errors | >32,000-char SQL from too many fields | Exclude fields from reporting schema; fewer enum/currency fields |
| System slow/locks when adding fields (Db2) | Db2 locking on type/field modification | Do it off-peak |
| Field label `Tags`/`Delete`/`Folder Path`… breaks FastMap | Reserved labels | Rename label |
| ObjectManager metadata load (types/fields/relationships) fails or locks on Db2 | IBM guidance expects the reporting schema to be dropped first; we don't drop it (policy) | Stop. Do not retry blindly or touch the DB. Capture `ObjectManager.log` + trace ids, escalate to DBA / IBM Support |
| Circular relationship blocked (9.2.0+) | New relationship would create a cycle | Disable the conflicting relationship first |

## REST

| Symptom | Likely cause | Fix |
|---|---|---|
| 401 | Wrong creds; OAuth secret expired ("The client secret has expired") | Regenerate secret; check `Oauth2 Client Expiry` |
| Basic auth rejected on SaaS | Basic auth not available for OpenPages as a Service | Use API key / bearer |
| Query error with `SELECT *` | Not supported | List columns explicitly |
| Query misses rows the admin sees | Results honor caller's security | Expected; test with the right user |
| LIKE with apostrophe fails | Needs backslash escape | `\'` (Python `"\\'"`) |
| Create fails on enum value | Value not defined | Fix the value. Do **not** use `append_enum_vals=true` outside deliberate data loads |
| Can't add child to locked parent | Locked objects reject associations | Unlock, or registry `/OpenPages/Applications/GRCM/Locked Objects/Allowed Associations/*` |
| No workflow instance after create | Auto Start off, Applicability not met, object locked, or another workflow already running on the object | Check properties; `op.py get <id> --workflow` |
| Transition 4xx | Action name vs label, wrong instance id, a validation failed, or user is not an assignee | Use the action **name**; re-read instance; read the error `data` |

## Questionnaires

| Symptom | Likely cause | Fix |
|---|---|---|
| Response action / low-score object not created | Workflow action lacks the *Questionnaire response action* / custom action operation; target type not a child of the asset type (silently skipped) | Add the operation on the right action; add the relationship; `verify_spec.py` |
| Resubmit after reject fails on duplicate | Create-object response action without *Skip if it exists* | Tick it (lint enforces `skip_if_exists: true`) |
| Question answers "from field" not shown | Field's object type isn't the assessment's primary parent, or populate operation missing | Use a field on the primary parent; add *Set questionnaire answers with related field value* |
| Attribute-based dependency never shows the question | Condition on an object type unrelated to the assessment → false | Condition on the asset type actually linked |
| Questionnaire UI behaves oddly (read-only / no accept-reject) after workflow edits | Lifecycle fields not set per stage | Set `LCStage`, `LCReadOnly`, `LCInReview` in each stage's actions |
| Copied answers land in the wrong question | Question reworded to a different meaning (same internal id) | New meaning = new question |
| Imported template is empty / duplicated | Renamed template + old-version import | Create from copy, or import into another folder |
| Live compliance score differs from `qr_score.py` | IBM's weighted formulas are ambiguous; unanswered-question handling assumed | Record the observed behavior here and adjust `qr_score.py` |

## BYOM / GenAI (from past integration work)

Known codes met while wiring BYOM to a local Ollama through a Caddy HTTPS reverse proxy: `OP-63505`, `OP-63003`,
boolean type mismatches in the OpenAPI extension spec, and an empty `messages[]` array in the request mapping.
Record the confirmed cause and fix for each here the next time one appears. 9.2.0+ has a **model test page** that
shows raw JSON responses and validates JSONata mappings before runtime: use it first (it does not support file upload tests).

| Code / symptom | Cause | Fix |
|---|---|---|
| OP-63505 | *(record)* | *(record)* |
| OP-63003 | *(record)* | *(record)* |

## Environment notes (per release)

- 9.2.1 local container: *(record the calibration results from testing.md here: base URL, port, auth, workflow instance id behavior, pinned data types)*
