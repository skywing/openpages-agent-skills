# Lesson 04 - Relationships: parents, children, links to IBM types

**Time:** 30-45 min · **Changes OpenPages:** three relationships · **SAM:** on for about 10 minutes

## Objectives
- Add relationships in the admin UI and understand primary parent, min/max parents.
- Link a custom type to IBM types (Process, Policy).
- Prove the result with a relationship dump and the generator's compare mode.

## Concepts

**A relationship** says type A may be a parent of type B. Each relationship has min/max parents and children
(unlimited = 2147483647). The spec writes parents on the child type:
```yaml
- name: PXKNException
  parents:
    - { type: SOXProcess, primary: true, max_parents: 1 }   # exactly one process
    - { type: Policy }                                       # optional link
```
`primary: true` is a design statement (which parent the creation view and the REST scripts use); OpenPages itself
stores the primary parent per object, not per relationship.

**Where relationships live.** IBM's relationships are in the set *SOX Object Model*; everything added in the UI goes to
*SOX Extended Object Model*. `gen_fields.py --relationships` can generate that set, but it writes the **whole** set
(including other people's relationships) because it is not known whether a load merges or replaces. In a shared
environment someone else may add a relationship between your dump and your load, so **in shared-dev you add
relationships in the UI** and use the generator only to compare.

**Circular relationships** are blocked in 9.2.x. 9.2.1 shows an impact analysis before you disable or delete one.

## Do

### 1. SAM on (tell your team first)
Administration menu > System Admin Mode > **Enable**.

### 2. Add the relationships
Administration menu > Solution Configuration > Object Types > **KN Policy Exception** > Relationships > New Relationship:
1. Parent `Process` (SOXProcess) → child `KN Policy Exception`; max parents 1.
2. Parent `Policy` → child `KN Policy Exception`.

Then Object Types > **KN Compensating Control** > Relationships > New Relationship:
3. Parent `KN Policy Exception` → child `KN Compensating Control`.

### 3. SAM off
Administration menu > System Admin Mode > **Disable**. Do it now, before reading on.

### 4. Look and compare (read-only)
```bash
./op op.py rels PXKNException
./om dump relationships --env shared-dev --out build/PXKN/reference          # -> shared-dev-relationships-op-config.xml
./om dump reference --env shared-dev --filter build/PXKN/template/ObjectManagerExportFilters-PXKN-reference.xml \
     --out build/PXKN/reference --prefix pxkn-reference
./op gen_fields.py specs/pxkn.yaml --compare build/PXKN/reference/pxkn-reference-op-config.xml \
     --relationships build/PXKN/reference/shared-dev-relationships-op-config.xml
```
The compare report (`build/PXKN/fields/*compare*.md`) shows relationship rows as OK, and fields as missing: those come in
lesson 05. Open the relationship dump and find your three `contentTypeRelationship` elements.

## Check
```bash
./op tutorial check 4
```
Runs `verify_spec` against your types and relationships only (fields come next lesson).

## Pitfalls
- The relationship is added on the **child** type's Relationships tab in this tutorial's steps; check which side the
  dialog asks for and read the parent/child labels before saving.
- `max_parents: 1` in the spec but unlimited in the UI shows as a DIFF in the compare: fix the UI or the spec.
- Forgot to turn SAM off: every other user is locked out. Check `./op op.py ping`.

## Recap
1. Why does the tutorial add relationships in the UI instead of loading the generated set?
2. What does `max_parents: 1` enforce?
3. Which set contains relationships you add in the UI?
