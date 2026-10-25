# Lesson 03 - Custom object types from a platform template

**Time:** 60 min · **Changes OpenPages:** two object types (permanent) · **SAM:** toggled by the loader for seconds

## Objectives
- Create a new object type the supported way: dump a platform type, derive, validate, load.
- Read an ObjectManager loader file and its derive report.
- Understand why SAM must be OFF when loading these files.

## Concepts

**ObjectManager** exports (`d`, dump), validates (`v`) and loads (`l`) configuration as XML files named
`<prefix>-op-config.xml`. It runs on your machine and talks to the server's REST API. `./om` wraps it: it builds the
client settings for the chosen environment in a temporary folder (V1 REST path `/grc/api`, TLS, Java 21) and never
edits the client folder.

**Deriving.** `derive_type.py` takes a dump of `SOXIssue` (or `SOXTask`) and writes a loader for your type: new system
name, labels from the spec, its own root folder (`/_op_sox/Project/Default/PXKNException`), the template's own field
groups removed, `suppliedByVendor="false"`. It keeps the dump's `<systemAdminMode>` markers, so **ObjectManager switches
SAM on and off by itself**. If SAM is already on, creating the root folder fails (`OP-00008 ... createCollection cannot be
executed in System Administration Mode`) and nothing is created.

**Validate is a dry run.** It checks the file against the DTD and enumerations; it does not prove the load will
succeed, but a pass with `STATUS_FINISHED_SUCCESS` and exit code 0 is required before any load.

## Do

### 1. Dump the two platform templates (read-only)
```bash
./om dump reference --env shared-dev --filter build/PXKN/template/ObjectManagerExportFilters-SOXIssue.xml \
     --out build/PXKN/template --prefix soxissue          # -> build/PXKN/template/soxissue-op-config.xml
./om dump reference --env shared-dev --filter build/PXKN/template/ObjectManagerExportFilters-SOXTask.xml \
     --out build/PXKN/template --prefix soxtask
```
PowerShell: put each command on one line (or end lines with a backtick `` ` `` instead of `\`).
Check the dump is not empty: it must contain `<contentType ` (`grep -c "<contentType " build/PXKN/template/soxissue-op-config.xml`;
PowerShell `Select-String "<contentType " build/PXKN/template/soxissue-op-config.xml`).

### 2. Derive your types
```bash
./op derive_type.py --dump build/PXKN/template/soxissue-op-config.xml --baseline SOXIssue --spec specs/pxkn.yaml --type PXKNException
./op derive_type.py --dump build/PXKN/template/soxtask-op-config.xml  --baseline SOXTask  --spec specs/pxkn.yaml --type PXKNControl
```
Outputs in `build/PXKN/types/`: `pxknexception-op-config.xml` + `pxknexception-derive-report.md` (and the same for the
control). **Read both reports.** Exit code 1 means warnings to read, not failure. Compare with the template:
```bash
./op diff_config.py build/PXKN/template/soxissue-op-config.xml build/PXKN/types/pxknexception-op-config.xml
```

### 3. Validate (read-only)
```bash
./om validate build/PXKN/types pxknexception --env shared-dev
./om validate build/PXKN/types pxkncontrol   --env shared-dev
```
Both must end with `OK` (`STATUS_FINISHED_SUCCESS`). Logs: `runs/om-shared-dev-validate-*.log`.

### 4. Load (WRITE, permanent)
Check SAM is **off** (`./op op.py ping`). Tell your team you are loading (the loader locks users out for a few seconds).
Re-read the system names in the reports one last time.
```bash
./om load build/PXKN/types pxknexception --env shared-dev     # type the prefix to confirm
./om load build/PXKN/types pxkncontrol   --env shared-dev
```

### 5. Look at the result
```bash
./op op.py type PXKNException --fields     # system fields only: your field groups come in lesson 05
```
In the UI: Administration menu > Solution Configuration > Object Types > *KN Policy Exception*.

## Check
```bash
./op tutorial check 3
```
Passes when both types exist; warns if a label differs from the spec.

## Pitfalls
- Dump has no `<contentType>`: the filter's wrapper element is wrong or the dump options are off. Use the generated
  filter files and `./om dump reference` (it turns on the right options).
- `Invalid rootFolderPath` / `objectType does not exist` after `OP-00008`: SAM was on. Turn it off and load again.
- Load failed half way: stop, keep `runs/om-*.log`, and tell the environment owner. Never drop or re-create the reporting
  schema to "fix" a load, even if an IBM note suggests it.
- Windows: `./om` needs `openpages-tools-client\bin\ObjectManager.cmd`. Passwords with `&`, `^`, `%` or `!` can break
  Windows batch argument parsing; use a password without them for the tutorial user or ask the environment owner.

## Recap
1. Why can't you create an object type in the UI in 9.2.x?
2. Why must SAM be off when loading a derived loader?
3. What does validation prove, and what does it not prove?
