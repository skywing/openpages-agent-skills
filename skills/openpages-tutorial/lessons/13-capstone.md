# Lesson 13 - Capstone: reverse-engineer your solution and finish cleanly

**Time:** 60-90 min · **Changes OpenPages:** disables your workflow, removes test data

## Objectives
- Bring a solution that was built in the UI back under spec control (the brownfield workflow).
- Prove spec and environment are identical.
- Leave the shared environment tidy.

## Concepts

Real OpenPages environments are full of solutions built by hand, without a spec. `reverse_spec.py` turns read-only
dumps into an **inventory** of non-IBM items (IBM's are marked `suppliedByVendor="true"`), you choose what belongs to the
solution in `selection.yaml`, and it drafts a spec. The proof is the round trip: `gen_fields --compare` reports
0 differences and `verify_spec` 0 errors. You did the forward direction; now do the reverse on your own solution.

## Do

### 1. Read-only captures
```bash
./om dump custom        --env shared-dev --out build/_reverse/shared-dev     # large: everyone's configuration
./om dump relationships --env shared-dev --out build/_reverse/shared-dev
./op dump_schema.py --env shared-dev --only PXKN
```

### 2. Inventory and selection
```bash
./op reverse_spec.py inventory --dump build/_reverse/shared-dev/shared-dev-custom-op-config.xml \
     --dump build/_reverse/shared-dev/shared-dev-relationships-op-config.xml --schema schema/shared-dev
```
Open `build/_reverse/selection.yaml`: keep only your `PXKN` items in one solution (key `PXKN`), delete everything else.
You will see other people's solutions: read, do not touch.

### 3. Draft spec and compare with yours
```bash
./op reverse_spec.py spec --selection build/_reverse/selection.yaml --key PXKN \
     --dump build/_reverse/shared-dev/shared-dev-custom-op-config.xml \
     --dump build/_reverse/shared-dev/shared-dev-relationships-op-config.xml --schema schema/shared-dev
#  -> specs/pxkn.reversed.yaml (yours exists) and build/PXKN/reverse/REVERSE-REPORT.md
```
Diff `specs/pxkn.reversed.yaml` with `specs/pxkn.yaml`. What came back exactly (types, fields, relationships, filters)?
What came back only as raw XML (views, workflow operations, calculations)? What can never come back from a dump
(primary-parent intent, reasons, tests)?

### 4. Round-trip proof
```bash
./om dump reference --env shared-dev --filter build/PXKN/template/ObjectManagerExportFilters-PXKN-reference.xml \
     --out build/PXKN/reference --prefix pxkn-reference
./op gen_fields.py specs/pxkn.yaml --compare build/PXKN/reference/pxkn-reference-op-config.xml \
     --relationships build/_reverse/shared-dev/shared-dev-relationships-op-config.xml
./op verify_spec.py specs/pxkn.yaml --env shared-dev
```

### 5. Finish cleanly
- Workflows > `PXKN Exception Lifecycle` > **disable** (running instances finish; no new ones start), unless the
  environment owner wants it kept as an example.
- Delete your two filters, or make them private.
- Test data: `test_run --cleanup` already removed scenario objects. Leave your Processes, template and program (they
  record the lesson), or ask the owner how they want them handled.
- Your object types, field groups and fields stay (they cannot be removed within policy); their prefix makes them
  traceable to you.

## Check
```bash
./op tutorial check 13           # self-check, then --confirm
./op tutorial status
```

## Recap
1. Which parts of a solution can a dump give back exactly, and which only as raw XML?
2. Why does the inventory need a human selection step?
3. What did you leave behind in shared-dev, and why is it acceptable?
