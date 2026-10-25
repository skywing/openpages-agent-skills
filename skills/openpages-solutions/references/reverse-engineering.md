# Reverse-engineering an existing solution into a spec (brownfield)

Use when a solution was built in an environment without this tooling (objects, fields, relationships, views, workflows,
filters, calculations already exist) and you want it under spec control. Everything here is **read-only** and safe on
production (`tier: prod` is write-blocked anyway). Tool: `scripts/reverse_spec.py`. Proven on TPR (2026-10-23): the
reversed spec matched the live dumps (gen_fields `--compare`: 0 differences) and the hand-written spec field for field.

## 1. Capture (read-only), SAM off

Two ObjectManager dumps and one REST snapshot of the source environment, all read-only:

```bash
./om dump custom        --env <env> --out build/_reverse/<env>   # -> <env>-custom-op-config.xml
./om dump relationships --env <env> --out build/_reverse/<env>   # -> <env>-relationships-op-config.xml
./op dump_schema.py     --env <env>                              # -> schema/<env>/ (workflow stages/actions, creation dates)
```

**A. custom** has no filter and turns on only: jsp/form/file-upload content types, bundle types, object strings, object
profiles, query definitions, responsive and dashboard views, process definitions, calculations (tbcalculations) and
rules (tbrules). It contains IBM's items too (`suppliedByVendor="true"`); the inventory filters them. It can be large
(tens of MB).

**B. relationships** turns on only `content.type.relationship.sets`, no filter.

`./om` builds these option sets in a temporary copy of the client, so the client's own `ObjectManager.properties` and
filter file are never changed (see `packaging.md`, "`./om`"). Running ObjectManager.sh by hand: set the same options,
and back up and restore both files around each dump.

## 2. Inventory

```bash
./op reverse_spec.py inventory --dump build/_reverse/<env>/<env>-custom-op-config.xml \
     --dump build/_reverse/<env>/<env>-relationships-op-config.xml --schema schema/<env>
```
-> `build/_reverse/INVENTORY.md` + `build/_reverse/selection.yaml`.

How "not IBM" is decided: `suppliedByVendor="false"` on content types, field groups, filters, responsive and dashboard
views; relationships in the **SOX Extended Object Model** set; workflows on custom types, or on IBM types when REST
`created_on` is after the install date; calculations/rules on custom types (others listed for review).
Suggested solutions = custom types connected by relationships or sharing a name prefix; field groups on IBM types,
shared-type relationships, filters, views, workflows and calculations are attached by object type or prefix, the rest
goes to `unassigned`.

**Edit `selection.yaml`**: set each solution's `key` and `name`; move items in from `unassigned` (or out); delete
other teams' items. This is the human decision of what the solution is.

## 3. Spec draft

```bash
./op reverse_spec.py spec --selection build/_reverse/selection.yaml --key <KEY> \
     --dump build/_reverse/<env>/<env>-custom-op-config.xml --dump build/_reverse/<env>/<env>-relationships-op-config.xml \
     --schema schema/<env>
```
-> `specs/<key>.yaml` (or `<key>.reversed.yaml` if one exists), `build/<KEY>/reverse/REVERSE-REPORT.md`,
`build/<KEY>/reverse/raw/{workflows,views,calculations}/*.xml`.

| Part | Captured as |
|---|---|
| object types | full: label, plural, description, parents (incl. max/min parents), children; `template: existing` |
| fields (own and on shared types) | full: type, required, enum values in order, default, description, min/max, search, label, guidance, currency, length, starting group |
| relationships between shared types | full (max parents); `reason: TODO` |
| profiles | the profiles that include the types |
| filters | name, object type, criteria expression |
| views | name, type, object type + raw XML |
| workflows | stages and actions (REST), start type, execute-as-system + raw XML; assignees/operations/validations still to write |
| calculations | `calculations_captured` (name, type, enabled) + raw XML; move to `calculations:` with inputs/set when refined |

`solution.existing: true` relaxes two lint rules (names need not share the key; `template: existing`).

## 4. Prove and adopt

1. `gen_fields.py specs/<key>.yaml --compare <dump A> --relationships <dump B>` -> **0 differences**.
2. `verify_spec.py specs/<key>.yaml --env <env>` -> **0 errors** (read-only).
3. Resolve TODOs: one `primary: true` parent per type (not in the dumps), `reason` on shared changes, `owner`.
4. Refine workflows (assignees, operations, validations, comments), views (sections, fields) and calculations from
   `raw/`, re-running 1-2 after each change.
5. Add `tests.scenarios` and run them on a **dev copy** (never on prod).
6. From here on the spec is the source of truth: change spec -> generate/plan -> verify -> test -> package.

Limits: field types other than the seven confirmed encodings are reversed (multi_enum, decimal, simple/medium string)
but `gen_fields` refuses to generate them until one is confirmed from a dump; the primary parent and the reasons for
shared changes are not in any dump; questionnaire template content is not in these dumps (capture it from the Template
Editor or Export Configuration).
