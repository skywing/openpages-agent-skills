# Derive report: `TPRRemediation` from `SOXIssue`

- Source dump: `build/TPR/template/soxissue-op-config.xml`
- Loader: `build/TPR/types/tprremediation-op-config.xml` (ObjectManager prefix `tprremediation`)
- Label / plural: Remediation / Remediations
- Root folder: `/_op_sox/Project/Default/TPRRemediation`
- Field groups dropped from template: none

## Warnings (resolve before import)

- none

## Changes

- contentType <contentType> @name: `SOXIssue` → `TPRRemediation`
- contentType <contentType> @description: `OpenPages GRC Object Type` → `Remediation plan for a third-party issue`
- contentType <contentType> @rootFolder: `/_op_sox/Project/Default/Issue` → `/_op_sox/Project/Default/TPRRemediation`
- contentType @allowOverride → `true`
- contentType @suppliedByVendor: `true` → `false` (custom type; confirm ObjectManager validation accepts it)
- <dependencySet> <dependencySet> @objectType: `SOXIssue` → `TPRRemediation`
- <objectTypeString> <objectTypeString> @name: `SOXIssue` → `TPRRemediation`
- <objectTypeString> <objectTypeString> @singularValue: `Issue` → `Remediation`
- <objectTypeString> <objectTypeString> @pluralValue: `Issues` → `Remediations`
- <objectTypeString> <objectTypeString> @suppliedByVendor: `true` → `false`
- <resource> root folder `/_op_sox/Project/Default/Issue` → `/_op_sox/Project/Default/TPRRemediation` (creator/dates kept from template)

## Notes

- copied <dependencySet name=None> (renamed)
- copied <objectTypeString name='SOXIssue'> (renamed)
- kept the dump's System Admin Mode markers (true before the contentType, false after)

## Next steps

1. Review this report and the XML diff against the template.
2. Target env, SAM OFF (the loader toggles System Admin Mode itself): `ObjectManager.sh v c <user> <pw> <dir> <prefix>` (validate) → fix → `ObjectManager.sh l c ...` (load).
   Do NOT drop or re-create the reporting schema.
3. UI: add relationships, field groups/fields, profiles, views (see references/custom-object-type.md).
4. `op.py type <Type> --fields`, `verify_spec.py <spec>`; Object Prefix Z<n> + Generate reporting framework if reported on.