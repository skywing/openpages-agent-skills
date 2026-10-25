# Field generation report: Third-Party Remediation Tracker (TPR)

## Output

- `tpr-fields-op-config.xml`: 3 field groups, 13 fields, profiles: OpenPages Modules Master

## Load (human-run)

1. Review this report and the XML. 2. `ObjectManager.sh v c <user> <pw> <dir> tpr-fields` (validate).
3. `ObjectManager.sh l c <user> <pw> <dir> tpr-fields` in a maintenance window (SAM toggled by the file).
4. `verify_spec.py <spec>` and `gen_fields.py <spec> --compare <new dump>` must both be clean.
Never drop or re-create the reporting schema; no SQL/DDL.

## Relationships

- 2 relationship(s) already in 'SOX Extended Object Model' kept unchanged (not from this spec): SOXBusEntity->SeleniumSurvey (Association), SOXBusEntity->SeleniumSurvey (Attachment)
- `tpr-relationships-op-config.xml`: set 'SOX Extended Object Model' written in FULL (5 relationships: existing members kept, spec relationships added/updated), so a loader that replaces set members loses nothing.
- Load separately: `v c ... tpr-relationships`, then `l c`. Rollback = re-load the relationship dump taken before (keep it).
