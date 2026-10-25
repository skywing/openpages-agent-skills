# Lesson 12 - Packaging and promotion runbook

**Time:** 45 min · **Changes OpenPages:** no

## Objectives
- Know what moves between environments with which tool, and what does not move at all.
- Read a layered deployment runbook generated from the spec.

## Concepts

| Moves with | Carries |
|---|---|
| **Configuration Packaging** (9.2.0+; REST in 9.2.1) | object types (with field groups, fields, relationships, filters), profiles (views + types), workflows (email templates only), questionnaire templates; dependency validation and diffs |
| Export / Import Configuration | the same categories, file based |
| ObjectManager | anything dumpable, as XML; diffable in git |
| FastMap | data, not configuration (never questionnaire templates) |

**Not migrated:** business entities, groups, reports, JSPs, triggers, namespaces, secrets. Calculations carry nothing
referenced; workflows do not carry the views or types they use. Both sides must be on the same version and fix pack.

**Layers.** A solution deploys in order: object model (types, fields, relationships) → profiles and views → filters →
calculations → workflows → questionnaire template → verification. Each layer has its own rollback; type and field
removal has none (lesson 11), so the target gets a **snapshot** first, and generated loaders are regenerated from the
**target's own dumps** (column names and display orders differ per environment).

**Shared changes** (an IBM workflow, another team's profile) are recorded edits with a reason and an approver, not
package content.

## Do
```bash
./op plan.py package specs/pxkn.yaml        # -> build/PXKN/PACKAGE.md + ObjectManager filters
```
Read `PACKAGE.md` top to bottom and answer:
1. Which layer would you deploy first and why?
2. What do you snapshot in the target before starting?
3. Which items are NOT in the package and how do they get to the target?
4. What is the rollback for the workflow layer, and why is there none for fields?

Your solution is never promoted out of shared-dev; this is the practice run.

## Check
```bash
./op tutorial check 12
```

## Recap
1. Why are loaders regenerated from the target's dumps instead of copied from dev?
2. Name three things that Configuration Packaging does not migrate.
