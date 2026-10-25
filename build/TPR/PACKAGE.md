# Package & deploy runbook: Third-Party Remediation Tracker v0.1.0

Target must run the **same OpenPages version and patch level** as dev (9.2.1).
Policy: no SQL/DDL; never drop or re-create Db2 tables or the reporting schema.

## What goes how

| Layer | Items | Mechanism | Why |
|---|---|---|---|
| 1 Object types | TPRRemediation, TPRMilestone | derived loaders `build/TPR/types/*-op-config.xml` (ObjectManager) | no UI to create types in 9.2.x |
| 2 Fields + profile inclusion | TPR-Rem, TPR-Ms, TPR-Fnd (on Finding); profiles OpenPages Modules Master | `gen_fields.py` loader, **regenerated against the target's dump** | merges into the shared profile instead of replacing it |
| 3 Relationships | Finding->TPRRemediation, TPRRemediation->TPRMilestone, Vendor->Finding | `gen_fields.py --relationships`, **from the target's relationship dump** | keeps every relationship the target already has in the UI set |
| 4 Solution-owned config | filters: TPR Open Remediations, TPR Vendor Findings; views: TPRRemediation-Task, TPRRemediation-Grid, TPRRemediation-Create; calculations: TPR Open Milestones; workflows: TPR Remediation Lifecycle; questionnaire templates: TPR Vendor Remediation Attestation | Configuration Packaging (Path A) or Export/Import Configuration | owned by this solution only |
| 5 Shared IBM workflows | Questionnaire Assessment Workflow, Sys-Workflow-Finding | **manual edit in target**, per the change list below | packaging would overwrite the target's own version |

**Do NOT package:** the whole `Object Profiles` item (it carries the full shared profile and would overwrite the target's), or `Object Types` for shared types (Finding, Vendor) - layers 2 and 3 cover the solution's part of them.

## Before the change window

- [ ] Change approval covers the **shared changes** (list below): they affect other teams' objects and programs
- [ ] Groups exist in target: `TPR Reviewers`
- [x] Decision: Rework action comment - decided 2026-10-23 (UAT/production: comment REQUIRED on Rework, tested by hand (REST v2 cannot pass action comments); dev keeps it optional for automated tests. Applied in the target after the package deploy (see the workflow's production overrides))
- [x] Decision: Skip if it exists on vendor Findings - decided 2026-10-23 (keep Skip if it exists: one standing Finding per gap per vendor; triage reuses or closes it)
- [x] Decision: Template v1 retirement - done 2026-10-23 (v1 marked superseded; v2 is current)
- [ ] Decision: Vendor Finding name collision - open (object names must be unique within a folder (User Guide p.65); run test case 'no owner, second vendor (same business entity)'. If the second vendor gets no Finding: switch Finding to auto-naming (Applications > GRCM > Auto Naming > Finding) and drop object_name)
- [ ] **Target snapshots** (rollback evidence + generator input), SAM off. First deployment: the solution's own types do not exist yet, so trim the reference filter to the profile, the shared types and their strings; the generator then assigns new profile displayOrders (max+1) and reporting column names (check the validate output)
  - reference dump with `build/TPR/template/ObjectManagerExportFilters-TPR-reference.xml` -> `build/TPR/target/<env>/tpr-reference-op-config.xml`
  - relationship-set dump (all dump options off except `content.type.relationship.sets`, no filter) -> `build/TPR/target/<env>/tpr-relationships-op-config.xml`
  - `dump_schema.py --env <env> --only TPR,Finding` (read-only)
- [ ] Regenerate against the target: `gen_fields.py <spec> --reference build/TPR/target/<env>/tpr-reference-op-config.xml --relationships build/TPR/target/<env>/tpr-relationships-op-config.xml --out build/TPR/target/<env>`
- [ ] Review both reports; `ObjectManager.sh v c` each loader **on the target** (validate only)
- [ ] Configuration Packaging in dev: package `TPR-0.1.0` with the layer-4 items; publish; export; import into target **without deploying**; compare

## In the change window (in this order)

SAM **off** for every ObjectManager load (the files carry their own systemAdminMode markers).

1. Load type `TPRRemediation`: `ObjectManager.sh l c <user> <pw> <dir> tprremediation` (derived loader; parents before children)
2. Load type `TPRMilestone`: `ObjectManager.sh l c <user> <pw> <dir> tprmilestone` (derived loader; parents before children)
3. Load fields: `... l c ... tpr-fields`
4. Load relationships: `... l c ... tpr-relationships`
5. Deploy the Configuration Package (layer 4); review View Priority conflicts
6. Shared change - `Questionnaire Assessment Workflow`: Add operation 'Questionnaire response action' to Review > Approve and Close, Approval > Approve and Close and Information Gathering > Submit and Close; publish as a new version (running assessments keep their version). Before: confirm no other template has response actions. Re-apply after fix packs that replace this workflow. Reason: TPR attestation response actions create Findings; a separate copy cannot be routed per template (no template field; Name = <asset>_QA_<seq>)
7. Shared change - `Sys-Workflow-Finding`: Applicability: add condition TPR-Fnd:Source is not equal to Vendor Attestation (keep any existing conditions). Publish. Reason: creating a Finding auto-starts this Internal Audit workflow (type=create); vendor-raised Findings have no Engagement or audit team
8. Production override - `TPR Remediation Lifecycle` > Review > **Rework**: set comment = required; publish (dev keeps the automatable setting); test by hand (below)
9. Reporting: Object Prefix for new types, Reporting Framework Generation **Update** (never Re-Create/Drop)

## Shared changes (for the change record)

| Change | Target | Reason |
|---|---|---|
| field group `TPR-Fnd` (Source) | Finding | mark Findings raised by the vendor attestation so the Internal Audit workflow skips them and reports can filter them |
| relationship Vendor -> Finding | Finding | questionnaire response actions create a Finding under the assessed Vendor |
| Add operation 'Questionnaire response action' to Review > Approve and Close, Approval > Approve and Close and Information Gathering > Submit and Close; publish as a new version (running assessments keep their version). Before: confirm no other template has response actions. Re-apply after fix packs that replace this workflow | workflow `Questionnaire Assessment Workflow` | TPR attestation response actions create Findings; a separate copy cannot be routed per template (no template field; Name = <asset>_QA_<seq>) |
| Applicability: add condition TPR-Fnd:Source is not equal to Vendor Attestation (keep any existing conditions) | workflow `Sys-Workflow-Finding` | creating a Finding auto-starts this Internal Audit workflow (type=create); vendor-raised Findings have no Engagement or audit team |

## Verify (target)

- [ ] `verify_spec.py <spec> --env <env>` -> 0 errors, no auto-start-collision warning (read-only)
- [ ] New dumps of the target, then `gen_fields.py <spec> --compare <new reference dump> --relationships <new relationship dump>` -> 0 differences
- [ ] UI smoke test as a business user (not admin): remediation Draft -> Review -> Approved -> Close incl. the milestone gates
- [ ] Manual test - `TPR Remediation Lifecycle` > Review > Rework: without a comment it is refused; with a comment it goes to Draft and the comment shows in the process history
- [ ] Questionnaire: one test program (3-stage) on a test vendor; Findings appear only at close with Source set; no audit workflow on them
- [ ] Write the results into a target TEST-EVIDENCE file (as `build/TPR/TEST-EVIDENCE.md` for dev)

## Rollback (per layer)

- Relationships: re-load the **pre-change** relationship dump of the target
- Fields / profile inclusion: added fields cannot be deleted safely once data exists; hide them from profiles and views instead (re-load the pre-change reference dump's profile entries)
- Object types: cannot be removed; disable their relationships and profile inclusion
- Layer 4: re-deploy the previous package version, or disable the workflow/calculation
- Shared workflows: revert the recorded edit and publish (the previous version stays in the workflow history)
