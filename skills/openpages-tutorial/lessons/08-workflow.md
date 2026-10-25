# Lesson 08 - The workflow: stages, actions, validations, operations

**Time:** 90 min · **Changes OpenPages:** 1 workflow · **SAM:** not needed

## Objectives
- Build a GRC workflow in the Workflow Designer from the spec.
- Use set-field operations, validations with messages, and the *Run calculation* gate.
- Publish, understand versions, and verify the result through REST.

## Concepts

A workflow **definition** belongs to one object type; an object runs at most one workflow at a time. **Stages** (start,
standard, end) are connected by **actions**. On an action:
- **Conditions** show/hide the action.
- **Validations** let the user click, then block with a message until fixed.
- **Operations** do things: set fields, run calculation, create objects, start workflow, lock...
- Validations and operations run **in the order listed** and can be interleaved.

**Auto Start** starts the workflow when an object is created (UI, REST, or a questionnaire response action). The first
action (Start → Draft) runs by itself: use it to initialise fields. If a type has more than one workflow, Applicability
conditions are mandatory; two enabled auto-start workflows on one type break every save.

**Publish** creates a new version; active instances move to the latest version. Stage-level edits (assignees) on running
instances need **Sync** (Workflow Instances page).

Your lifecycle:
```text
Start --Begin--> Draft --Submit--> Review --Approve--> Approved --Expire--> End
                   ^                 |  \--Reject--> End
                   +----Rework-------+
Submit : validations Justification / Requested Expiry / Exception Owner not empty; set Status = In Review
Approve: 1) Run calculation PXKN Control Counts  2) Total Controls >= 1  3) Open Controls = 0  4) set Status = Approved
```

## Do

Checklist: `build/PXKN/BUILD.md` section 8 (`./op plan.py build specs/pxkn.yaml`). Administration menu > Solution
Configuration > **Workflows** > New.

1. Properties: name `PXKN Exception Lifecycle`, object type *KN Policy Exception*, Type **Auto Start**, Execute As System
   **False**.
2. Stages: Start, Draft, Review, Approved, End. Draft: assignee = field *Exception Owner*, task view `PXKNException-Task`.
   Review: assignee = yourself (real solutions use a reviewer group).
3. Actions exactly as the spec's `workflows:` (names matter: tests and REST use the action **name**):
   - Begin (Start → Draft): set field Status = Draft.
   - Submit (Draft → Review): three validations, each with the spec's message; set Status = In Review.
   - Approve (Review → Approved): **operation Run calculation `PXKN Control Counts` first**, then the two validations,
     then set Status = Approved. Drag to reorder if needed.
   - Rework (Review → Draft), comment optional; set Status = Draft.
   - Reject (Review → End), comment optional; set Status = Rejected.
   - Expire (Approved → End): set Status = Expired.
4. Publish.
5. Try it in the UI: create an exception with all fields and one control in status Proposed. Submit → Review. Approve →
   blocked with "Every control must be Implemented or Verified". Set the control to Implemented, Approve → Approved.
   Look at Open/Total Controls: filled by the calculation at that moment.
6. Read it back through REST:
   ```bash
   ./op op.py wf --type PXKNException
   ```

## Check
```bash
./op tutorial check 8
```
`verify_spec` compares stages, actions and targets with the spec, and warns if another auto-start workflow is enabled on
your type.

## Pitfalls
- Action renamed in the UI but not in the spec (or the reverse): tests fail with "action not found". The spec wins.
- Approve passes with no controls: you forgot the `Total Controls >= 1` validation, or the calculation is not published.
- Open/Total Controls blank after Approve: the calculation did not run (workflow or calculation not published).
- Required comment: REST API v2 on 9.2.1 cannot pass action comments (OP-08571), so automated tests cannot drive an
  action whose comment is required. The tutorial keeps comments optional; production designs test those by hand.
- Do not validate `System Workflow Fields:Action Comment`: it is empty while validations run and blocks every caller.

## Recap
1. Why does the Approve action run the calculation before validating?
2. What happens to running instances when you publish a new version?
3. What breaks if two auto-start workflows are enabled on one type?
