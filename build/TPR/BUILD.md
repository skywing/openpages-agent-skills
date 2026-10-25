# Build checklist: Third-Party Remediation Tracker v0.1.0 (OpenPages 9.2.1)

Work in the dev container. Tick each box. After the last step run:
`verify_spec.py <spec>` (must be 0 errors) then `dump_schema.py --only TPR` and commit `schema/`.

## 0. Prerequisites

- [ ] Logged in as an administrator with the **Object Types** application permission (and System Administration Mode permission)
- [ ] No other admin is editing the same object types (concurrent edits are rejected)
- [ ] Db2: schedule field/field-group changes on existing types for off-peak (locking delays)
- [ ] Ran the Schema Analysis report if adding fields to a type that already has many (reporting schema SQL limit 32,000 chars)
- [ ] Policy: no SQL/DDL against the database; never drop Db2 tables or the reporting schema (skip + flag any step that asks for it)

## 1. Enable System Admin Mode (SAM)

Required for object type, field group, field and relationship changes.
- [ ] Open Administration menu > System Admin Mode: **Enable** (or `PUT /v2/configuration/admin_mode?enable=true`)

## 2. Object types, field groups, fields

### Remediation (`TPRRemediation`)

- [ ] Create type `TPRRemediation` (system name immutable), label 'Remediation', plural 'Remediations', from template `SOXIssue` (no UI exists; see references/custom-object-type.md):
  - [ ] Dump template: `ObjectManager.sh d c <user> <pw> <dir> soxissue` (filters: contentType SOXIssue) → build/TPR/template/
  - [ ] `derive_type.py --dump build/TPR/template/soxissue-op-config.xml --baseline SOXIssue --spec <spec> --type TPRRemediation`; review the derive report
  - [ ] SAM on → `ObjectManager.sh v c ... tprremediation` → `l c ...` → SAM off. Do NOT drop the reporting schema; if the load fails, stop and escalate
  - [ ] Relationships > New Relationship: `Finding` as parent (added in UI, not in the loader)
- [ ] Edit properties: description, Title component, Global Search (Editing object type properties)
- [ ] Fields > New Field > Field Group > **New** `TPR-Rem`
  - [ ] `Status` - enum - REQUIRED - values: Draft, In Review, Approved, Closed; default: Draft (Profiles: OpenPages Modules Master)
  - [ ] `Severity` - enum - REQUIRED - values: Low, Medium, High, Critical (Profiles: OpenPages Modules Master)
  - [ ] `Target Date` - date - REQUIRED (Profiles: OpenPages Modules Master)
  - [ ] `Remediation Owner` - user_group - REQUIRED (Profiles: OpenPages Modules Master)
  - [ ] `Plan Summary` - long_string (Profiles: OpenPages Modules Master)
  - [ ] `Estimated Cost` - currency (Profiles: OpenPages Modules Master)
  - [ ] `Vendor Confirmed` - boolean - default: False (Profiles: OpenPages Modules Master)
  - [ ] `Open Milestones` - integer (Profiles: OpenPages Modules Master)
  - [ ] `Total Milestones` - integer (Profiles: OpenPages Modules Master)

### Milestone (`TPRMilestone`)

- [ ] Create type `TPRMilestone` (system name immutable), label 'Milestone', plural 'Milestones', from template `SOXTask` (no UI exists; see references/custom-object-type.md):
  - [ ] Dump template: `ObjectManager.sh d c <user> <pw> <dir> soxtask` (filters: contentType SOXTask) → build/TPR/template/
  - [ ] `derive_type.py --dump build/TPR/template/soxtask-op-config.xml --baseline SOXTask --spec <spec> --type TPRMilestone`; review the derive report
  - [ ] SAM on → `ObjectManager.sh v c ... tprmilestone` → `l c ...` → SAM off. Do NOT drop the reporting schema; if the load fails, stop and escalate
  - [ ] Relationships > New Relationship: `TPRRemediation` as parent (added in UI, not in the loader)
- [ ] Edit properties: description, Title component, Global Search (Editing object type properties)
- [ ] Fields > New Field > Field Group > **New** `TPR-Ms`
  - [ ] `Status` - enum - REQUIRED - values: Not Started, In Progress, Done; default: Not Started (Profiles: OpenPages Modules Master)
  - [ ] `Due Date` - date - REQUIRED (Profiles: OpenPages Modules Master)
  - [ ] `Percent Complete` - integer (Profiles: OpenPages Modules Master)

### Existing type `Finding` (field groups added by this solution)

Reason: mark Findings raised by the vendor attestation so the Internal Audit workflow skips them and reports can filter them

- [ ] Object Types > `Finding` > Fields > New Field > Field Group > **New** `TPR-Fnd`
  - [ ] `Source` - enum - optional - values: Vendor Attestation (Profiles: OpenPages Modules Master)

## 3. Relationships

Open Administration menu > Solution Configuration > Object Types > <type> > Relationships > New Relationship (SAM on).

- [ ] `Finding` → parent of `TPRRemediation` (primary)
- [ ] `TPRRemediation` → parent of `TPRMilestone`
- [ ] `TPRRemediation` → parent of `TPRMilestone` (primary)
- [ ] `Vendor` → parent of `Finding` (existing types; on `Finding` > Relationships) — questionnaire response actions create a Finding under the assessed Vendor

9.2.x validates against circular relationships; disable a conflicting relationship first if blocked.

## Reporting (if Cognos reports need the solution)

Per IBM's change table, new types / fields / associations need **no** reporting schema re-create or update, only a framework generation.
- [ ] Settings > Platform > Reporting Framework V6 > Configuration > Object Prefix: append `TPRREMEDIATION=ZA`, `TPRMILESTONE=ZB` (check the letters are unused)
- [ ] Cognos Analytics > Reporting Framework Generation > Update > Selected Models (the solution's model) > Submit; review details
- [ ] Test/extend reports (regeneration does not add new fields to existing reports)
- Never Re-Create or Drop the reporting schema (policy); see references/reporting.md

## 4. Disable System Admin Mode

- [ ] Open Administration menu > System Admin Mode: **Disable** (exports also fail while SAM is on)

## 5. Profiles

- [ ] Open Administration menu > Profiles > `OpenPages Modules Master`: include object types `TPRRemediation`, `TPRMilestone` and their fields; set required/optional per profile if needed

## 6. Public filters

- [ ] Object Types > `TPRRemediation` > Filters > add `TPR Open Remediations`: Status != Closed
- [ ] Object Types > `Finding` > Filters > add `TPR Vendor Findings`: TPR-Fnd:Source = Vendor Attestation

## 7. Views (View Designer)

Open Administration menu > Solution Configuration > Views. Prefer **Copy view** from the system view of the same object type, then edit on the Design tab. Save is automatic; **Publish** runs the full validation.

### Task View `TPRRemediation-Task` on `TPRRemediation`
- [ ] Start from: system view (View List > Include system views > open > Copy view)
- [ ] Section **Overview**: `Name`, `Description`, `TPR-Rem:Status`, `TPR-Rem:Severity`, `TPR-Rem:Target Date`, `TPR-Rem:Remediation Owner`
- [ ] Section **Plan**: `TPR-Rem:Plan Summary`, `TPR-Rem:Estimated Cost`, `TPR-Rem:Vendor Confirmed`
- [ ] Grid relationship field: Children → `TPRMilestone`; actions: New, Add, Delete; fields: Name, TPR-Ms:Status, TPR-Ms:Due Date, TPR-Ms:Percent Complete
- [ ] Card relationship field: Parents → `Finding`; actions: Add, Set Primary Parent; fields: default
- [ ] Set View Priority / default; enable
- [ ] Publish (fix all validation errors)

### Grid View `TPRRemediation-Grid` on `TPRRemediation`
- [ ] Columns: `Name`, `TPR-Rem:Status`, `TPR-Rem:Severity`, `TPR-Rem:Target Date`, `TPR-Rem:Remediation Owner`
- [ ] Set View Priority / default; enable
- [ ] Publish (fix all validation errors)

### Creation View `TPRRemediation-Create` on `TPRRemediation`
- [ ] Fields: `Name`, `Description`, `TPR-Rem:Severity`, `TPR-Rem:Target Date`, `TPR-Rem:Remediation Owner` (Creation Views must let the user pick a primary parent unless defaulted from context)
- [ ] Set View Priority / default; enable
- [ ] Publish (fix all validation errors)

## 7b. Changes to existing workflows

Open Administration menu > Solution Configuration > Workflows > <workflow> (edit, then Publish).

- [ ] `Questionnaire Assessment Workflow`: Add operation 'Questionnaire response action' to Review > Approve and Close, Approval > Approve and Close and Information Gathering > Submit and Close; publish as a new version (running assessments keep their version). Before: confirm no other template has response actions. Re-apply after fix packs that replace this workflow — TPR attestation response actions create Findings; a separate copy cannot be routed per template (no template field; Name = <asset>_QA_<seq>)
- [ ] `Sys-Workflow-Finding`: Applicability: add condition TPR-Fnd:Source is not equal to Vendor Attestation (keep any existing conditions) — creating a Finding auto-starts this Internal Audit workflow (type=create); vendor-raised Findings have no Engagement or audit team
- [ ] Publish each changed workflow; new objects use the latest published version

## 8. Workflows (GRC Workflow Designer)

Open Administration menu > Solution Configuration > Workflows > New (or copy an existing workflow, 9.2.1).

### `TPR Remediation Lifecycle` on `TPRRemediation`
- [ ] Properties: Type = Auto Start; Execute As System = False; Applicability conditions if >1 workflow on the type
- [ ] Stage **Start** (start)
  - [ ] Action **Begin** → Draft | set fields: TPR-Rem:Status=Draft
- [ ] Stage **Draft** (standard): assignee field:TPR-Rem:Remediation Owner; task view TPRRemediation-Task
  - [ ] Action **Submit** → Review | validations: TPR-Rem:Plan Summary is not empty | set fields: TPR-Rem:Status=In Review
- [ ] Stage **Review** (standard): assignee group:TPR Reviewers
  - [ ] Action **Approve** → Approved | set fields: TPR-Rem:Status=Approved
  - [ ] Action **Rework** → Draft | comment optional
- [ ] Stage **Approved** (standard)
  - [ ] Action **Close** → End | validations: TPR-Rem:Total Milestones >= 1 (message: Add at least one milestone before closing); TPR-Rem:Open Milestones = 0 (message: All milestones must be Done before closing) | set fields: TPR-Rem:Status=Closed
- [ ] Stage **End** (end)
- [ ] Publish. If you edited stage-level properties (assignees, due dates, subscribers) of a workflow with active instances, use **Sync** on the Workflow Instances page.

## 9. Verify

- [ ] `python scripts/verify_spec.py <spec>` → 0 errors
- [ ] `python scripts/test_run.py <spec> --apply --cleanup --junit runs/junit.xml` → all pass
- [ ] Display Debug Info on, open each view, confirm the right view is served and 'Why can't I save?' is clear
