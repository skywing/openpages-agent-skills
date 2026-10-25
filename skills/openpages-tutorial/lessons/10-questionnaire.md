# Lesson 10 - Questionnaire: template, scoring, response actions, program

**Time:** 2 hours · **Changes OpenPages:** 1 template, 1 program, 3 assessments, 2 test Processes · **SAM:** not needed

## Objectives
- Know the built-in questionnaire framework (template → program → assessment) and where each piece is configured.
- Author a scored template with display logic and response actions.
- Predict the scores, launch a program, answer, and compare.
- Understand why the shared Questionnaire Assessment Workflow is not yours to edit.

## Concepts

**Built in, not custom.** `QuestionnaireTemplate` → `SectionTemplate` → `SubSectionTemplate` → `QuestionTemplate`;
`Program` launches one `QuestionnaireAssessment` per **asset** (Process, Vendor, Asset, Subprocess, Engagement,
Employee). The respondent is the asset's owner. You never create object types for questionnaires; you may create
**targets** of response actions, which you did: `PXKNException` is a child of Process.

**Scoring.** Only single and multiple choice are scored. Answer score -1..9999 (-1 = excluded), weights 0..9999.
Compliance score and risk score come from IBM's formulas; `qr_score.py` computes the expected values from the spec.

**Display logic.** q2 shows only when q1 = No. Hidden questions are not scored. Keep controlling and dependent questions
in the same subsection.

**Response actions** run when the assessment's workflow reaches an action that has the *Questionnaire response action*
operation. *Create object* makes a child of the asset (your exception under the Process), ignores views (so it sets
every field required at creation) and should have **Skip if it exists** (a reject → resubmit would otherwise fail on the
duplicate name). The created exception starts your workflow (auto start) in Draft.

**The workflow is shared.** Every program in the environment uses the one *Questionnaire Assessment Workflow*. A copy
cannot be routed to your template (assessments have no template field), and disabling the original moves everyone onto
the copy. The response-action operation runs whatever response actions each template defines, so once it is on the
workflow, every template's actions work. You check it is there; you do not add it. If it is missing, that is a shared
change for the environment owner.

**Templates lock** when a program launches them. Assessments keep the template as it was at launch; a new version is a
*Create from copy*.

## Do

1. Predict the scores:
   ```bash
   ./op qr_score.py specs/pxkn.yaml --detail
   ```
   Three cases: fully compliant 100/0, MFA gap 25/15, retention gap only 50/15. Change an answer score in the spec, re-run,
   and see how the formula reacts; then change it back.
2. Is the shared workflow ready? (read-only)
   ```bash
   ./op op.py wf --type QuestionnaireAssessment
   ```
   Look for the operation on Review > *Approve and Close*. Missing: ask the environment owner before going on.
3. Build checklist:
   ```bash
   ./op plan.py questionnaire specs/pxkn.yaml   # -> build/PXKN/QUESTIONNAIRE-PXKN-Process-Policy-Readiness.md
   ```
   Follow sections 1-3 and 6. **Skip section 4 (workflow)**: that is the shared change you do not make.
4. Template: Primary menu > Assessments > Questionnaire templates > New: name `PXKN Process Policy Readiness`, scoring
   Simple, owners = you, folder *Questionnaire Templates*. Editor > Blank > format settings > sections, subsections,
   questions (put the spec id `q1`... in each question's **Reference** field) > display logic for q2 > two response actions
   with **Skip if it exists** and the two set fields.
5. Two more test Processes under the same Business Entity, owned by you: `KN Tutorial Process B`, `KN Tutorial Process C`.
6. Program: Assessments > Programs > New: Assessment Questionnaire, owner/reviewer = you, your Business Entity,
   **3 Stage Lifecycle (with review)**, a due date > Select Questionnaire from Library > your template > Assets: your three
   Processes > **Launch**.
7. Answer: Process → case "fully compliant", B → "MFA gap, nothing compensating", C → "retention gap only". Submit for
   review; on one of them **Reject**, resubmit, then **Approve and Close** all three.
8. Compare:
   ```bash
   ./op op.py query "SELECT [Resource ID], [Name] FROM [QuestionnaireAssessment] WHERE [Name] LIKE 'KN Tutorial Process%'"
   ./op op.py qa <assessment id> --out runs/tutorial/KN/qa-a.json      # scores and answers
   ./op op.py query "SELECT [Resource ID], [Name], [PXKN-Exc:Status] FROM [PXKNException] WHERE [Name] LIKE 'KN %gap'"
   ```
   If your server rejects `LIKE`, open each Process's Assessments section in the UI for the ids instead.
   Expect `KN MFA gap` under Process B and `KN Retention gap` under Process C, each in Draft (your workflow started), and
   nothing created before *Approve and Close*.

## Check
```bash
./op tutorial check 10
```
Runs `qr_score` (expectations hold) and `verify_spec` with the questionnaire: template exists, asset and target types
are related, the shared workflow has the response-action operation on the stages the spec lists. A missing operation on
shared-dev is reported as an error: that is the environment owner's to fix, not yours.

## Pitfalls
- Launch fails with a save error: another enabled workflow with Auto Start on QuestionnaireAssessment exists (someone's
  copy). Tell the environment owner; do not disable anything yourself.
- Scores differ from `qr_score`: the template differs from the spec (an answer score, a weight), or the assessment was
  launched before you fixed the template (assessments keep their launch-time template).
- Response action created nothing: no operation on the action you closed with, a required field not set, or the target
  type is not a child of the asset type.
- Fixed object names must be unique within a folder: that is why each name starts with your code.

## Recap
1. Why must response actions set every required field?
2. Why do you not copy or edit the Questionnaire Assessment Workflow?
3. When do the exceptions appear, and why only then?
