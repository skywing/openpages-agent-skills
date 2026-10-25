# TPR test evidence (dev container `local`, OpenPages 9.2.1)

Signed off by the solution owner, 2026-10-21. Raw outputs were in `runs/` on the dev workstation (test-local-*.json, qa-*.json, verify-local-*.md); `runs/` is not kept in git, so this file is the committed record.

## Remediation lifecycle (REST, `test_run.py specs/tpr-example.yaml --apply --cleanup`) - 7/7 PASS (2026-10-18)
- happy path to closed; rework loop; submit blocked without plan summary
- close blocked while a milestone is open; close blocked with no milestones (calculation TPR Open Milestones)
- vendor finding starts no audit workflow; ordinary finding still starts audit workflow (Sys-Workflow-Finding Applicability)

## Questionnaire (UI, test programs on template v1 and v2) - accepted
| Check | Result |
|---|---|
| Scores A / B | 100/0, 25/15 as spec (qr_score.py reproduced live values) |
| Score C | 75/5 on program 2: assessment kept launch-time "Never = -1"; template fixed to 0 (accepted, re-test with a new program when convenient) |
| Display logic (q2 hidden when q1 = No) | confirmed (vendor B) |
| Response actions create Findings with TPR-Fnd:Source = Vendor Attestation | confirmed: 12551 "No remediation owner", 12571 "Vendor never reviewed" |
| Skip if it exists | confirmed: reused vendors got no second Finding |

## Defects found and fixed during testing
- Template v1: q3 had a missing / mis-scored control; q4 "Never" scored -1 (excluded) -> v2 template, spec updated (Logging removed).
- Leftover enabled copy "TPR Questionnaire Assessment Workflow" (id 122) blocked all program launches ("saveResource" /
  "multiple workflows to start on object creation") -> disabled; verify_spec.py now warns on this.

## Open design item
- Skip if it exists is per vendor + Finding name: in an annual cycle a still-existing Finding suppresses a new one.
  Options: keep / put the cycle (year) in the Finding name / untick. Decision pending.

## Field generator (`gen_fields.py`) - 2026-10-22
- `--compare` against the reference dump (build/TPR/reference/tpr-reference-op-config.xml): 0 differences after the
  spec recorded 5 UI-only settings (Milestone Status default/search, Due Date description, Percent Complete 0-100,
  TPR-Rem group description).
- Generated `build/TPR/fields/tpr-fields-op-config.xml` (3 field groups, 13 fields, profile OpenPages Modules Master):
  first validate FAILED (includedObjectType displayOrder missing) -> fixed; second `ObjectManager.sh v c` = SUCCESS
  (both "ObjectManager Validation Process" and "Validate Migration File": STATUS_FINISHED_SUCCESS). Not loaded.
- Relationships (2026-10-23): relationship-set dump `build/TPR/reference/tpr-relationships-op-config.xml` (954 rels).
  `--compare --relationships`: 0 differences after the spec recorded Finding -> TPRRemediation max_parents 1.
  Generated `build/TPR/fields/tpr-relationships-op-config.xml` = the live 'SOX Extended Object Model' set, member for
  member (5, incl. 2 non-TPR SeleniumSurvey rels kept). `ObjectManager.sh v c ... tpr-relationships` = SUCCESS (2026-10-23). Not loaded.
