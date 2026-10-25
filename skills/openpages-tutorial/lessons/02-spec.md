# Lesson 02 - Design the spec: names that last forever

**Time:** 45 min · **Changes OpenPages:** no

## Objectives
- Read a solution spec and know what each section drives.
- Understand which names are permanent and which can change later.
- Lint the spec and make sure your key is free in shared-dev.

## Concepts

**The spec is the single source of truth.** Open `specs/pxkn.yaml` (your code). Its sections, in build order:

| Section | Built in | Read by |
|---|---|---|
| `solution` (name, `key`, owner) | - | every script |
| `object_types` (name, template, label, parents, children, field_groups) | 03, 04, 05 | derive_type, gen_fields, verify_spec |
| `profiles` | 05, 06 | gen_fields, plan |
| `filters`, `views` | 06 | plan (UI checklist) |
| `calculations` | 07 | verify_spec (lint), plan |
| `workflows` | 08 | plan, verify_spec, test_run |
| `tests` (fixtures, scenarios) | 09 | test_run |
| `questionnaires` | 10 | plan, qr_score, verify_spec |

**Permanent vs changeable.**

| Permanent once built | Changeable |
|---|---|
| object type system name (`PXKNException`) | labels, plural labels, descriptions |
| field group name (`PXKN-Exc`) | field labels, help text, required flag, defaults |
| field name and data type (`Status`, enum) | enum *labels*, adding enum values |
| | views, filters, workflows, calculations, questionnaires (versioned or editable) |

Removing a type or field needs a reporting-schema re-create, which is out of policy. So **design with disable, not
delete**, and get names right now.

**Naming rules.** Object type names: letters and digits, starting with a letter, short (IBM notes problems with long
names that start alike). Field groups and fields: start with a letter; letters, digits, spaces, `-`, `_`. Never use the
field labels `Delete`, `Parent Path`, `Parent Objects`, `Parent Object Types`, `Folder Path`, `Tags` (they break
FastMap). In this tutorial everything also carries your code (lesson 00).

**Templates.** OpenPages 9.2.x has no UI to create an object type. You copy a *platform* type: `SOXIssue` for a business
record with its own lifecycle, `SOXTask` for a light child item. That is what `template:` says.

## Do

1. Read your spec top to bottom with the table above. Find: the two object types and their templates; the primary
   parent of each; the field that the questionnaire sets; the two calculations and their types.
2. Make one small design change of your own so the spec is yours, for example add a value to
   `PXKN-Exc:Exception Category`, or a field `Ticket Reference` (type `long_string`) to `PXKN-Ctl`. Keep the prefix rules.
   Re-read every system name: after lesson 05 they cannot change.
3. Lint:
   ```bash
   ./op verify_spec.py specs/pxkn.yaml --lint-only
   ```
4. Generate the build checklist and skim it (this is what lessons 03-08 do):
   ```bash
   ./op plan.py build specs/pxkn.yaml      # -> build/PXKN/BUILD.md
   ```

## Check
```bash
./op tutorial check 2
```
Passes when the lint has 0 errors, every name carries your code, and no object type in shared-dev already starts with
your key (another learner with the same initials).

## Pitfalls
- A YAML indentation error shows as a parse error with a line number: fix indentation with spaces, never tabs.
- Required at creation vs required to progress: `Justification` is *not* `required: true` because the questionnaire
  (lesson 10) creates exceptions without it; the workflow's Submit validation requires it instead. Decide this per field.
- `BUILD.md` lists steps for a dedicated dev container. In shared-dev follow the lessons: they tell you when SAM is needed
  and when the generated files replace UI steps.

## Recap
1. Which three kinds of names can never change?
2. Why is `Justification` validated by the workflow instead of being required?
3. Why does the tutorial copy SOXIssue instead of a solution type like Finding?
