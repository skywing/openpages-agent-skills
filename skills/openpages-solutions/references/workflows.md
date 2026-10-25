# GRC Workflow (9.2.x)

Menu: **Open Administration menu > Solution Configuration > Workflows** → GRC Workflow Designer (graphical).
9.2.1: copy a workflow from the grid or from the configuration page (no export/import round trip).

## Model

- A **definition** belongs to exactly one object type; a type can have several definitions (e.g. Control Assessment,
  Control Change Request) but **an object runs at most one workflow at a time**.
- **Stages**: start, standard, end. **Actions** connect stages and carry: comment settings, **conditions**, **validations**,
  **operations**, email notification settings, run-in-background, Auto-Advance Stage.
- Each **publish creates a new version**. By default, since 9.0.0.1, active instances move to the latest published
  version (`Platform > Workflow Implementations > OpenPages > Keep active workflows on the latest published version`).
  If a stage is removed, instances on it stay on the old version until they reach a stage that exists in the new one.
- Publishing does **not** re-evaluate instances already on a stage (e.g. new assignee rules). 9.2.0 adds **Sync** on the
  Workflow Instances page to push stage-level edits (assignees, due date, criticality, stage subscribers) to instances on
  that stage; 9.2.1 shows the sync notice only when needed.
- A disabled definition starts no new instances; running ones continue.

## Properties

| Property | Notes |
|---|---|
| Label | A-Z a-z 0-9 _ - space; per locale |
| Type | **Auto Start** (on create or copy of the main object; not for sub-objects created by the copy) or **Manual Start** (Actions button) |
| Scheduled Start | Recurring / specified date-time / cron expression (not crontab). Shows as a Scheduler job |
| Execute As System | True → operations run as OPSystem (Activity tab shows OPSystem). Does not affect applicability |
| Automated | No standard stages; used by RCM rules |
| Oversight | Actor fields only (not System Workflow Fields:Overseers) |
| Overall Due Date | start date, value, related object field, preference object; with offset |
| Applicability | Conditions that decide whether this workflow starts; **mandatory when a type has more than one workflow**, and important for Auto Start. Advanced Logic: `1 and (2 or 3)` |
| Criticality | Map a single-value enum to low/medium/high/critical |

A locked object must be unlocked before a workflow can start on it.

## Actions: conditions vs validations vs operations

- **Conditions** hide/show actions (e.g. show *Escalate* when loss > 1M; hide *Submit* while children are open).
  On an auto-advance action they gate the advance, but may only reference the **current object**, and must not use
  system variables (`[$END_USER$]`, `[$TODAY$]`); only one auto action may be true at a time.
- **Validations** let the user click, then block with an error until fixed (required fields, children closed).
- **Operations**: create objects (+ associations), delete objects, custom action, lock/unlock, set fields, start workflow,
  run calculation, associate objects, populate questionnaire answers, delete comments, run an AI model (9.2.1: view-based models too).
- Validations and operations run **in the order listed**; you can interleave them.
  Pattern "gate on child state": Manual calculation counting children in a state (see `calculations.md` recipes) →
  on the action: *Run calculation* operation first, then a validation on the calculated field, then set-field operations.
  Also count ALL children (second input with no filter + second Set Field in the same calculation) and validate `>= 1`,
  otherwise an object with no children passes "open = 0". One validation per rule, each with its own message.
  Debug: a blank calculated field after the action = the calculation never ran (unpublished workflow/calculation).
- First action (start → first standard stage) runs automatically: use it to initialize fields. If there are several first
  stages, each start action needs a condition. The final action (last stage → end) resets fields / prepares the next workflow.
- If an operation or validation fails on an automatic action, the workflow returns to the last stage where a user chose an action.
- 9.2.0: `[$TODAY$]` and date system fields use the local time zone in expressions.

## Testing through the API

1. Create the object (`POST /contents`); an Auto Start workflow starts if Applicability passes.
   For Manual Start: `POST /workflows/definitions/{id}/start/{object id}`.
2. Find the object's current **activity instance** with `GET /workflows/instances/search` → `activity_instances[]`
   (`id`, `status` = stage label, `assignees`, `grc_object.id`) and **filter on `grc_object.id`** (live 9.2.1 ignores
   `object_id`/`grc_object_id` params). Do NOT use `GET /contents/{id}?include_workflow=true` → `workflow_activity_ids`:
   on 9.2.1 those ids are not activity-instance ids; used with `/workflows/instances/{id}` they returned HTTP 204 or
   **another object's** activity (a transition then moved the wrong object).
   `GET /workflows/instances/{activity id}` → details. Each transition returns a NEW `activity_instance_id`; follow it.
3. `POST /workflows/instances/{activity id}/transition/{action name}`: action **name**, not label. An empty HTTP 204
   means nothing was done. Check `grc_object_id` in the response. The final action returns `"process_state": "complete"`.
   **OP-08557 = a workflow validation failed**; the message names the field (e.g. `[Plan Summary] is required`).
   To require a comment, set the action's **comment requirement = required**. Do NOT also add a validation on
   `System Workflow Fields:Action Comment`: that read-only field is not filled when validations run, so the action
   fails for every caller, UI included (seen live on 9.2.1).
   **Action comments cannot be passed through the public REST API v2 on 9.2.1** (tested: body `comment`/`comments`/
   `action_comment`/`transitionComment.commentValue`, query params, field updates: all OP-08571 "A comment must be
   provided"). The UI uses an internal endpoint, `POST /app/api/taskview/transition?resourceId=&transitionName=&comment=`
   (PUT, body `{}`, session cookies + `op-csrf` header; basic auth is rejected with OP-00048 "session has expired";
   undocumented, may change between fix packs). Mark comment-required steps `manual: true` (+ `manual_reason`) in the
   spec: `test_run.py` drives the scenario up to that step, reports it as MANUAL (JUnit `skipped`, not a failure) and
   stops; check the action in the UI.
4. Re-read and assert stage + fields. A failed validation returns an error: that is a valid negative test.

`test_run.py` automates this from the spec. On first use against a new release, run one scenario with `-v` and confirm
which id the transition endpoint expects (activity-instance id from `workflow_activity_ids`).
Run tests as a user who is actually an assignee of the stage; admin may bypass what business users see.

## Migrating in-flight objects between workflow versions

- Default behavior already moves active instances to the latest version; only instances on **removed** stages lag.
- Plan: list active instances per stage (`GET /workflows/instances/search?workflow=<name>`), map old stages → new stages,
  keep every stage that has live instances until they drain, **or** transition them via the API before publishing the removal.
- After changing stage-level assignees/due dates, use **Sync** for the affected stage.
- Export does not carry views, object types or custom actions a workflow references; migrate them first.
