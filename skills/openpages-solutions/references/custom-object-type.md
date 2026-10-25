# Creating a custom object type (9.2.x): template → derive → validate → import

IBM provides **no UI to create a new object type** in 9.2.x (the admin guide covers editing existing types only).
The supported route is to export an existing type as an ObjectManager loader file, derive the new type from it, and
import it back with ObjectManager or Import Configuration. Everything else (fields, relationships, profiles, views,
workflows) is then done in the UI.

Policy reminders: no SQL/DDL, no dropping or re-creating Db2 tables or the reporting schema (see `reporting.md`).

## 1. Choose the baseline (platform object types only)

Platform object types installed on every 9.2.x system: SOXBusEntity, SOXIssue, SOXTask, SOXDocument,
SOXExternalDocument, SOXSignature. Use one of these, not a solution type (ORM/RCM/TPRM...). Solution types carry
solution-specific field groups, relationships and settings that you would have to strip out.

| Baseline | Use it when the new type is... | Why / caveats |
|---|---|---|
| **SOXIssue** (Issue) *(default)* | a business record with its own lifecycle/workflow (assessment, remediation, exception, request) | Secondary type designed to associate with any primary type; standard form-based type |
| **SOXTask** (Issue Action Item) | a lightweight child item under another record (milestone, step, sub-task) | Simple child; small field set |
| SOXDocument (File) | a record whose main content is an uploaded file | File-upload type: dump with `configuration.manager.dump.file.upload.content.types=true`; file types come along |
| SOXExternalDocument (Link) | a record that is essentially a URL/reference | Shares the root storage folder with File for ACL purposes |
| ~~SOXBusEntity~~ | never | "Special" type with extra overhead; self-contained by default; security context point in the role-based model |
| ~~SOXSignature~~ | never | System sign-off mechanism |

Record the choice per type in the spec: `template: SOXIssue`.

## 2. Export the template (source = dev container)

```bash
cd <OP_HOME>/bin            # inside the container, or openpages-tools-client/bin
cp ObjectManager.properties ObjectManager.properties.bak
```
`ObjectManager.properties`: set to `true`
```
configuration.manager.dump.jsp.based.content.types=true       # SOXIssue / SOXTask (form/JSP-based types)
# configuration.manager.dump.file.upload.content.types=true   # only for SOXDocument-based types
configuration.manager.dump.bundle.types=true                  # so the script knows the template's field groups
```
`ObjectManagerExportFilters.xml` (next to `ObjectManager.sh`). The wrapper element must be the DTD's container for the
type's kind: `jspBasedContentTypes` (SOXIssue, SOXTask, most solution types) or `formBasedContentTypes`. A made-up
wrapper such as `<contentTypes>` is silently ignored and the dump contains only the DTD and a header (verified on 9.2.1).
Model it on `ObjectManagerExportFilters-Example.xml` (same folder):
```xml
<openpagesConfigurationBOM xmlFormatVersion="1.0">
  <jspBasedContentTypes>
    <contentType name="SOXIssue"/>
  </jspBasedContentTypes>
  <dependencies>
    <dependencySet objectType="SOXIssue"/>
  </dependencies>
</openpagesConfigurationBOM>
```
A good dump has `<contentType ...>` elements after the DTD (`grep -c "<contentType " file`); 0 means the filter matched nothing:
try `formBasedContentTypes`, or check the dump flags in `ObjectManager.properties`.
```bash
./ObjectManager.sh d c <adminUser> <password> /tmp/opx soxissue      # -> /tmp/opx/soxissue-op-config.xml
```
Restore `ObjectManager.properties.bak` afterwards. Copy the dump to `<project>/build/<KEY>/template/`. Commit it: it's the
version-specific reference for everything derived from it (the XML format version is in its root element: 1.31 on 9.2.1-89).

## 3. Derive the new type

```bash
./op derive_type.py \
  --dump build/TPR/template/soxissue-op-config.xml --baseline SOXIssue \
  --spec specs/tpr.yaml --type TPRRemediation
# -> build/TPR/types/tprremediation-op-config.xml
# -> build/TPR/types/tprremediation-derive-report.md
```
What the script changes: system name, label, plural label, description, root folder
(`/_op_sox/Project/Default/<Type>`), removes the template's own non-system field groups, copies other
name-referencing elements (e.g. object strings) renamed, adds `allowOverride="true"`. It does **not** copy relationships.
Exit code 1 means warnings: read the report. Typical warnings:
- numeric id attributes (environment-specific ids): decide keep/remove based on what ObjectManager validation says;
- leftover template labels in strings: fix by hand or set labels later in the UI;
- the new name must stay short (IBM best practice), letters/digits only, solution-key prefixed.

Verified against a real 9.2.1-89 dump (format 1.31): a SOXIssue dump is small (header, root-folder `<resource>`, one
`<contentType>`, `<dependencySet>`). The script keeps `jspPath` untouched, renames the root folder resource, sets
`suppliedByVendor="false"`, and keeps the dump's `<systemAdminMode>` markers. Labels/plural labels live in
`<objectStrings>`: include `<objectTypeString name="SOXIssue"/>` in the export filter, otherwise the derive report warns
and labels are set in the UI. The dump begins with a DOCTYPE/DTD that the derived loader does not carry; if ObjectManager
validation complains, prepend the dump's DOCTYPE block.

Always diff the output against the template dump (`diff_config.py template.xml new.xml`) and keep both in git.

## 4. Validate and import (target = dev container first)

1. Planned window. **Leave System Admin Mode OFF for a loader derived by `derive_type.py`.** It carries the dump's own
   `<systemAdminMode enabled="true"/>` / `false` markers, so ObjectManager switches SAM on for the content type and off
   again itself. Creating the root-folder resource fails if SAM is already on (verified 9.2.1: `OP-00008 ... "createCollection"
   cannot be executed in System Administration Mode`; the folder failure then cascades to 'Invalid rootFolderPath',
   'objectType does not exist' and 'Object Type does not exist' validation errors, and nothing is created). Turn SAM on by
   hand only for UI work (relationships, fields) or for a loader without those markers.
2. Validate: `./ObjectManager.sh v c <user> <pw> <dir> tprremediation`, or Import Configuration → **Validate**
   (file must be named `<prefix>-op-config.xml`). Fix every error; re-derive rather than hand-patching when possible.
   How to read the result (verified on 9.2.1-89): ObjectManager is a REST client; the client log is terse. A clean run
   shows `Validation Process (<prefix>): Completed`, `STATUS_FINISHED_SUCCESS` and exit code 0, with no per-object lines.
   A bad file shows `(line, col) Processing '<element>', Attribute: '<name>', Value: '<v>' is invalid. Should be one of: ...`,
   `Completed with validation errors`, `STATUS_FINISHED_ERROR` and exit code 1. Validation checks element/attribute
   values against the DTD and enums (e.g. contentType `category` is one of System, Master, Compliance, Secondary
   Compliance, Custom Form, Viz Diagram); it does not prove the load will succeed. Run a negative control once per
   environment (break one attribute, validate under a throwaway prefix) so a pass means something. Use the exit code in scripts.
3. Load: `./ObjectManager.sh l c <user> <pw> <dir> tprremediation`, or Import Configuration → **Import**.
   Check `ObjectManager.log` / the History tab: `Total Validation Errors: 0`, `Total Exceptions: 0`.
4. Do **not** drop or re-create the reporting schema (IBM's ObjectManager Db2 note says to; policy says no, and IBM's
   reporting table says a new object type needs only a framework generation). If the load fails or locks: stop,
   collect the log and trace ids, escalate.
5. Disable System Admin Mode.

## 5. Finish in the UI (see object-model.md, views.md)

1. SAM on: Object Types > the new type > **Relationships > New Relationship** (primary parent first, then children).
   Then **Fields > New Field** for the solution field groups/fields from the spec. SAM off.
2. Editing object type properties: description, Title component, Global Search.
3. Profiles: include the type and its fields.
4. Views: copy the system Task/Grid/Creation views for the new type if generated; otherwise copy the template type's
   system views and change the object type. Publish.
5. Primary menu: add the type to a submenu (Settings > Applications > Common > Configuration, hidden settings).
6. Reporting (optional): Object Prefix `TPRREMEDIATION=Z<letter>` + Generate reporting framework.

## 6. Verify

```bash
./op op.py type TPRRemediation --fields     # exists, system fields present, no template field groups
./op op.py rels TPRRemediation              # relationships as designed
./op verify_spec.py specs/tpr.yaml          # 0 errors
./op test_run.py specs/tpr.yaml --apply --cleanup
```

## 7. Promote to other environments

Don't re-run the derivation per environment. Promote the **finished type from dev** (type + field groups +
relationships + profiles + views) with Configuration Packaging or Export/Import Configuration (`packaging.md`).
The derived loader and derive report stay in git as the design record.

## Rollback in dev

A loaded type can't simply be deleted: removing object types requires a reporting schema re-create (out of policy).
Rename (label only) and disable its relationships/profile inclusion, or restore the dev container from backup.
So validate thoroughly before loading, and never load an unreviewed derivation.


## Generating fields and profile inclusion (`gen_fields.py`)

Built from a live 9.2.1 reference dump of the finished TPR types (2026-10-22, `build/TPR/reference/`).

```bash
./op gen_fields.py specs/<key>.yaml --compare build/<KEY>/reference/<dump>.xml    # drift: must be 0 differences
./op gen_fields.py specs/<key>.yaml --reference build/<KEY>/reference/<dump>.xml  # -> build/<KEY>/fields/<key>-fields-op-config.xml
```

- Covers `object_types[].field_groups` and `type_extensions[].field_groups`, enum values (value = 1..n in spec order,
  enum default = that number), field labels (`objectStrings`) and inclusion in the spec's `profiles`
  (`objectProfiles explicitListing="false"`: listed entries are added/updated, others untouched).
  The 9.2.1 validator **requires `displayOrder` on every `includedObjectType`** ("Attribute: 'displayOrder', Value:
  Not provided!" fails validation): the generator copies it from the reference dump, or assigns max+1 for a type new to
  the profile, so always pass `--reference`.
- Confirmed encodings: enum (Enumerated String/List), integer, date, currency (USD default), long_string
  (Long String, dataLength Medium, Text Area), user_group (Simple String + User/Group Selector, starting group
  OpenPagesApplicationUsers), boolean (default false). multi_enum, decimal, simple/medium string, business entity are
  **refused** until an existing field of that type has been dumped.
- Reporting columns are server-assigned: `--reference` reuses the live name (Finding's `Source` became `source00`).
  On a new field of an existing type, check the validate output for a column collision.
- Spec keys it reads per field: `type, required, values, default, description, min, max, search, label, guidance,
  currency, length, starting_group, read_only`.
- Load like the derived type file: SAM **off** (the file carries its own markers), `v c` then `l c`, prefix
  `<key>-fields`. Then re-dump and `--compare` again.

### Relationships (`--relationships <dump>`)

- Dump them separately: ObjectManager.properties with every `configuration.manager.dump.*` option false except
  `content.type.relationship.sets=true`, and **no** filter file (restore both afterwards). 9.2.1: 954 relationships in
  3 sets; IBM's are in **SOX Object Model**, everything added in the UI is in **SOX Extended Object Model**
  (inheritsFrom SOX Object Model). `SOX Current` was empty.
- Encoding: `contentTypeRelationship parent child type=Association enabled minParents maxParents minChildren maxChildren`
  (unlimited = 2147483647). Spec: `object_types[].parents` (`max_parents`, `min_parents`), `children`, top-level
  `relationships`.
- The generator writes the UI set **in full** (existing members, including other teams', plus the spec's) because it is
  not known whether a load merges into or replaces a set's members. Relationships already provided by the IBM set are
  not written. Keep the pre-load relationship dump: re-loading it is the rollback.
- `--compare ... --relationships <dump>` checks presence, enabled and min/max parents (an unset `max_parents` means
  unlimited, so a UI limit like Finding -> TPRRemediation maxParents=1 shows as a DIFF until the spec records it).
