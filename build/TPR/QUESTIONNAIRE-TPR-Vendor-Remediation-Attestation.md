# Questionnaire build checklist: TPR Vendor Remediation Attestation

Scoring: **simple** · Lifecycle: **3 Stage Lifecycle (with review)** · Assets: Vendor

Reference: skills/openpages-solutions/references/questionnaires.md. Authoring is UI-only (Questionnaire Template Editor).

## 0. Prerequisites

- [ ] Response-action / low-score target types exist and are children of the asset type(s) (`verify_spec.py`)
- [ ] Permissions per references/questionnaires.md (template, section/subsection/question templates, Program, QuestionnaireAssessment, assets, File)
- [ ] Mail server configured (assignee notifications)
- [ ] Template, assets and program will be in the **current reporting period**

## 1. Template object

- [ ] Primary menu > Assessments > Questionnaire templates > **New**
  - Name `TPR Vendor Remediation Attestation`; Description: Annual attestation of third-party remediation governance; Questionnaire Scoring Method: Simple
  - Primary Owner / Reviewer / Approver: <your-user> / <your-user> / None; Select Folder
- [ ] Save → **Editor** tab → **Blank**
- [ ] Format settings: Titles **Off**, Auto numbering **On**, Weight and score **On**
- [ ] Introduction: title (≤4000), description (≤2048), translations; logo optional

## 2. Sections, subsections, questions

### Section: Governance (weight 1)

#### Subsection: Ownership (weight 1)

| ID | Type | Req | W | Question | Answers (score) | Display logic | Comments / attachments |
|---|---|---|---|---|---|---|---|
| q1 | Single choice | Y | 1 | Is there a named owner for remediation of findings at ${asset.name}? | Yes (10), No (0) |  | comment optional, attachment optional |
| q2 | Long text | Y | 1 | Describe the current remediation plan. |  | (1) q1 in ['Yes'] | comment optional, attachment optional |
| q3 | Multiple choice | Y | 1 | Which controls are in place? | MFA (10), Encryption (10), None of the above (-1) excl. |  | comment optional, attachment optional |

### Section: Monitoring (weight 1)

#### Subsection: Oversight (weight 1)

| ID | Type | Req | W | Question | Answers (score) | Display logic | Comments / attachments |
|---|---|---|---|---|---|---|---|
| q4 | Single choice | Y | 1 | How often is the vendor reviewed? | Annually (10), Every 2 years (5), Never (0) |  | comment optional, attachment optional |

- [ ] Enter the spec `id` in each question's **Reference** field (not shown to respondents) so answers can be traced back to the spec
- [ ] Dependencies: Display logic > Condition builder; keep controlling + dependent questions in the same subsection

## 3. Response actions (Editor > Response actions > New response action)

- [ ] **Finding when no remediation owner**: when (1) q1 in ['No'] → create_object `Finding`, name 'No remediation owner', **Skip if it exists**
  - [ ] Description: Set field = Raised by questionnaire: vendor has no named remediation owner
  - [ ] TPR-Fnd:Source: Set field = Vendor Attestation
- [ ] **Finding when vendor never reviewed**: when (1) q4 in ['Never'] → create_object `Finding`, name 'Vendor never reviewed', **Skip if it exists**
  - [ ] Description: Set field = Raised by questionnaire: vendor oversight review never performed
  - [ ] TPR-Fnd:Source: Set field = Vendor Attestation
- Response actions ignore views: set every required field of created objects.

## 4. Workflow

- [ ] Edit shared workflow **Questionnaire Assessment Workflow** in place (shared change: other programs use it; running assessments keep their version). First confirm no other template has response actions
- [ ] Every stage sets lifecycle fields: `OPLC-QAssessment:LCStage` (`3Stage-Info` etc.: lifecycle-prefixed enum values), `OPLC-Std:LCReadOnly`, `OPLC-Std:LCInReview`; `OPLC-QAssessment:LCName` comes from the program
- [ ] Every stage has an assignee (respondent = asset owner)
- [ ] Stage **Review** → action **Approve and Close** → New Operation: Questionnaire response action
- [ ] Stage **Approval** → action **Approve and Close** → New Operation: Questionnaire response action — 4-stage lifecycle programs
- [ ] Stage **Information Gathering** → action **Submit and Close** → New Operation: Questionnaire response action — 2-stage lifecycle (no review)
- [ ] Publish

## 6. Test program

- [ ] Assessments > Programs > New: type Assessment Questionnaire, owner/reviewer/approver, primary business entity, Lifecycle **3 Stage Lifecycle (with review)**, due date
- [ ] Select Questionnaire from Library → `TPR Vendor Remediation Attestation`; Assets in Program: one **test** Vendor owned by a test respondent
- [ ] Launch; check Process History; confirm the template is now locked

| Test case | Answers | Expected compliance | Expected risk | Hidden | Expected objects |
|---|---|---|---|---|---|
| all controls, reviewed annually | {'q1': 'Yes', 'q2': 'Quarterly patch cycle', 'q3': ['MFA', 'Encryption'], 'q4': 'Annually'} | 100.0 | 0.0 | [] |  |
| no owner, no controls | {'q1': 'No', 'q3': ['None of the above'], 'q4': 'Every 2 years'} | 25.0 | 15.0 | ['q2'] | Finding 'No remediation owner' |
| no owner, second vendor (same business entity) | {'q1': 'No', 'q3': ['None of the above'], 'q4': 'Every 2 years'} | 25.0 | 15.0 | ['q2'] | Finding 'No remediation owner' |
| partial | {'q1': 'Yes', 'q2': 'x', 'q3': ['MFA'], 'q4': 'Never'} | 50.0 | 15.0 | [] | Finding 'Vendor never reviewed' |

- [ ] Answer each case as the respondent; submit; as reviewer check low-score icons; reject → resubmit once, then approve and close
- [ ] Check WHEN expected objects appear: if response actions sit on close actions, nothing exists after submit/reject and the objects appear only after close (once each)
- [ ] Fixed object names: object names must be unique within a folder (User Guide p.65). Run the same triggering answers for TWO assets under the same business entity and confirm EACH gets its object; with Skip if it exists the second one may be skipped. Fix: auto-naming for the target type (Applications > GRCM > Auto Naming > <type>)
- [ ] `op.py qa <assessment id> --out runs/qa-<case>.json`; compare scores with the table; `op.py query` for expected objects under the asset
- [ ] Program Report / Single Assessment Report; Export answers
