# Lesson 09 - Automated tests with test_run

**Time:** 45-60 min · **Changes OpenPages:** test objects (cleaned up) · **SAM:** not needed

## Objectives
- Read and write test scenarios in the spec: data to create, workflow steps, expected stages and fields.
- Write negative tests (a validation must block).
- Run dry, then for real with cleanup and a JUnit report.

## Concepts

`test_run.py` reads `tests:` from the spec. A scenario creates objects (with `{run}` in names, replaced by a run id),
then drives the workflow through REST action by action and checks after each step:
```yaml
- name: approve blocked while a control is proposed
  create:
    - { ref: ex5, type: PXKNException, name: "KN-TEST Proposed Control {run}", parent: "@process", fields: {...} }
    - { ref: c5,  type: PXKNControl,   name: "KN-TEST Proposed {run}", parent: "@ex5", fields: {...} }
  workflow:
    object: "@ex5"
    steps:
      - { action: Submit,  expect_stage: Review }
      - { action: Approve, expect_error: true, expect_stage: Review }   # the validation must block
```
`@process` is a **fixture** (`tests.fixtures`): your Process from lesson 01. `expect_fields` checks values after a step;
`expect_state: completed` checks the workflow ended. Your spec has six scenarios: happy path, rework, three negatives,
reject.

**Dates.** `"2026-12-31"` is sent as midnight in the environment's `timezone`, so the UI shows 31 Dec. Scenario
"approve blocked with no controls" reads the date back after Submit to prove the round trip.

**Dry run first.** Without `--apply` nothing is written: you see what would be created and called. `--cleanup`
soft-deletes the test objects at the end. Every write is logged in `runs/audit.jsonl`.

## Do

1. Read your six scenarios. Add one of your own, for example "control verified also passes" (a control in status
   Verified, Approve → Approved). Use names starting with `KN-TEST`.
2. Dry run:
   ```bash
   ./op test_run.py specs/pxkn.yaml --env shared-dev
   ```
3. Run for real:
   ```bash
   ./op test_run.py specs/pxkn.yaml --env shared-dev --apply --cleanup --junit runs/tutorial/KN/junit.xml
   ```
4. A failure tells you the step and what differed. Fix the workflow or the spec (decide which one is wrong), re-run one
   scenario with `--only "<scenario name>"`.

## Check
```bash
./op tutorial check 9
```
Reads `runs/tutorial/<CODE>/junit.xml`: no failures, at least as many tests as scenarios.

## Pitfalls
- `fixture ... matched 0 objects`: the Process name in `tests.fixtures.process` does not match lesson 01's object.
- `action not found`: the action name in the UI differs from the spec.
- A negative test that passes for the wrong reason: check the error message names the field you expected.
- Tests run as you (an admin). Real users may see less; do a manual pass as a business user before promoting.

## Recap
1. What makes a good negative test?
2. Why does the tutorial check the expiry date after Submit?
3. What does `--cleanup` do, and what does it not do?
