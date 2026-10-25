# Lesson 05 - Field groups and field types

**Time:** 60-90 min · **Changes OpenPages:** two field groups, 17 fields (permanent), profile entries · **SAM:** loader-toggled, then on for about 10 minutes

## Objectives
- Know the OpenPages field types and when to use each.
- Generate field groups and fields from the spec, validate and load them.
- Build fields by hand in the UI for types the generator does not know yet, and see how they are encoded.
- Prove spec and environment match: 0 differences.

## Concepts

| Spec type | OpenPages data type / display | Use for | In this solution |
|---|---|---|---|
| `enum` | Enumerated String, single select | status, ratings (values in order; default) | Status, Risk Rating, Effectiveness |
| `multi_enum` | Enumerated String, multi-select | tags, categories | Exception Category (**by hand**) |
| `boolean` | Boolean | yes/no | Renewal Requested |
| `integer` | Integer (min/max) | counts, percentages | Coverage Percent, calculated counts |
| `decimal` | Float | scores with decimals | Inherent Risk Score (**by hand**) |
| `currency` | Currency (default USD) | money, converted with exchange rates | Estimated Exposure |
| `date` | Date | deadlines; stored as an instant (time zone!) | Requested Expiry |
| `long_string` | Long String, text area | free text | Justification, Control Description |
| `simple_string` / `medium_string` | short text | codes, references | (optional, your own field) |
| `user_group` | Simple String + User/Group Selector | owners, assignees | Exception Owner |

**Field groups** bundle fields of one type (`PXKN-Exc`, `PXKN-Ctl`). A field group belongs to one object type.

**Generated vs by hand.** `gen_fields.py` writes an ObjectManager loader from the spec using **encodings confirmed from
a live 9.2.1 dump** (enum, integer, date, currency, long_string, user_group, boolean). Other types are *refused* (skipped
with an error line) until someone confirms their encoding from a real dump. You will be that someone for `multi_enum`
and `decimal`: build them by hand, dump, and read how OpenPages stored them.

**Profiles.** A field is visible only if the object type and field are included in the user's **profile**. The
generated loader adds your types and fields to the profiles listed in the spec (`explicitListing="false"`: listed
entries are added, others are untouched).

## Do

### 1. Fresh reference dump of your types (read-only)
```bash
./om dump reference --env shared-dev --filter build/PXKN/template/ObjectManagerExportFilters-PXKN-reference.xml \
     --out build/PXKN/reference --prefix pxkn-reference
```

### 2. Generate
```bash
./op gen_fields.py specs/pxkn.yaml --reference build/PXKN/reference/pxkn-reference-op-config.xml
#  -> build/PXKN/fields/pxkn-fields-op-config.xml  and  pxkn-fields-report.md
```
Read the report: 15 fields generated (more if you added one in lesson 02), 2 skipped (`Exception Category` multi_enum, `Inherent Risk Score` decimal). Open the
XML and find one enum field: values are stored as numbers 1..n in spec order; the labels are in `objectStrings`.

### 3. Validate, then load (SAM OFF: the file switches it)
```bash
./om validate build/PXKN/fields pxkn-fields --env shared-dev
./om load     build/PXKN/fields pxkn-fields --env shared-dev
```
A column-name collision message on validate means a reporting column already exists; read it before loading.

### 4. The two fields by hand (SAM on, tell your team)
SAM on → Object Types > *KN Policy Exception* > Fields > New Field, field group `PXKN-Exc`:
- `Exception Category`: Enumerated String, **multi-valued**, values Access, Configuration, Data Retention, Vendor, Other.
- `Inherent Risk Score`: Float (decimal), min 0, max 10.
Include both in the profile (`OpenPages Modules Master`, or the one your spec lists). SAM off.

### 5. Read the encoding you just created
```bash
./om dump reference --env shared-dev --filter build/PXKN/template/ObjectManagerExportFilters-PXKN-reference.xml \
     --out build/PXKN/reference --prefix pxkn-reference
```
In `pxkn-reference-op-config.xml` find the two fields' XML and compare them with an enum and an integer field. Note the
attributes that differ (data type, multi-value flag, display type). This is how an encoding gets confirmed; send your
notes to the skill maintainer (do not edit `gen_fields.py` yourself).

### 6. Prove it
```bash
./op gen_fields.py specs/pxkn.yaml --compare build/PXKN/reference/pxkn-reference-op-config.xml \
     --relationships build/PXKN/reference/shared-dev-relationships-op-config.xml
./op op.py type PXKNException --fields
```
The compare should show 0 differences for the generated fields (the hand-built ones are reported as not generated).

## Check
```bash
./op tutorial check 5
```
`verify_spec` against types, relationships and fields: every field exists with the right data type.

## Pitfalls
- A field added with the wrong type cannot be changed later (only a new field). Check type and name before saving.
- Converting an enum from single to multi-value later needs SAM and a reporting schema *update*; decide now.
- `user_group` fields need a starting group; the generator uses `OpenPagesApplicationUsers`.
- Date fields: OpenPages stores an instant. A bare `2026-12-31` sent as UTC midnight shows as 30 Dec in New York; the
  tooling sends midnight in the environment's `timezone` instead (lesson 09 tests this).
- Profile import is one of the changes that needs a reporting **schema update** (lesson 11): note it for the owner.

## Recap
1. Which field types can the generator build today, and why not the others?
2. How is an enum's value stored, and where do its labels live?
3. What does `explicitListing="false"` protect in a shared profile?
