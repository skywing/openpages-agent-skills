# Derive report: `TPRMilestone` from `SOXTask`

- Source dump: `build/TPR/template/soxtask-op-config.xml`
- Loader: `build/TPR/types/tprmilestone-op-config.xml` (ObjectManager prefix `tprmilestone`)
- Label / plural: Milestone / Milestones
- Root folder: `/_op_sox/Project/Default/TPRMilestone`
- Field groups dropped from template: none

## Warnings (resolve before import)

- none

## Changes

- contentType <contentType> @name: `SOXTask` → `TPRMilestone`
- contentType <contentType> @description: `OpenPages GRC Object Type` → `Milestone`
- contentType <contentType> @rootFolder: `/_op_sox/Project/Default/IssueActionItems` → `/_op_sox/Project/Default/TPRMilestone`
- contentType @allowOverride → `true`
- contentType @suppliedByVendor: `true` → `false` (custom type; confirm ObjectManager validation accepts it)
- <dependencySet> <dependencySet> @objectType: `SOXTask` → `TPRMilestone`
- <objectTypeString> <objectTypeString> @name: `SOXTask` → `TPRMilestone`
- <objectTypeString> <objectTypeString> @singularValue: `Action Item` → `Milestone`
- <objectTypeString> <objectTypeString> @pluralValue: `Action Items` → `Milestones`
- <objectTypeString> <objectTypeString> @suppliedByVendor: `true` → `false`
- <resource> root folder `/_op_sox/Project/Default/IssueActionItems` → `/_op_sox/Project/Default/TPRMilestone` (creator/dates kept from template)

## Notes

- copied <dependencySet name=None> (renamed)
- copied <objectTypeString name='SOXTask'> (renamed)
- kept the dump's System Admin Mode markers (true before the contentType, false after)

## Next steps

1. Review this report and the XML diff against the template.
2. Target env, SAM OFF (the loader toggles System Admin Mode itself): `ObjectManager.sh v c <user> <pw> <dir> <prefix>` (validate) → fix → `ObjectManager.sh l c ...` (load).
   Do NOT drop or re-create the reporting schema.
3. UI: add relationships, field groups/fields, profiles, views (see references/custom-object-type.md).
4. `op.py type <Type> --fields`, `verify_spec.py <spec>`; Object Prefix Z<n> + Generate reporting framework if reported on.