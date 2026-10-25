# OpenPages solutions workspace (9.2.x)

Home of the `openpages-solutions` Claude skill (source in `skills/openpages-solutions/`, linked into `.claude/skills/openpages-solutions`) and the
specs, schema snapshots, build plans, loaders and test runs it produces. Open this folder in Claude Code and the skill
loads automatically. Reference solution: **TPR** (Third-Party Remediation Tracker), `specs/tpr-example.yaml`.

## What this is

The skill turns an IBM OpenPages solution from a sequence of admin-UI clicks into a **specification that is designed,
checked, built, tested and promoted repeatably**. Claude Code (or a developer running the scripts directly) works as an
OpenPages solution engineer who knows the 9.2.x rules and quirks and cannot silently drift from the design.

You describe the solution once in a spec. The tooling builds as much of it as OpenPages allows, tells you exactly how to
build the rest in the UI, proves the result matches the spec, and produces a deployment package with the evidence that
compliance and change management ask for.

## What it helps with

| Stage | What it does | Tools |
|---|---|---|
| **Design** | One spec (YAML) describes the whole solution: object types, fields, relationships, views, workflows, calculations, questionnaires, changes to shared IBM configuration, tests, open decisions. Lint catches design errors before building: bad names, invalid calculation expressions (`if` without `else`, unknown functions), circular relationships, required fields on shared types, shared changes without a reason. | `spec.py`, `verify_spec.py --lint-only` |
| **Build** | **Generates** what can be generated: new object types (derived from a platform type dump), field groups, fields, enum values, labels, profile inclusion and relationships, as ObjectManager loaders validated on 9.2.1. For UI-only parts (views, workflows, questionnaire templates) it writes an ordered checklist with menu paths. | `derive_type.py`, `gen_fields.py`, `plan.py build`, `plan.py questionnaire` |
| **Verify** | Compares the live system with the spec over REST, and an ObjectManager dump with the spec field by field and relationship by relationship, so anything built differently or changed later in the UI shows up. Warns on system-wide hazards (e.g. two enabled auto-start workflows on one type, which breaks every object save). | `verify_spec.py`, `gen_fields.py --compare`, `dump_schema.py`, `diff_config.py` |
| **Test** | Creates test objects, drives workflows through REST, asserts stages, fields and expected errors, checks which workflow does or does not auto-start, cleans up. Computes expected questionnaire scores to check live results. Results go into a test-evidence file. | `test_run.py` (JUnit output), `qr_score.py`, `op.py qa` |
| **Promote** | Layered deploy runbook: loaders regenerated from the **target's own dumps**, Configuration Packaging for solution-owned config, recorded manual edits for shared IBM configuration; change-record table, open decisions, verification, per-layer rollback. | `plan.py package` |
| **Know-how** | Reference guides to 9.2.x behaviour, much of it confirmed on a live 9.2.1 container: calculation expression language, workflow REST limits, questionnaire mechanics, ObjectManager encodings and validator rules, date/time-zone handling. | `skills/openpages-solutions/references/*.md` |

## Why it matters

- **Control and audit trail.** Every design choice is written down with its reason; test evidence is produced as you
  go; the change record for UAT/production comes out of the spec (fits change management and SR 11-7-style governance).
- **Safety rails built in.** `tier: prod` is write-blocked in code; writes are dry-run unless `--apply` and logged to
  `runs/audit.jsonl`; no SQL/DDL and never dropping Db2 tables or the reporting schema; shared IBM configuration is
  never overwritten wholesale; unconfirmed loader encodings are refused rather than guessed; secrets only from
  environment variables (`OP_USER`, `OP_PASSWORD`).
- **Repeatability.** The second solution is mostly a new spec: generators, checks and tests are reused. Problems hit once
  are recorded in the references so the next team does not rediscover them (e.g. a leftover workflow copy that blocked
  every program launch, the validator's required `displayOrder`, the time-zone date bug, assessments keeping their
  launch-time scores).

## What it does not do

- **Views, workflow design and questionnaire content stay UI-built.** The skill plans and verifies them; OpenPages has no
  supported way to generate them.
- **REST v2 cannot pass workflow action comments**, so actions with a required comment are tested by hand.
- **Field generation covers seven field types** (enum, integer, date, currency, long string, user/group, boolean) whose
  encoding was seen in a live dump; other types need one dump of an existing field first.
- **It does not replace OpenPages judgement.** Design decisions (e.g. editing the shared assessment workflow in place,
  the vendor-Finding triage) are made by people; the skill makes sure they are recorded, built and tested.

## One-time setup

```bash
mkdir -p .claude/skills && ln -s "$PWD/skills/openpages-solutions" .claude/skills/openpages-solutions   # register the skill (absolute link)
ln -s "$PWD/skills/openpages-tutorial" .claude/skills/openpages-tutorial    # the tutorial skill (same pattern)
test -f .claude/skills/openpages-solutions/SKILL.md && echo "skill link OK"   # then restart Claude Code / VS Code
bash setup_venv.sh                                # creates ./.venv from requirements.txt (PyYAML only)
# edit config/environments.yaml -> local.base_url = your container's OpenPages URL (e.g. https://localhost:10111)
#   and local.timezone (IANA, e.g. America/New_York) so spec dates are stored correctly
export OP_USER=OpenPagesAdministrator             # or your admin user
read -s OP_PASSWORD && export OP_PASSWORD
./op op.py ping                                   # connectivity + auth + SAM status (runs with .venv)
./op dump_schema.py                               # snapshot -> schema/local/ (commit it)
./om dump relationships --env local --dry-run     # ObjectManager wrapper: desktop client + Java 21 (see packaging.md)
.venv/bin/python -m unittest discover -s tests    # self-test of the tooling against a mock server
```

All scripts run with the project venv: `./op <script>.py ...` or `source .venv/bin/activate` then
`python skills/openpages-solutions/scripts/<script>.py`. Container commands use **podman**.
ObjectManager runs through `./om` (desktop client, see `references/packaging.md`): it needs the client folder
(`openpages-tools-client/` in the project, git-ignored; or `om_client_dir`) and Java 21; your default `java` is left alone.

### Windows (PowerShell)

The Python scripts are the same; only the launchers differ. Install Python 3.12 (python.org, with the `py` launcher).

```powershell
powershell -ExecutionPolicy Bypass -File setup_venv.ps1   # .venv + tzdata (Windows has no time-zone database)
powershell -ExecutionPolicy Bypass -File link_skills.ps1  # .claude\skills junctions (no admin rights needed)
$env:OP_USER = "OpenPagesAdministrator"; $env:OP_PASSWORD = Read-Host "Password"
.\op op.py ping                                          # op.cmd = ./op (sets PYTHONUTF8=1)
.\om dump relationships --env local --dry-run            # om.cmd = ./om
```

| macOS / Linux | Windows | Note |
|---|---|---|
| `./op <script>` | `.\op <script>` | `op.cmd` sets `PYTHONUTF8=1`: the scripts write UTF-8 (arrows etc.) without naming an encoding |
| `./om ...` | `.\om ...` | needs `openpages-tools-client\bin\ObjectManager.cmd` (or `.bat`); Java 21 from `om_java_home`, `JAVA_HOME` or Program Files; `lib\` is copied per run when symlinks are not allowed |
| `bash setup_venv.sh` | `setup_venv.ps1` | |
| `ln -s` skill links | `link_skills.ps1` | directory junctions |
| `export X=...` | `$env:X = "..."` | |

`.gitattributes` keeps the bash launchers LF and gives the Windows launchers CRLF on checkout.

## Learning: the tutorial skill

`skills/openpages-tutorial/` is a self-paced course for developers new to OpenPages or at mid level. The learner builds
a small **Policy Exception** solution (two custom types, relationships to Process and Policy, nine field types, views,
filters, an automatic and a manual calculation, a workflow with a calculation gate, automated tests, a scored
questionnaire with response actions, packaging and a reverse-engineering capstone) in the **shared-dev** environment,
with every name carrying the learner's code (`PX<CODE>...`). Works with Claude Code and GitHub Copilot (VS Code agent
mode): both load `.claude/skills/openpages-tutorial/SKILL.md`; type `/openpages-tutorial`. The lessons are plain Markdown
and can also be followed without an AI assistant.

### Starting the tutorial

Before the first session: set the real `shared-dev.base_url` in `config/environments.yaml`, and register the skill
(macOS: the `ln -s` lines under One-time setup; Windows: `link_skills.ps1`). Restart Claude Code / VS Code afterwards:
skills are loaded at startup.

Open the project folder in **Claude Code**, or in **VS Code with Copilot Chat in Agent mode**, and type in the chat:

```
/openpages-tutorial start
```

or in plain words:

```
Start the OpenPages tutorial for me. My learner code is KN and my OpenPages user is <your user>.
```

The coach checks your progress (`./op tutorial status`), begins at lesson 00 (Python setup, shared-dev credentials,
ObjectManager client), then asks for your code and runs `./op tutorial start --code KN --owner <user>` once you
confirm. Your code is your initials (2-4 letters); check nobody else uses it.

| In the chat | What happens |
|---|---|
| `/openpages-tutorial next` | resumes at your next unfinished lesson |
| `/openpages-tutorial lesson 5` | opens a specific lesson |
| `/openpages-tutorial check 5` | runs the lesson check |
| `/openpages-tutorial status` | shows your progress |

Without an AI assistant, read `skills/openpages-tutorial/lessons/00-setup.md` and use the commands directly:

```bash
./op tutorial start --code KN --owner <OpenPages user>   # specs/pxkn.yaml, filter files, progress
./op tutorial next                                       # which lesson, which file
./op tutorial check 3                                    # lesson check (read-only)
```

If `/openpages-tutorial` is not offered: restart the tool; check `.claude/skills/openpages-tutorial/SKILL.md` exists
(`ls .claude/skills/`, Windows `dir .claude\skills`); in Copilot use **Agent** mode (skills are not used in Ask mode).

## The loop

| Step | Command |
|---|---|
| Spec | copy `specs/tpr-example.yaml` → `specs/<key>.yaml`; `verify_spec.py specs/<key>.yaml --lint-only` |
| Existing solution (brownfield) | `./om dump custom` + `./om dump relationships` (read-only) → `reverse_spec.py inventory` → edit `build/_reverse/selection.yaml` → `reverse_spec.py spec --key <KEY>` → prove with `gen_fields.py --compare` (see `references/reverse-engineering.md`) |
| New object types | dump a platform type with ObjectManager → `derive_type.py --dump ... --baseline SOXIssue --spec ... --type <Type>` → `./om validate` → `./om load`, SAM off (see `references/custom-object-type.md`) |
| Fields, profiles, relationships | `./om dump reference --filter ...` and `./om dump relationships` → `gen_fields.py specs/<key>.yaml --reference <dump> --relationships <rel dump>` → `./om validate` → `./om load`; or build in the UI from `plan.py build` → `build/<key>/BUILD.md` |
| UI-only parts | views, workflows, calculations from `BUILD.md`; questionnaire from `plan.py questionnaire` → `build/<key>/QUESTIONNAIRE-*.md` |
| Verify | `verify_spec.py specs/<key>.yaml` (0 errors); `gen_fields.py specs/<key>.yaml --compare <dump> --relationships <rel dump>` (0 differences) |
| Test | `test_run.py specs/<key>.yaml` (dry run) → `--apply --cleanup --junit runs/junit.xml`; `qr_score.py specs/<key>.yaml` for questionnaire scores |
| Package | `plan.py package specs/<key>.yaml` → `build/<key>/PACKAGE.md` (layered runbook) + ObjectManager filters |
| Post-deploy | `verify_spec.py specs/<key>.yaml --env uat`; new target dumps → `gen_fields.py --compare`; `diff_config.py schema/local schema/uat` |

## Layout

| Path | Contents |
|---|---|
| `skills/openpages-solutions/` | the skill: `SKILL.md`, `scripts/`, `references/`, `templates/` |
| `skills/openpages-tutorial/` | the tutorial skill: `SKILL.md`, `lessons/00-13`, `templates/pex-spec.template.yaml`, `scripts/tutorial.py` |
| `op`, `om` / `op.cmd`, `om.cmd` | launchers for macOS/Linux / Windows |
| `specs/` | solution specs (source of truth) |
| `config/` | `environments.yaml` (no secrets), `type_map.yaml` (confirmed REST data types) |
| `schema/<env>/` | REST snapshots from `dump_schema.py` |
| `build/<KEY>/` | `BUILD.md`, `PACKAGE.md`, `QUESTIONNAIRE-*.md`, `TEST-EVIDENCE.md`; `template/` and `reference/` ObjectManager dumps; `types/` derived type loaders; `fields/` generated field and relationship loaders |
| `runs/` | test runs, verify reports, `qa` files, `audit.jsonl` |
| `tests/` | unit tests for the tooling (mock OpenPages server) |
| `docs/ibm/` | IBM documentation used as the source (Administrator's Guide 9.2.x) |
