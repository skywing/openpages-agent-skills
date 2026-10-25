# Lesson 00 - Setup and guardrails

**Time:** 30-45 min · **Changes OpenPages:** no

## Objectives
- Run the tooling on your machine (macOS or Windows) against the shared environment `shared-dev`.
- Know the rules that keep a shared environment safe: prefixes, System Admin Mode, no database changes, no prod writes.
- Start your tutorial: your learner code, your spec, your progress file.

## Concepts

**What you are building.** A small *Policy Exception* solution: a process owner asks for a time-limited exception to a
policy; the exception lists compensating controls; a reviewer approves it only when the controls are in place; a
questionnaire on the process raises exceptions automatically. It touches every part of an OpenPages solution:

| Part | Lesson |
|---|---|
| Custom object types `PX<CODE>Exception`, `PX<CODE>Control` | 03 |
| Relationships (Process → Exception → Control, Policy → Exception) | 04 |
| Field groups and 9 field types | 05 |
| Profile, task/grid/creation views, filters | 06 |
| Automatic and manual GRC calculations | 07 |
| Workflow with validations and a calculation gate | 08 |
| Automated tests | 09 |
| Questionnaire with scoring and response actions | 10 |
| Reporting, packaging, reverse engineering | 11-13 |

**Spec first.** Everything is described in one YAML file, `specs/px<code>.yaml`. The scripts read it to generate
ObjectManager files, write UI checklists, verify what you built and test it. You change the spec, then build.

**The tooling.** `./op <script>` runs the Python scripts of the `openpages-solutions` skill with the project's virtual
environment; `./om` runs IBM's ObjectManager command-line client. Both read `config/environments.yaml`, which names
environments and the *environment variables* that hold credentials (never the credentials themselves).

**Shared environment.** `shared-dev` is used by other developers and learners at the same time. Three rules:
1. **Your code on everything.** System names start with `PX<CODE>` (e.g. `PXKN`), labels with `<CODE> ` (e.g. `KN `),
   test objects with `<CODE>-TEST`. `./op tutorial check` enforces it.
2. **System Admin Mode (SAM) locks everyone else out.** Object type, field and relationship changes need it. Keep it on
   for minutes, not hours, and turn it off when done. ObjectManager files from this tooling switch SAM themselves.
3. **Hands off shared configuration.** No edits to IBM types' field groups, the Questionnaire Assessment Workflow, other
   people's items. No SQL, no dropping tables or the reporting schema, ever. Nothing in this tutorial needs any of that.

**Permanent names.** Object types, field groups and fields cannot be deleted or renamed in OpenPages without a
reporting-schema re-create (out of policy). What you build in lessons 03-05 stays in `shared-dev`. That is why lesson 02
makes you check every name first.

## Do

Examples in all lessons use the learner code **KN** (key `PXKN`, spec `specs/pxkn.yaml`): replace it with yours.
Command convention in all lessons: commands are written for macOS/Linux. On **Windows (PowerShell)** use `.\op` instead
of `./op` and `.\om` instead of `./om`; paths with `/` work in PowerShell too. Where a command differs, both are shown.

### 1. Python 3.12 and the project venv

macOS:
```bash
cd ~/aidev/openpages            # your clone of the project
bash setup_venv.sh              # creates .venv (needs python3.12: brew install python@3.12)
```
Windows (install Python 3.12 from python.org first; tick "Add python.exe to PATH" and "py launcher"):
```powershell
cd C:\dev\openpages
powershell -ExecutionPolicy Bypass -File setup_venv.ps1
```
`op.cmd` sets `PYTHONUTF8=1` (the scripts write UTF-8 text; Windows would default to cp1252) and `setup_venv.ps1`
installs `tzdata` (Windows has no time-zone database; date fields need it).

### 2. Register the skills (Claude Code and GitHub Copilot)

Both tools load project skills from `.claude/skills/<name>/SKILL.md`.

macOS:
```bash
mkdir -p .claude/skills
ln -sfn "$PWD/skills/openpages-solutions" .claude/skills/openpages-solutions
ln -sfn "$PWD/skills/openpages-tutorial"  .claude/skills/openpages-tutorial
test -f .claude/skills/openpages-tutorial/SKILL.md && echo "skill link OK"
```
Windows:
```powershell
powershell -ExecutionPolicy Bypass -File link_skills.ps1     # directory junctions; no admin rights needed
```
Restart Claude Code or VS Code. In chat, `/openpages-tutorial` starts the coach (Copilot: agent mode).

### 3. The environment entry

Open `config/environments.yaml` and check the `shared-dev` entry: `base_url` (ask the environment owner), `tier: dev`,
`allow_writes: true`, `verify_tls`, `timezone`. Do not put credentials in it.

### 4. Credentials (this terminal session only)

macOS:
```bash
export OP_ENV=shared-dev
export SHARED_DEV_USER=<your OpenPages user>
read -s SHARED_DEV_PASSWORD && export SHARED_DEV_PASSWORD
```
Windows:
```powershell
$env:OP_ENV = "shared-dev"
$env:SHARED_DEV_USER = "<your OpenPages user>"
$env:SHARED_DEV_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
  [Runtime.InteropServices.Marshal]::SecureStringToBSTR((Read-Host -AsSecureString "Password")))
```
The variable names come from `username_env` / `password_env` in the `shared-dev` entry.

```bash
./op op.py ping            # OK env=shared-dev tier=dev ... writes=allowed ; System Admin Mode: ...
```

### 5. ObjectManager client (needed from lesson 03)

ObjectManager is IBM's command-line tool that dumps and loads configuration as XML. It runs on your machine and talks
to the server over HTTPS.
- Put the client in the project folder: `openpages-tools-client/` with `bin/` and `lib/` (git-ignored; get it from the
  environment owner). Windows: `bin/ObjectManager.cmd` (or `.bat`) must be there.
- Java 21 (IBM Semeru 21). macOS: `brew install --cask semeru-jdk-open@21` (your default `java` is left alone).
  Windows: install Semeru 21; `./om` finds it in Program Files, or set `om_java_home` in the `shared-dev` entry.
```bash
./om dump relationships --env shared-dev --dry-run     # shows what would run; changes nothing
```

### 6. Start your tutorial

Pick a code: your initials, 2-4 letters (`KN`). Check with your team that nobody else uses it.
```bash
./op tutorial start --code KN --owner <your OpenPages user>
./op tutorial lessons
```
This creates `specs/pxkn.yaml`, filter files in `build/PXKN/template/` and `runs/tutorial/KN/progress.yaml`.

## Check
```bash
./op tutorial check 0
```
Passes when `shared-dev` is reachable with your credentials, is not a prod-tier environment and allows writes.

## Pitfalls
- `can't find '__main__' module`: you ran `./op` without a script name.
- `No Java 21 found`: install Semeru 21 or set `om_java_home`. `java -version` showing another version is fine; `./om`
  selects Java 21 per run.
- HTTP 401: wrong variable names or values; `echo $SHARED_DEV_USER` (PowerShell `$env:SHARED_DEV_USER`).
- TLS errors: a dev server with a self-signed certificate needs `verify_tls: false` (dev only) or `ca_file`.

## Recap
1. Why must every name carry your code in `shared-dev`?
2. What happens to other users while System Admin Mode is on?
3. Where do credentials live, and where must they never appear?
