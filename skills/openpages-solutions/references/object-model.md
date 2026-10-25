# Custom object types, fields, relationships (9.2.x)

Menu: **Open Administration menu > Solution Configuration > Object Types** (needs the *Object Types* application permission).

## Design rules before you build

1. **System names are permanent.** Object type name, field group name and field name cannot be renamed; only labels
   can. Settle them in the spec first.
2. **Prefix everything** with a solution key (`TPR...`, `TPR-Rem`). This avoids collisions with IBM solution types
   (`SOXIssue`, `SOXBusEntity`...), makes packaging filters trivial, and keeps `dump_schema.py --only TPR` clean.
3. **Short type names.** IBM has a known issue where long object type names with a similar beginning cause problems.
4. **Name charset**: field groups and fields must start with a letter; letters, digits, spaces, `-`, `_` only.
   Object type system names: letters and digits.
5. **Do not use these field labels** (they break FastMap import/export): `Delete`, `Parent Path`, `Parent Object Types`,
   `Parent Objects`, `Folder Path`, `Tags`.
6. **Keep field counts lean.** The reporting schema SQL is limited to 32,000 characters; many enum and currency fields
   blow it. Run the *Schema Analysis report* before adding fields to a crowded type, or exclude fields from the
   reporting schema.
7. **Every object needs a primary parent** in practice (Creation Views must let users pick one). Design the
   parent chain explicitly: which type is the primary parent, which are secondary associations.
8. **Avoid circular relationships.** 9.2.0 validates and blocks them; disable the conflicting relationship first.
9. Delete unused relationships (IBM best practice: eliminate unused object type relationships). 9.2.1 shows an
   impact analysis (calculations, views, reports, existing objects) before you disable or delete one.

## Database policy

All changes go through OpenPages itself (admin UI, ObjectManager, Import Configuration, Configuration Packaging,
REST). **No SQL/DDL against the OpenPages database, and no dropping or recreating Db2 tables or the reporting
schema**, even where an IBM procedure lists it. Skip such a step, flag it, and escalate if the operation fails.

## System Admin Mode (SAM)

Required for: object model hierarchy changes, creating/modifying object types, field groups and fields, converting
an enum from single to multi-value, field-level security, reporting schema create/drop/refresh (schema drop is
out of scope for this skill: see Database policy).
Not required for views, workflows, profiles, filters (but you may enable it to keep users out).
While SAM is on, only users with *System Administration Mode* permission can log in, and all writes except metadata
changes are blocked. **Export Configuration fails while SAM is on.** Toggle: admin menu or `PUT /v2/configuration/admin_mode?enable=`.
9.2.0 adds *System Maintenance Mode (SMM)* for maintenance windows by user group; it complements SAM rather than replacing it.

## Build order in the UI

1. SAM on.
2. Object type:
   - **Existing type** (IBM or previously added): open it from the Object Types list.
   - **New type**: no UI exists in 9.2.x. Derive it from a platform object type dump and import it:
     follow `custom-object-type.md` (template choice, `derive_type.py`, validate/load, relationships in the UI).
     Then set labels, description and the **Title** component (Editing object type properties).
   - For Cognos reporting on the new type: add it to `Platform > Reporting Framework V6 > Configuration > Object Prefix`
     with a unique `Z<letter>` prefix, then generate the reporting framework (Cognos Analytics > Reporting Framework
     Generation). Per IBM's change table, adding types, fields and associations needs **no** schema re-create or update.
     See `reporting.md`.
3. Fields section → **New Field** → Field Group → **New** (creates the group), then add fields:
   Name (immutable), Label (localizable), Description, Data Type, Required, Global Search, ranges/colors
   (integer/decimal/currency/enum), Default Value, and **Profiles** (defaults to every profile the type belongs to).
4. Relationships section → Parents / Children → **New Relationship** → pick type; enable; optionally **Single parent max**.
5. SAM off.
6. Profiles: include the type and fields; set required/optional per profile. (Changes to assignments are best made
   from the profile, not the object type page.)
7. Filters, field dependencies, dependent picklists on the type page as needed.
8. **Validate computed fields** button on the type page if you added computed fields.

Data types (UI): Boolean, Business Entity Selector, Classifier, Currency, Date, Decimal, Enumerated String (single/multi),
Integer, Long String, Reporting Fragment, Simple String, User/Group. Display type is defined per field on the object type.
Date fields render in the user's time zone since 9.2.0 (timestamp fields differ).

## Config as code: ObjectManager loader XML

Object types, field groups, fields, relationships, profiles, views, filters, workflows can also be **loaded** from an
ObjectManager XML file (`<prefix>-op-config.xml`, root `<openpagesConfiguration xmlFormatVersion="...">`), with
`ObjectManager.sh l c <user> <pw> <dir> <prefix>` or Import Configuration.

Rule: **never write loader XML from memory.** Build one reference type in the UI, dump it
(`ObjectManager.sh d c ...` with filters, see packaging.md) and use that dump as the template.
IBM's ObjectManager topics say that on Db2 the reporting schema should be dropped before loading metadata (types,
fields, relationships) and re-created after. **Per project policy we do not drop it** (and IBM's reporting-schema change
table lists these additions as needing only a framework generation): validate first (`v c`), load in a quiet
window with SAM on, and if the load fails or locks, stop and escalate with `ObjectManager.log`. Elements/attributes
differ by `xmlFormatVersion`. When re-importing a changed object type, set `allowOverride="true"` on `contentType`
so attributes like `titleEnabled`, `searchEnabled` update.

## Verifying

`dump_schema.py --only <KEY>` then `verify_spec.py <spec>`. Type definitions from `GET /types/{name}` return
`field_definitions[]` with `name` (`Group:Field`), `data_type`, `required`, `computed`, `read_only`, `enum_values[]`
(`name`, `localized_label`, `hidden`, `parent_id`), `dependencies[]`, and `GET /types/{name}/associations` returns
`{name, relationship: Parent|Child, min, max, is_enabled, association_definition_id}`.
