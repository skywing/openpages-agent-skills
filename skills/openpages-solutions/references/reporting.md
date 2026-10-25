# Reporting schema and reporting framework (9.2.x)

Source: Administrator's Guide > *Managing the reporting schema* and *Configuring and generating the reporting framework*
(9.2.x, "Changes that require the reporting schema to be updated or re-created").

Two different things:
- **Reporting schema (RPS)**: real-time reporting tables/views in the OpenPages database, maintained by OpenPages.
  Actions: **Update** (incremental), **Create / Re-Create** (Re-Create drops then rebuilds), **Drop**.
- **Reporting framework (RPF)**: the Cognos framework models/packages generated from the schema. Action: **Generate / Update**
  (all models or selected models). Never edit these packages in Cognos Framework Manager; regeneration overwrites them.

## Policy for this skill

| Action | Allowed? |
|---|---|
| Generate / update the **reporting framework** (admin UI or `RpsRpf` with `RPSRPF_ACTION_TYPE=RPF`) | Yes |
| **Update** the reporting schema (incremental, admin UI) | Yes, in a planned window (needs SAM) |
| **Re-Create** or **Drop** the reporting schema, `DROP_REPORTING_SCHEMA=true`, SQL scripts such as `RPS_Update` | **No.** Flag it, explain why it is needed, and leave the decision and execution to the platform owner/DBA through change management |
| Any SQL/DDL against the OpenPages database | **Never** |

Prefer designs that need no re-create: **disable** a relationship or stop using a field instead of *removing*
object types/fields (removal requires a schema re-create).

## Change → required action (IBM table, 9.2.x)

| Change | Re-create schema | Update schema | Generate framework |
|---|---|---|---|
| Add a field to a field group | No | No | **Yes** |
| **Add a new object type** | No | No | **Yes** |
| **Add an association between object types** | No | No | **Yes** |
| Remove a field from a field group | No | No | Yes |
| Disable an association between object types | No | No | Yes |
| Encrypt a long string (CLOB) field | No | No | Yes |
| Define/modify/delete business entity recursive object levels | No | No | Yes |
| **Import a profile** (ObjectManager or Import Configuration) | No | **Yes** | No |
| Set/change display type to Multi-Valued User/Group/User Group Selector | No | **Yes** | No |
| Add an index on an RT column (`Settings > Platform > Reporting Schema > Create Index on Fields`) | No | **Yes** | No |
| Remove orphaned RPS columns and tables | No | **Yes** | No |
| Remove object types or attributes | **Yes** (out of policy) | No | Yes |
| Change the security model (needs IBM Support once data exists) | **Yes** (out of policy) | No | Yes |
| Change *Populate past periods* | **Yes** (out of policy) | No | No |
| Change reporting URL settings (Host, Port, Protocol) | **Yes** (out of policy) | No | No |
| Configure the triangles setting | **Yes** (out of policy) | No | No |

Consequence for a typical custom solution (new types + fields + relationships + profile + views + workflow):
**Update schema** (because of the profile import) **+ Generate framework** (because of new types/fields/associations).
No drop, no re-create. Regenerating does not change existing reports; new fields must be added to reports by a report author.

## Permissions

| Task | Application permission |
|---|---|
| Open *System Configuration > Reporting Schema* (update/create/drop) | **Reporting Schema** |
| Enable/disable System Admin Mode | **System Administration Mode** |
| *Cognos Analytics > Reporting Framework Generation* | **Reporting Framework** (SOX > Administration > Reporting Framework) |
| `RpsRpf.sh` | API > Administration > Background Process > Get Process Info, plus the above (or super administrator) |

Recommendation: give the solution builder role **Reporting Framework** only; keep **Reporting Schema** with the platform
owner, since the same page exposes *Re-Create* and *Drop*.

## Operational notes

- Schema update/create needs SAM: users can't log on and logged-in users can't commit. Schedule it; no reports,
  backups or jobs running during the operation.
- OpenPages does **not** need a restart after a schema operation.
- Every schema operation is logged: on the Reporting Schema page, search for the operation to open its
  **Information** and **Log** tabs. Attach them to the change record.
- *Populate Past Periods* (`Settings > Platform > Reporting Schema > Populate Past Periods`, default `true`) includes all
  enabled past reporting periods in the schema, which makes schema operations take longer. Changing it requires a
  re-create, so it's out of policy for this skill; leave it as configured.
- Cognos URL/host pointer changes are propagated to the schema by a separate documented procedure (*Update Cognos
  settings and URL host pointers for Cognos reports*). They're environment setup, not solution work, and are out of scope.

## Procedures

### Enable a new object type for reporting (before generating the framework)
`Open Administration menu > System Configuration > Settings > Platform > Reporting Framework V6 > Configuration > Object Prefix`
append `,<TYPE>=Z<letter>` (two uppercase letters, unique; IBM recommends `Z<n>` for user-created types, e.g.
`TPRREMEDIATION=ZA`, `TPRMILESTONE=ZB`).

### Update the reporting schema (incremental)
1. Planned window; make sure no reports, backups or other jobs are running (don't start any during the update).
2. `Open Administration menu > Enable System Admin Mode`.
3. `Open Administration menu > System Configuration > Reporting Schema` → **Update** → **Refresh** until 100%.
   Custom indexes are re-created automatically from their registry definitions (default on).
4. `Open Administration menu > Disable System Admin Mode`.
Do **not** click *Re-Create* or *Drop* on that page.

### Generate the reporting framework
Permission: *SOX > Administration > Reporting Framework*.
1. `Open Administration menu > Cognos Analytics > Reporting Framework Generation` → **Update**.
2. Choose **Selected Models** (only the models that contain the solution's namespaces) or **All Models**.
3. Submit; review the operation details for errors (Viewing reporting framework details).
4. **Test the reports.**

### Command line alternative: `RpsRpf.sh`
From `<OP_HOME>/bin` or `openpages-tools-client/bin`; `JAVA_HOME` set; `rest.url.path` in
`openpages-tools-client.properties` points at `https://<host>:<port>/grc/api`. In `RpsRpf.properties`:
```properties
RPSRPF_ACTION_TYPE=RPF          # framework only. (RPS/BOTH also creates the schema: not used by this skill)
DROP_REPORTING_SCHEMA=false     # must stay false
# RPF_PARAMS: do not modify
```
Credentials: put them in the file only for the run and remove them afterwards (or use the UI). Log:
`<client_tools>/logs/openpages-tools-client.log`.

### Keep models small
Large framework models produce a `model.xml` too big for Cognos. Put the solution's namespaces in a separate model and
disable unused namespaces (`Platform > Reporting Framework V6 > Models > <model> > Namespaces > <ns> > Is Enabled`).

## The ObjectManager note

Some ObjectManager topics say that on Db2 you should drop the reporting schema before loading metadata (object types,
fields, field groups, associations) and re-create it afterwards. That conflicts with this policy and with the table above
(these additions need only a framework generation). This skill does **not** drop it: it validates, loads with SAM on in a
quiet window, then runs Update schema (if profiles were imported) and Generate framework. If the load fails or locks,
stop and escalate with `ObjectManager.log`.
