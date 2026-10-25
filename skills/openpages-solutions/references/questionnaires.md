# Questionnaire solutions (9.2.x)

Source: 9.2.x User Guide > *Questionnaires*; Administrator's Guide > *Getting started with questionnaire assessments*,
*Configuring Workflows* (questionnaire operations), *Custom Machine Learning Models* (questionnaire answering),
*FastMap* (export), Solutions Guide > *Object name mapping*.

## The framework is built in: configure it, don't create types

| Object type (system name) | Label | Role |
|---|---|---|
| `QuestionnaireTemplate` | Questionnaire Template | The questionnaire design; parent of sections |
| `SectionTemplate` → `SubSectionTemplate` → `QuestionTemplate` | Section / SubSection / Question Template | Content hierarchy (questions live in subsections only) |
| `Program` | Program | Launches assessments for a set of assets; defines owner, reviewer, approver, lifecycle, due date |
| `QuestionnaireAssessment` | Questionnaire Assessment | One instance per asset; answered by the respondent; driven by a workflow |
| Assets: `Resource` (Asset), `SOXProcess`, `SOXSubprocess`, `Vendor`, `Engagement`, `Employee` | | What is assessed. Respondent = asset primary owner (or the employee) |

"Questionnaire" (legacy object type) is unrelated to Questionnaire Assessments. Never use it.

A questionnaire **solution** = template content + scoring + dependencies + response actions (what answers do to
other objects) + the Questionnaire Assessment Workflow + program/lifecycle + permissions + (optional) AI answering and
reporting. The only custom object types you might add are **targets** of response actions (e.g. a remediation record),
built with `custom-object-type.md`.

## What is UI-only vs verifiable through the API

| Task | How |
|---|---|
| Author template content, scoring, dependencies, response actions, AI model association | **Questionnaire Template Editor** (UI). No documented REST authoring API |
| Workflow operations | GRC Workflow Designer (UI) |
| Create programs, launch | UI (Assessments > Programs) |
| Read an assessment / template as JSON | REST `GET /v2/questionnaire/{id}/assessment`, `GET /v2/questionnaire/{id}/template` (read-only; used by `op.py qa` / `op.py qt`) |
| Drive the assessment workflow in tests | REST workflow transition (same as other workflows) |
| Check response-action results (created/updated objects) | REST query / `op.py` |
| Promote templates | **Export/Import Configuration** (category *Questionnaire Templates*) or Configuration Packaging. **Not FastMap** (loses dependencies/response actions) |

## Design rules

1. **Limits (IBM recommended max):** 1000 questions per template; 199 subsections+questions per section; 50 questions
   (incl. dependent) per subsection. Dependency depth: up to 6 levels (9.2.0+); a question already 5 levels deep can't be
   a controlling question.
2. **Question types:** Single choice, Multiple choice (can mark answers *Exclusive*, e.g. "None of the above"), Short text
   (252 chars), Long text (2048), Table (≤15 columns, ≤30 rows, 50 chars/cell, stored as pipe-delimited CSV; can be
   dependent, never controlling), Email, URL, User/Group, User, Group (9.2.0), Date, Decimal, Integer (9.2.1).
   **Only single/multiple choice are scored.** All others are excluded from scoring.
3. **Controlling questions** must be single/multiple choice; no circular dependencies. Attribute-based conditions
   evaluate fields of the assessment's related object; conditions on object types not related to the assessment
   resolve to **false**. Hidden questions are excluded from scoring. Keep controlling and dependent questions in the
   same subsection: moving one across subsections drops the dependency.
4. **Stable question identity.** *Copy answers* (from a previous program) and reporting rely on internal question
   identifiers. Edit wording lightly; don't repurpose a question for a different meaning (old answers would be copied into
   it). New meaning = new question. Since 9.0.0.5, choice options have a stable *name* plus an editable *label*.
5. **Versioning.** A template locks when a program launches it. For a new version use **Create from copy** into its own
   folder (a second copy in the same folder is copied from the first copy). Don't rename a template and re-import an old
   version (that creates an empty template and updates the renamed one).
6. **Scoring method:** *Simple* when the focus is question-level; *Weighted average* when some subsections matter more.
   Answer score −1 to 9999 (−1 excludes the answer); weights 0 to 9999 (0 excludes). Use a small consistent answer range,
   e.g. 0 to 10 with 10 = best. Formulas below; `qr_score.py` computes expected scores from the spec.
7. **Answers from fields:** single choice ↔ single-select field, multiple ↔ multi-select, short/long text ↔ text field.
   The field's object type must be the assessment's **primary parent**, or the question is not displayed. Populated only
   when the workflow operation runs (not live).
8. **Response actions** (template *Response actions* panel): `Set fields` (Set field / Set field with answer / Add new
   values to field), `Create object` (child of the assessment's parent asset), `Copy object` (+ one level of *Copy related
   child*). Conditions: question-based, `in` operator, Advanced logic. Target object types unrelated to the assessment are
   skipped. For create: tick **Skip if it exists** (a reject → resubmit otherwise fails on the duplicate name). Response
   actions ignore views, so **set every required field** of created objects. In expressions, *self* = the assessment when
   setting fields on existing objects, but = the assessment's parent when creating/copying.
9. **Nothing runs by itself.** Response actions and field-populated answers only run when the **Questionnaire Assessment
   Workflow** has the matching operation on an action.

## Questionnaire Assessment Workflow

OpenPages ships **Questionnaire Assessment Workflow**. Prefer **copying it (9.2.1 copy)** and editing the copy over
editing the original. If both stay enabled on `QuestionnaireAssessment`, give them **Applicability** conditions, since an
object runs one workflow at a time.

**Applicability caveat (9.2.1, checked 2026-10-08):** `QuestionnaireAssessment` has NO field naming its template or
program, its Name is `<asset name>_QA_<7-digit seq>` (no template name), and workflows start on create (launch), before
anyone could set a marker field. So a copy cannot be routed per template, and **disabling the original moves every other
program onto your copy** (don't). Pattern: add your operations to the **shipped workflow in place** as a new version
(running assessments keep their version) and treat it as a shared change: change approval, record it in the spec's
`workflow_changes`, re-apply after fix packs. The *Questionnaire response action* operation runs each assessment's own
template response actions, so templates without response actions are unaffected; check existing templates first.
**Seen live (2026-10-21):** an enabled copy left next to the original made every program launch fail with
*"The program launch internal error: ... saveResource"*; the server log said *"Failed to start workflow. There are
multiple workflows to start on object creation"*. Disable any copy you are not using; `verify_spec.py` now warns.

**Observed in the first TPR test program (9.2.1, 2026-10-21):**
- Assessment names were `<Program name> - <asset name>` for that program, while older programs on the same server had
  `<asset name>_QA_<seq>`. Don't rely on the name format.
- `OPSS-QAssessment:ComplianceScore` / `RiskScore` are INTEGER fields: 83.33 / 3.33 show as 83 / 3.
- In `op.py qa` JSON the two numbers swap meaning by level (observed on 3 assessments, consistent):
  **question** level: `compliance_score` = maximum points, `risk_score` = achieved (q1 = No: 10 / 0);
  **section / subsection** level: `compliance_score` = achieved, `risk_score` = maximum (Governance 15 / 20).
  An answer scored −1 (excluded) shows 0 / 0 at question level.
- Assessments keep the template **as it was at launch**: a template edited after launch (9.2.1 still allowed editing an
  answer score on a launched template) changes only programs launched later. Re-test with a NEW program.
- `qr_score.py` reproduced all three live assessments exactly once fed the template **as built**, so check the
  template's answer scores against the spec before blaming the formula.
- `LCStage` showed `2Stage-Close`: the program's Lifecycle decides the path, not the template. A 2-stage program never
  reaches Review, so actions on *Approve and Close* are not exercised.

Lifecycle fields the workflow **must** set (they drive the questionnaire UI):

| Field | Purpose |
|---|---|
| `OPLC-QAssessment:LCStage` | Required. Stored enum values on 9.2.1 (dump 2026-10-08) are lifecycle-prefixed: `2Stage-Info`, `2Stage-Close`, `3Stage-Info`, `3Stage-Review`, `3Stage-Close`, `4Stage-Info`, `4Stage-Review`, `4Stage-Approval`, `4Stage-Close` (UI labels read *Information Gathering* etc.) |
| `OPLC-Std:LCReadOnly` | Makes answers read-only |
| `OPLC-Std:LCInReview` | Enables accept/reject of answers |
| `OPLC-QAssessment:LCName` | Chosen lifecycle, values `2Stage`/`3Stage`/`4Stage` (labels *2 Stage Lifecycle (no review)* ...); copied from the program's `OPSS-Program:Lifecycle`. Programs and assessments must have it |
| `OPLC-QAssessment:LCStatus`, `OPLC-QAssessment:LCTransition`, `OPLC-Std:LCAssignee`, `OPLC-Std:LCDueDate`, `OPLC-Std:LCComment` | Also set by the shipped workflow (status, last transition such as `3Stage-Info-Submit`, assignee, due date); keep them in the copy |

Stages: 2-stage Information Gathering → Closed; 3-stage adds In Review (reject returns to Information Gathering);
4-stage adds In Approval. Assign a user at every stage (respondent = asset owner; last-stage owner may be the program owner).
The Actions button in the Task View and in the questionnaire UI are the same workflow.

Operations to add (Action → Validations and Operations → New Operation; permission *SOX > Administration > Workflow*):

| Need | Operation | Put it on |
|---|---|---|
| Run the template's response actions | **Questionnaire response action** | Prefer the **close** actions (*Approve and Close* on Review and on Approval, plus *Submit and Close* for 2-stage): objects then come only from reviewed, final answers, and reject/resubmit loops create nothing. On *Submit for Review* they fire on unreviewed answers and again on each resubmit |
| Pre-fill answers from fields | **Set questionnaire answers with related field value** (optional *Override user answers* = true) | the start/first action |
| Create an issue (or other child of the asset) per low-scoring answer | **Custom action**, class `com.ibm.openpages.api.service.local.workflow.actions.QuestionnaireScoreAssessmentAction`, properties `threshold` (default 5; object created when an answer's score < threshold), `objectType` (system name, default `SOXIssue`; must be a child of the asset type; not SOXDocument/SOXExternalDocument). Files attached to the answer are attached to the new object | e.g. *Submit and Close* / *Submit for Review* |

If the target type is not yet a child of the asset type (e.g. `Finding` under `Vendor` on 9.2.1), add the link as a top-level
`relationships:` entry in the spec (with a `reason`); `plan.py build` lists it and `verify_spec.py` checks it live.

Execute As System = true when respondents lack write access to the target objects. Email notifications need the mail
server configured; the notification fires on creation and each transition.

## Permissions (role templates / RLS)

| Object type | Program owners (create + launch) | Respondents / reviewers |
|---|---|---|
| QuestionnaireTemplate | Read, Write, Associate | Read |
| SectionTemplate, SubSectionTemplate, QuestionTemplate | Read, Write | Read |
| Program | Read, Write, Associate | Read (4-stage: program owner is an assignee) |
| QuestionnaireAssessment | Read, Write, Associate | Read, Write, Associate (RLS on current assignee, or role template) |
| Assets linked to assessments | Read, Associate | Read, Associate |
| File (SOXDocument) | Lock, Unlock (role permissions) | Read, Write, Associate, Delete |
| Response-action targets (e.g. SOXIssue) | | Write/Associate, or use Execute As System |

Only program owners should be able to delete assessments. AI answering needs *SOX > User Interfaces > Show AI Insights*.

## Build sequence

1. **Spec** the `questionnaires:` section (template, scoring, questions, dependencies, response actions, workflow ops,
   tests). Lint: `verify_spec.py <spec> --lint-only`; expected scores: `qr_score.py <spec>`.
2. **Targets first:** any custom type used by response actions (`custom-object-type.md`), with the asset type as parent.
3. **Template:** Primary menu > Assessments > Questionnaire templates > New (name, description, scoring method, owner,
   reviewer, approver: **users only**, no groups, on 9.2.1; folder: the picker cannot create one, default root is
   `/_op_sox/Project/Default/ICDocumentation/Questionnaire Templates`) → Editor → Blank (or From template) → Format settings (Titles, Auto numbering, Weight and
   score) → Introduction (title ≤4000, description ≤2048, translations; logo PNG ≤350×200 in
   `<OP_HOME>/wlp-usr/shared/apps/op-apps.ear/taskui.war/images/questionnaire`) → sections/subsections → questions →
   dependencies (Display logic > Condition builder) → answers-to-field → response actions. `plan.py questionnaire <spec>`
   generates the checklist.
4. **Workflow:** add the operations above to the shipped Questionnaire Assessment Workflow in place (new version; see the
   Applicability caveat: a copy cannot be routed per template on 9.2.1), check lifecycle fields per stage, publish.
5. **Permissions** per table above.
6. **Optional AI answering (9.2.1):** Integrations > Custom Machine Learning Models > New model: Input type
   *Questionnaire* (`$questionnaireJSON$`), object type = asset type, optional file attachments (Gemini/OpenAI only,
   all files in one request), prompt **must** demand a JSON structure with question id, answer, reasoning, confidence;
   outputs via JSONata (question id, answer array, reasoning, confidence), optional confidence threshold, Model action
   *Automatically set*, timeout 1 to 300 s (default 120). Associate the model in the template Editor. Use the model
   test page first. Users run *Populate Answers*, choose replace vs unanswered-only, then review.
7. **Program:** Assessments > Programs > New (type Assessment/Classification, owner, reviewer, approver, primary
   business entity, **Lifecycle**, due date) → Select Questionnaire from Library → Assets in Program → **Launch**
   (optionally *Program to copy answers from*). Launch creates one assessment per asset (background), starts the
   workflow, emails respondents, and locks the template. Relaunch only adds assessments for new assets. Wrongly created
   assessments are removed by dissociating from the asset. Ad hoc: asset Task view > Assessment section > New.
8. **Current reporting period:** templates, assets and programs must be in the current reporting period.

## Testing

Answering happens in the UI (or AI populate). Everything around it is scriptable:
- Before: `verify_spec.py` (asset/target types, relationships, the copied workflow's stages/actions), `qr_score.py`
  expected Compliance/Risk scores per test case. For offline checks, snapshot the framework types too:
  `dump_schema.py --only <KEY>,QuestionnaireAssessment,<asset types>,<target types>`.
- Workflow action names come from the shipped workflow. Confirmed on 9.2.1 (workflow id 65, v1, published,
  "Questionnaire Assessment Workflow"; re-check with `op.py wf --type QuestionnaireAssessment` on other systems):
  `Start` -> **Information Gathering** (`Submit for Review` -> Review, `Submit and Close` -> Closed) ->
  **Review** (`Submit for Approval` -> Approval, `Approve and Close` -> Closed, `Reject` -> Information Gathering) ->
  **Approval** (`Approve and Close` -> Closed, `Reject` -> Review) -> **Closed**.
- Hierarchy on 9.2.1: QuestionnaireTemplate and QuestionnaireAssessment are children of Program (among others), so the
  solution needs Program or another allowed parent in its hierarchy.
- During: create a **test program** with one test asset owned by a test user; answer per the spec's test case
  (dependencies: confirm hidden questions stay hidden). Check the variables render (`${asset.name}` etc.).
- After: `op.py qa <assessment id>` (assessment JSON: answers, scores), compare with `qr_score.py`; drive/inspect the
  workflow (`op.py wfi`, `test_run.py` transitions); confirm response-action and low-score objects exist under the asset
  (`op.py query`); reject → resubmit to prove *Skip if it exists*.
- Reports: Program Report, Single Assessment Report; *Export answers* (Excel) from review/approval/closed stages.

## Migration

- Templates: Export Configuration → *Questionnaire Templates* (brings section/subsection/question templates, dependencies,
  response actions) or Configuration Packaging. The workflow copy, custom model config, response-action target types and
  role templates are separate items: include them. Template ↔ object associations on questions are **not** migrated.
- Assessments (field data): FastMap. Answers: *Export answers* per assessment.
- Reporting: questionnaire object types are standard types; follow `reporting.md` (framework generation; no schema drop).

## Scoring formulas (IBM, 9.2.x)

Per question: single choice `QS = AS / max(AS) × 10`; multiple choice `QS = Σ selected AS / Σ all AS × 10`
(example: answers A10 B2 C1 D0, choose B+C, weight 1 → 3×10×1/13 = 2.31). `WQS = QS × QW`.
Subsection (total): simple `SSS = SSW × Σ WQS`; weighted average `SSS = SSW × Σ WQS / Σ QW` (average QS, 0 to 10).
Subsection (max): simple `MSSS = SSW × Σ (QW × 10)`; weighted average `MSSS = SSW × 10`.
Section `SS = SW × Σ SSS`; `TS = Σ SS`; `MS = Σ (SW × Σ MSSS)`; **Compliance** `CS = TS / MS × 100`; **Risk** `RS = MS − TS`.
Hidden, unscored-type, weight-0 and −1 answers are excluded.
Note: IBM's printed weighted-average and max formulas are inconsistent when weights ≠ 1 (as printed they could exceed
100%). `qr_score.py` uses the self-consistent reading above and treats unanswered questions as excluded. Calibrate once
against a live assessment and record the result in troubleshooting.md.

## From the User Guide (9.2.x, ch. 9 "Questionnaires", printed pp. 101-138; ch. 3-4)

Source: `docs/ibm/op_user_guide.pdf` (not in git). Confirms or corrects the notes above.

**Templates**
- *Create from copy* = Editor tab → **From template** tile → *Select questionnaire to copy* (p.104). A second copy in the
  same folder is copied from the first copy, so put each version copy in its own folder.
- No template preview is documented: check variables, links and display logic with a **test program** (pp.122, 124).
- Lock (p.105): launching locks the template; users with the right credentials can unlock, edit and re-lock, and "the
  changes take effect immediately". Observed 2026-10-21: an assessment already answered/closed kept its scores from the
  launch-time answer scores, so re-test with a new program after any change.
- Question types (pp.108-109): single, multiple, short text (252), long text (2048), table (30 rows x 15 cols, 50 chars),
  email, URL, user/group, user, group, date, decimal, integer, **object selector** (respondent picks related objects;
  needs Object being assessed, Relationship type, Object to associate; associating the picks needs the workflow
  operation *Associate questionnaire object selector responses*). Only single/multiple choice are scored.
- Per question: Required, Weight (0 excludes), Title (if enabled), Rationale (4000, not shown), Reference (URL, not
  shown), Show/require comments, Show/require attachments (a required attachment leaves the answer incomplete and
  **unscored** until added), Associations.
- Attribute-based display conditions: operators by field type (Currency/Date/Decimal/Integer: empty, equal, >, >=, <,
  <=, not empty, not equal; Enumerated string: does not match any, empty, equal, in, matches any, not empty, not equal,
  not in; Simple string: containing, empty, ends with, equal, matching regex, not containing, not empty, not equal, not
  matching regex, starts with; User/Group: empty, equal, in, in group, not empty, not equal, not in, not in group).
  Conditions on object types not related to the assessment are false. A field-based condition does not re-evaluate
  once the assessment is closed or read-only.

**Scoring (pp.102-104, 133)** - implemented by `qr_score.py`
- Single choice QS = AS / MAX(AS) x 10; multiple choice QS = SUM(selected AS) / SUM(all AS) x 10; any selected −1 answer
  makes the question ignored. WQS = QS x QW. Simple: SSS = SSW x SUM(WQS), MSSS = SSW x SUM(QW x 10). Weighted average:
  SSS = SSW x [SUM(WQS) / SUM(QW) x 10], MSSS = SSW x 10. SS = SW x SUM(SSS); CS = TS / MS x 100; RS = MS − TS.
- Hidden questions and text-type questions are excluded. "Low score" (reviewer filter) = question score 0-4.
- Scores update on every save (progress, compliance, risk visible to respondent and reviewer).

**Response actions (pp.114-121)**
- *Set field* values accept expressions: `[$TODAY$]`, `[$END_USER$]`, `[$System Fields:Description$]`. On create/copy,
  *self* is the assessment's **parent** (the asset); on set-fields of existing objects, *self* is the assessment.
- *New object name* is plain text: `${...}` variables are documented only for section/subsection descriptions and
  question/rationale text (p.122). The name is disabled when the type is auto-named (Settings:
  `Applications > GRCM > Auto Naming > <type>`, `Can be edited`).
- *Skip if it exists* prevents the reject → resubmit failure ("object already exists" blocks the submit) (p.117).
- Object names must be **unique within a folder** (ch. 4 p.65). A fixed name ("No remediation owner") for many assets
  can collide when their objects share a folder; with Skip if it exists the later asset's object may be skipped.
  Test two assets with the same answers; if it collides, switch the target type to auto-naming.
- Response actions ignore views: set every required field (p.118). Copy object supports one level of *Copy related
  child* (9.1.2+).

**Variables and links (pp.122-126)**: `${asset|program|questionnaireassessment|questionnairetemplate .id|.name|.description}`
and `.link`; fixed links `[text](https://...)`; Cognos links `[text](report://folderName=...&reportName=...&P=${program.id})`.
Content assist: type `/?` or `${`.

**Assessments, review, programs (pp.126-138)**
- Respondent = the asset's **primary owner** (employee account for Employee programs); no owner → no respondent.
- Copy answers (or program-level *Program to copy answers from*) matches questions by internal id: keep question
  identity across versions; a reworded question gets old answers.
- Review stage access: by default anyone who can edit the assessment can review; restrict with the Review stage's
  Access Control = Strict or Read (GRC Workflow stage property).
- Reject returns to Information Gathering; reviewers can flag, comment, re-flag. Emails are not sent if the assignee is
  unchanged, and not on close by default.
- Relaunch creates assessments only for newly added assets. To remove a wrongly created assessment, dissociate it from
  the asset. Launch status: program Task tab → Assessment Management → View (Process History).
- Ad hoc assessment: from the asset's Task tab, New assessment → lifecycle → Select Questionnaire Template.
- Launchers need Read on QuestionnaireAssessment and QuestionnaireTemplate; only program owners should delete assessments.
- AI answering (9.2.1): *Populate answers → Answer through AI*; files must be attached to the assessment or its primary
  parent; each AI answer gets an "answered by AI" comment (+ reasoning); needs *SOX > User Interfaces > Show AI Insights*.

**Workflow tasks (ch. 3 p.48)**: *Select an action to validate* in the user guidance panel shows key items and
validation errors for an action before running it - useful when a test transition fails with a validation error.
