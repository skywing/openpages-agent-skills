# Project: OpenPages solutions (IBM OpenPages 9.2.1, local container = env `local`)

- Use the `openpages-solutions` skill for all OpenPages work. Scripts: `skills/openpages-solutions/scripts/`, run from repo root with the
  project venv: `./op <script>.py ...` (or `.venv/bin/python skills/openpages-solutions/scripts/<script>.py`). Never use system python;
  if `.venv` is missing, run `bash setup_venv.sh`. New dependencies go in `requirements.txt`.
- Specs in `specs/` are the source of truth; update the spec before building or testing anything.
- Never write to non-dev environments; never store credentials in files. Dry-run before `--apply`.
- Record new error symptom → cause → fix rows in `skills/openpages-solutions/references/troubleshooting.md`.
- Learning requests ("teach me OpenPages", "start/continue the tutorial", "check lesson N") use the `openpages-tutorial`
  skill (`skills/openpages-tutorial/`): one lesson at a time in the shared-dev environment, every name prefixed with the
  learner's code; `./op tutorial ...`.
