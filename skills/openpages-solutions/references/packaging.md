# Packaging and deploying configuration (9.2.x)

Policy: **no SQL/DDL against the database and no dropping Db2 tables or the reporting schema** at any stage.
If a step below or in IBM's docs requires it, skip it, flag it, and escalate on failure.

Three mechanisms, same underlying loader format. Source and target must be on the **same version and patch level**.

| Path | When | Notes |
|---|---|---|
| **Configuration Packaging** (9.2.0+) | Default for promotion dev → test → prod | Package lifecycle: create → select items (see dependencies) → publish → export → import on target *without deploying* → compare → deploy. 9.2.1: version diffs, date-range filter + quick search when selecting, **missing-dependency validation blocks the load**, **REST API for all functions**, pagination |
| **Export/Import Configuration** | Ad-hoc moves, anything packaging UI lacks | Admin menu > System Migration > Export Configuration / Import Configuration. Produces a JAR (`<prefix>-env-mig-<MMddYYkkmmss>`) saved in *Migration Documents*; downloadable. Import accepts JAR or ObjectManager XML |
| **ObjectManager CLI** | Scripting, diffable XML, instance data, supplemental types | `ObjectManager.sh d\|l\|v\|b c <auth> [dir] [prefix]` from `openpages-tools-client/bin` or `<OP_HOME>/bin`. Super Administrator has full access |

Permissions: *ExportConfiguration* / *ImportConfiguration* application permissions + read/write on the *Migration Documents* folder.

## What moves (Export/Import Configuration)

Application Text · Calculations · Custom ML Models · Dashboards · Date Dimension Types (+Associations) · Dependent Picklists ·
Error Text · Extensions · Field Definitions · Field Dependencies · Field Groups · Filters · Groups/Users · Jobs ·
Object Profiles · Object Text · Object Types · Object Type Dimensions · Object Type Relationships · Questionnaire Templates ·
Recursive Object Levels · Role Assignments · Role Templates · Rule Sets · Rules (RCM) · Security Rules · Settings ·
Solutions · Tags · Themes · Views · Workflows. (Questionnaire templates: always via Export Configuration / packaging,
never FastMap, which drops dependencies and response actions; see questionnaires.md.) 9.2.1 adds Canvas designs/templates export/import through the configuration UI.

ObjectManager-only (import the XML via Import Configuration): system data, file types, application permissions,
currencies/exchange rates, reporting folders, locales, **instance data**, parent/child relationships of instances.

## Auto-included dependencies

| Exporting | Also exports |
|---|---|
| Object type | field groups (+fields), field dependencies, dependent picklists, public filters, root folders, type images, settings/strings, **relationships**, file types (file-upload types) |
| Field group | its fields |
| Object profile | views, object types (+deps), field groups (+deps), view labels, dashboards |
| Questionnaire template | section/subsection/question templates incl. dependencies and response actions |
| Group | subgroups, users, memberships, profile associations, group admins |
| Object type dimensions | recursive object levels |

"Do not include dependencies" is available for some items (e.g. views without their types/fields).

## Not included: handle manually, in this order

1. **Business entities / security domains** (FastMap) before users, groups, role assignments.
2. Groups referenced by user-field scopes, assignees, role assignments (import validation stops with *Group Missing!*).
3. Reports used on profiles/dashboards, JSPs, triggers, custom query subjects.
4. Namespaces used by computed fields (profile passes validation but the field breaks).
5. Workflows triggered by exported rules/jobs; views/object types/custom actions referenced by workflows;
   everything a calculation depends on.
6. Encrypted settings, mail/SMTP, search server, reporting URL settings, *Export File Name Prefix*; integration keys.
7. Questionnaire template ↔ object associations.

## Best-practice sequence

1. Baseline: dev/test mirror prod metadata (OPBackup), so nothing stray is promoted.
2. Build + test in dev; `verify_spec.py` = 0 errors; `test_run.py` green.
3. Package (or export) with SAM **off**; disable invalid triggers; no other import/export/validate job running.
4. Target: **Validate** first (well-formed loader, valid attributes, all dependencies present in file or target,
   special characters if enabled). Fix every error.
5. Import in a window with users off; the import may toggle SAM; make no manual config changes during it.
6. Settings that depend on new items → **second** migration file after the first import.
7. Security rules only after metadata **and** reporting schema exist in target.
8. Calculations: if import fails on input/output field conflicts, disable existing target calculations and re-import.
9. Post-import: review View Priorities; if profiles were imported run reporting schema **Update** (SAM on; System
   Configuration > Reporting Schema > Update); for new types/fields/associations set Object Prefix and **generate the
   reporting framework**; test reports (never Re-Create/Drop the schema, see reporting.md); `verify_spec.py --env <target>`
   (read-only) and `dump_schema.py` diff vs dev → attach to the change record.

## ObjectManager details

- Loader files: `<prefix>-op-config.xml`, root `<openpagesConfiguration xmlFormatVersion="...">`. Pass only the prefix.
- Dump scope: `ObjectManager.properties` (`configuration.manager.dump.*=true` per category;
  `configuration.manager.migrate.configuration.objects=true` = all configuration categories). Back it up before editing.
- Narrow with `ObjectManagerExportFilters.xml` next to `ObjectManager.sh` (root `<openpagesConfigurationBOM xmlFormatVersion="1.0">`),
  e.g. `<objectProfiles><objectProfile name="..."/></objectProfiles>`, `<responsiveViews><responsiveView name="..."/></responsiveViews>`.
  Predefined filter tags include `contentType` (object types), `bundleType` (field groups), `objectProfile`,
  `queryDefinition` (filters), `applicationString`, `currency`, `resource`, `ruleSet`. Start from the shipped
  `ObjectManagerExportFilters-Example.xml`.
- Exclude environment-specific settings: `configuration.manager.migrate.configuration.exclude.registry.entry.<n>=/OpenPages/...`
- Importing **security rules overwrites all existing ones**: export target rules, edit, re-import.
- New object type attribute updates on re-import need `allowOverride="true"` on `contentType`.
- `plan.py package <spec>` writes the filters file, properties snippet and the runbook; `diff_config.py` diffs two dumps.
- OpenPages as a Service: use `ibmcloud openpages` CLI for ObjectManager commands; auth by API key.

## Running ObjectManager from a desktop (remote client)

Administrator's Guide 9.2.x, "Installing tools and utilities" (p.734) and "Tools properties and parameters" (p.1029):
ObjectManager is a **REST client** (its log shows `sending ... bytes to endpoint validate/...`), so it runs on a laptop
against a remote OpenPages; no server login needed.

- Needs: IBM Semeru Runtimes (Java) with `JAVA_HOME` set, and network access to the application server's HTTPS port.
- Package: `openpages-tools-client.zip` from the installation media (`/OP_<version>_Main/OP_<version>_Tools`); on Cloud Pak
  for Data `oc cp openpages-<instance>-sts-0:/opt/ibm/OpenPages/openpages-tools.zip .`; OpenPages as a Service uses
  `ibmcloud openpages objectmanager`. Extract; work in `openpages-tools-client/bin`.
- `openpages-tools-client.properties`: **`rest.url.path = https://<host>:<port>/grc/api` (V1)**. Verified 9.2.1-89
  (2026-10-24): with the V2 path (`/opgrc/api/v2`) the server accepts the request but answers with lower-case process
  states (`"status_running"`) that the client cannot parse (`InvalidFormatException ... ProcessStatusType`); the
  server's own client is configured with `/grc/api` (internally `http://opapp:10108/grc/api`). TLS: the server certificate must be valid or in the client JVM's truststore; `insecure.skip.tls.verify=true`
  only for a dev container. Large loads: `max.req.body.size.mb` (chunks requests); busy server:
  `retry_count_on_http_429`, `retry_interval_sec_on_http_429`.
- Same commands as on the server (`ObjectManager.sh d|v|l c <user> <password> <dir> <prefix>`), same dump options in
  the client's `ObjectManager.properties`, same filter file. Pass credentials from `OP_USER`/`OP_PASSWORD`; never store
  them in properties files.
- Logs: `<client_tools>/logs/openpages-tools-client.log`.
- Prod/UAT from a laptop is a policy question (named admin account, network path, change approval), not a technical one.

### ObjectManager authentication (Admin Guide 9.2.x pp.98-101, 784-785)

| Deployment | `<authentication>` arguments |
|---|---|
| On premises / OpenPages on Cloud, basic auth | `<user> <password>` |
| On premises / OpenPages on Cloud, **native OAuth 2.0** configured | `<CLIENT_ID> <CLIENT_SECRET>`, plus `was_auth_server_url=https://<host>:<port>/oauth2/endpoint/OPOauthProvider` in `openpages-tools-client.properties`; the tool gets the token itself |
| IBM Software Hub (Cloud Pak for Data) | `jwt <JSON-Web-Token>`, or `<user> <API key>` (`platform.cloudpak.auth=true`, `platform.cloudpak.useZenApiKey=true`) |
| watsonx.governance as a Service on AWS | `apikey <API key>` |

- Once native OAuth 2.0 is configured, **basic auth is refused** for the REST API and the CLI tools (ObjectManager,
  RpsRpf, Notification Manager, UPEA). On premises there is no documented option to pass a pre-fetched bearer token.
- The OAuth client belongs to a functional user (its permissions apply); the secret expires per
  `/Applications/Common/Administration/Oauth2 Client Expiry`. The same client ID/secret serve `opclient.py`
  (`auth: oauth`, `OP_CLIENT_ID`/`OP_CLIENT_SECRET`) and ObjectManager.
- Credentials are command-line arguments (visible to `ps` on the machine): pass them from environment variables, run on
  a single-user workstation, and never write them into properties files or scripts.

### Desktop client built from the server's own files (when the installation zip is not at hand)

Verified on macOS against the dev container, 2026-10-24. Uses IBM's 9.2.1 files from the server; the proper source is
still `openpages-tools-client.zip` from the installation package.

1. Java 21 (the server runs IBM Semeru 21): `brew install --cask semeru-jdk-open@21`. It installs beside other JDKs and
   does not change the default `java`; select it per command: `JAVA_HOME=$(/usr/libexec/java_home -v 21) ./ObjectManager.sh ...`.
   The launcher uses `$JAVA_HOME/bin/java`, not the `java` on `PATH`.
2. Copy from `<OP_HOME>` (container: `/home/opuser/OP/OpenPages`) to a folder OUTSIDE the project (IBM files, not in git):
   `bin/ObjectManager.sh`, `bin/ObjectManager.properties`, `bin/openpages-tools-client.properties`,
   `bin/ObjectManagerExportFilters.xml`, any `bin/*log4j*`, and the 26 jars named in the launcher's `CLASSPATH`
   (`lib/openpages-tools-client.jar`, Implementation-Version 9.2.1, plus Spring/Jackson/Log4j/Guava/...).
   Main class `com.ibm.openpages.objectmanager.App`.
3. Delete line 2 of `ObjectManager.sh` (`JAVA_HOME=/opt/ibm/ibm-semeru-certified-21-jdk`, the container's path).
4. `rest.url.path = https://<host>:<port>/grc/api`; `insecure.skip.tls.verify = true` only for the self-signed dev
   container (keep `false` with the server certificate in the JVM truststore for UAT/prod).
5. Smoke test with a validate (read-only): two `STATUS_FINISHED_SUCCESS` lines.

### `./om`: the project wrapper (use this instead of calling ObjectManager.sh by hand)

`scripts/om.py` (launcher `./om` at the project root) runs the desktop client against an entry in
`config/environments.yaml`. It never edits the client folder: each run gets a temporary `bin/` copy with that run's
`openpages-tools-client.properties` (`rest.url.path = <base_url>/grc/api`, TLS from `verify_tls`, OAuth URL when
`auth: oauth`), `ObjectManager.properties` (only the dump options for the chosen kind) and filter file, linked to the
client's `lib/`, and Java 21 picked per run. Credentials come from the variables the entry names (prompted if unset),
masked in the log.

```bash
./om validate build/<key>/fields <key>-fields --env local       # read-only check of a loader
./om load     build/<key>/fields <key>-fields --env local       # WRITE: type the prefix to confirm (or --yes)
./om dump relationships --env uat                               # every relationship set, nothing else
./om dump reference --filter build/<key>/template/ObjectManagerExportFilters-<key>-reference.xml --env uat
./om dump custom --env uat                                      # input for reverse_spec.py
./om dump filter --filter my-filter.xml --env uat               # any dump narrowed by your own filter
./om dump custom --env uat --dry-run                            # show the command and properties, run nothing
```

- Output: `build/_om/<env>/<env>-<kind>-op-config.xml` (override with `--out`, `--prefix`); log in
  `runs/om-<env>-<command>-<time>.log` with the client's own log appended.
- `load` is refused for `tier: prod` and for `allow_writes: false`; each load is appended to `runs/audit.jsonl`.
- Exit code 2 when ObjectManager reports `STATUS_FINISHED_ERROR` or validation errors even though Java exited 0.
- Environment keys (optional): `om_client_dir`, `om_java_home`, `om_rest_url`, `om_oauth_url`, `om_insecure_tls`.
