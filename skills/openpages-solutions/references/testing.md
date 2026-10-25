# Testing a custom solution

Layers, cheapest first. All automated layers run against the **local container**; only the read-only layer
(verify/dump) ever touches UAT/prod.

| Layer | Tool | Proves |
|---|---|---|
| 0. Spec lint | `verify_spec.py <spec> --lint-only` | naming rules, enum values present, workflow graph closed (every action targets a real stage, start + end exist) |
| 1. Schema conformance | `verify_spec.py <spec>` | types, fields, data types, required flags, enum values, relationships, workflow stages/actions/targets match the spec |
| 2. Data + association | `test_run.py` `create:` blocks | objects can be created under the declared primary parent with required fields; extra associations accepted |
| 3. Workflow behavior | `test_run.py` `workflow:` blocks | auto/manual start, each action lands on the expected stage, set-field operations happen, validations block (negative steps with `expect_error: true`) |
| 4. Security | run 2-3 with a business-user env entry (different credentials) | profile/role/security-rule behavior; query results honor security |
| 5. UI | manual checklist + Display Debug Info (optionally Playwright) | correct view served per stage, relationship fields/actions, *Why can't I save?* |
| 6. Deployment | `verify_spec.py --env uat` + `diff_config.py schema/local schema/uat` | the package landed completely |

| Questionnaires | `qr_score.py` + test program + `op.py qa` | dependencies hide the right questions; compliance/risk scores match; response actions and low-score objects created under the asset; reject → resubmit doesn't fail (Skip if it exists) |

## Writing scenarios

- One happy path per workflow branch, one rework/loop path, one negative per validation.
- Name test objects with a recognizable prefix + `{run}` (`TPR-TEST ... {run}`) so leftovers are easy to find
  (`op.py query "SELECT [Resource ID],[Name] FROM [TPRRemediation] WHERE [Name] LIKE 'TPR-TEST%'"`).
- Fixtures (existing parents such as an Issue or Business Entity) go in `tests.fixtures` by numeric id or `Type:Name` (REST `/contents/{id}` cannot resolve folder paths: a path returns HTTP 500 RESTEASY003210).
- Assert on **action names** for transitions and on stage name *or* label for position.
- Enum/actor values compare by `name`.
- Always record the run manifest; use `--cleanup` in CI, keep objects when debugging, then `cleanup.py <manifest> --apply`.
- `--junit runs/junit.xml` for CI dashboards.

## Calibrate on a new release (one time)

1. `op.py ping`, `op.py types --grep TPR`, `op.py wf --type TPRRemediation`.
2. `test_run.py spec --apply --only "<happy path>" -v` and read the request log: confirm `workflow_activity_ids` exists on
   the object with `include_workflow=true` and that `/workflows/instances/{that id}/transition/{action}` advances it.
3. `dump_schema.py`, then pin unconfirmed data types in `config/type_map.yaml` (verify_spec prints the exact line).
Record anything that differs in `references/troubleshooting.md` → *Environment notes*.

## Evidence for audit / model risk

Keep, per release: spec (git), `schema/<env>/` dumps before/after, `runs/verify-*.md`, `runs/junit.xml`, run manifests,
`runs/audit.jsonl` (every write this tooling made: who, when, env, request), package file + its diff.
