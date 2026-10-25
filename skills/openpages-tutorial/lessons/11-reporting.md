# Lesson 11 - Reporting framework: what a change requires

**Time:** 20 min · **Changes OpenPages:** no (reading lesson)

## Objectives
- Tell the reporting **schema** from the reporting **framework**.
- Know which action each kind of change needs, and which actions are out of policy.

## Concepts

- **Reporting schema (RPS):** reporting tables and views in the OpenPages database, maintained by OpenPages. Actions:
  *Update* (incremental), *Create/Re-Create* (re-create drops then rebuilds), *Drop*.
- **Reporting framework (RPF):** the Cognos models generated from the schema. Action: *Generate / Update*.

| Change | Re-create schema | Update schema | Generate framework |
|---|---|---|---|
| New object type | no | no | yes |
| New field | no | no | yes |
| New relationship | no | no | yes |
| **Import a profile** (ObjectManager, Import Configuration) | no | **yes** | no |
| Remove an object type or field | **yes (out of policy)** | no | yes |

Your solution added types, fields, relationships (→ framework generation) and loaded profile entries with ObjectManager
in lesson 05 (→ schema update). A new type also needs an **Object Prefix** for the framework
(`PXKNEXCEPTION=Z<letter>`).

**Policy:** never re-create or drop the reporting schema, never run SQL. Removal needs a re-create, which is why the
tutorial disables instead of deleting. In a shared environment, schema updates and framework generation affect everyone
and take time: they are the environment owner's call, in a planned window.

## Do
1. Read `skills/openpages-solutions/references/reporting.md`.
2. Look at the reporting section of `build/PXKN/BUILD.md`.
3. Write down for your solution: which actions are needed, who runs them, and what you would ask the environment owner.

## Check
```bash
./op tutorial check 11           # self-check, then --confirm
```

## Recap
1. Which of your changes needs a schema *update*, and why?
2. Why is deleting a field out of policy?
