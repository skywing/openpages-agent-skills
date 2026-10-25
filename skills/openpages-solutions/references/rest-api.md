# OpenPages GRC REST API V2 (9.2.x)

Base URL: `https://<host>:<port>/opgrc/api/v2`. Source: IBM OpenPages REST API V2 OpenAPI spec (9.1 edition,
"may also apply to subsequent releases") plus the 9.2.1 release notes. Re-verify anything marked *(verify)*
against the 9.2.1 API reference for your instance before depending on it in automation.

## What the API can and cannot do

| Can (data + runtime) | Cannot (configuration) |
|---|---|
| Create/read/update/soft-delete objects, bulk create (≤100/request) | Create object types, field groups, fields |
| Add/remove parent/child associations | Create/modify relationships between object types |
| Query (SQL-like), global search | Create/modify views, profiles, filters |
| Read type definitions, fields, association definitions | Create/modify workflow definitions |
| Read workflow definitions; start workflows; transition instances | Export/import configuration (use UI, ObjectManager, or 9.2.1 packaging REST) |
| Toggle System Admin Mode; read/update settings; tags; SCIM users/groups | |

Configuration is built in the admin UI (or loaded as ObjectManager XML) and **verified** through the API.

## Authentication

| Deployment | Options |
|---|---|
| On-prem / local container | Basic auth (`Authorization: Basic ...`), or native OAuth 2.0 bearer token |
| OpenPages as a Service | Bearer token/API key (basic auth not available) |

OAuth 2.0 client credentials (9.2.x): `POST https://<host>:<port>/oauth2/endpoint/OPOauthProvider/token`
form body `client_id`, `client_secret`, `grant_type=client_credentials` → `access_token`. Client secrets expire
(registry `/Applications/Common/Administration/Oauth2 Client Expiry`); error text "The client secret has expired".

## Endpoints used by the scripts

| Purpose | Call |
|---|---|
| All object types | `GET /types` |
| One type + fields | `GET /types/{id or system name}?include_field_definitions=true` |
| Allowed relationships | `GET /types/{type}/associations[?association_type=parent\|child]` |
| Query | `POST /query` `{"statement","offset","limit","max_rows","case_insensitive","honor_primary"}` |
| Create object | `POST /contents[?append_enum_vals=true]` |
| Bulk create | `POST /contents/bulk` `{"create_objects":[...]}` max 100, `proceed_on_error` default true, 206 on partial success, existing objects are updated |
| Read object | `GET /contents/{id or path}?include_workflow=true&include_associations=none\|both\|parent\|child&field_filters=&evaluate_computed_fields=true` |
| Update object | `PUT /contents/{id}` |
| Soft delete | `DELETE /contents/{id}` (recover via `GET /contents/deletedresources`; purge is a separate endpoint this tooling never calls) |
| Empty create payload | `GET /contents/template?type_id=` |
| Associate | `POST /contents/{id}/associations` `{"associations":[{"id":"6045","type":"parent"}]}`; also `/associations/children`, `/associations/parents` |
| Disassociate | `DELETE /contents/{id}/associations?parents=1,2&children=3,4` |
| Can user create child type | `GET /contents/{id}/permissions/cancreate/{type}` |
| Workflow definitions | `GET /workflows/definitions[?object_type=&include_activities=true]` |
| Start workflow | `POST /workflows/definitions/{def id}/start/{grc_object_id}` |
| Workflow instance | `GET /workflows/instances/{id}` → `{id,status,assignees,grc_object,workflow:{id,name,version,activity:{id,name,label}}}` |
| Transition | `POST /workflows/instances/{id}/transition/{action name}` → `{grc_object_id,workflow_id,process_state,activity_instance_id,activity_name,activity_label}` |
| Search instances | `GET /workflows/instances/search?type_definition=&workflow=&user=&offset=&limit=` |
| System Admin Mode | `GET/PUT /configuration/admin_mode?enable=true\|false` |
| Settings (registry) | `GET /configuration/settings/{path}`, `PUT /configuration/settings` |
| Full object as JSON via a Task View (9.2.1) | `GET /contents/{resource_id}/object_json/{view_id}`: root object + related objects in the view + attachments; good for AI agent context and test snapshots *(verify)* |
| Configuration Packaging (9.2.1) | "REST API support for all functionality" per release notes; paths not in the 9.1 spec. Capture from your instance's API reference before scripting *(verify)* |

## Payload rules

- `type_definition_id`: type ID (`"6"`) or system name (`"SOXIssue"`). Labels are not accepted.
- `primary_parent_id`: object ID or full path (`/_op_sox/Project/Default/Issue/Parent-Issue.txt`).
- Fields are identified by `id` or `name`; custom field name = `"<FieldGroup>:<Field>"` (e.g. `OPSS-Iss:Status`).
  System fields have bare names (`Resource ID`, `Comment`, `Name`, `Description`).
- Enum value: `{"name": "Open"}`. Multi-value / actor fields: list, e.g. `[{"name":"Internal Audit"},{"id":"3484"}]`.
- `append_enum_vals=true` creates missing enum values on the fly. **Never use it in tests**: it silently changes configuration.
- Setting MEDIUM/LARGE string fields to null stores `""`.
- Documents: attachment content in `content_definition.children` (Base64 for binary); for large files use `PUT /contents/{id}/document`.
- Locked parents cannot take new child associations unless allowed by `/OpenPages/Applications/GRCM/Locked Objects/Allowed Associations/*`.

- `DATE_TYPE` values are instants. A bare `2026-12-31` is stored as UTC midnight (shows as Dec 30, 19:00 in New York).
  `shape_fields` sends spec dates as midnight in the env's `timezone` (config/environments.yaml) as `...T05:00:00.000Z`;
  `test_run.py` compares `expect_fields` dates in the same zone.

Data types observed live on a 9.2.1 server (7 types dumped): `STRING_TYPE`, `LARGE_STRING_TYPE`, `ENUM_TYPE`,
`MULTI_VALUE_ENUM`, `DATE_TYPE`, `INTEGER_TYPE`, `FLOAT_TYPE` (spec `decimal`), `BOOLEAN_TYPE`, `ID_TYPE`
(`MEDIUM_STRING_TYPE` is in the OpenAPI spec but not yet seen live). Still unconfirmed: currency, user/group,
business entity; pin them in `config/type_map.yaml` after dumping a type that has them (e.g. `dump_schema.py --only Vendor`).

## Query service

```sql
SELECT [Resource ID], [Name], [TPR-Rem:Status] FROM [TPRRemediation] WHERE [TPR-Rem:Status] = 'Draft'
```
- Brackets around type and field names. `SELECT *` is **not supported**; list columns.
- Default page size 50 (`/OpenPages/Platform/API/Query/Default PageSize`); page with `offset`/`limit`; `max_rows: 0` = all.
- Unordered queries are ordered by the first column for stable paging.
- Results honor the caller's security (role-based + security rules): test with a business-user account too.
- Escape `'` inside LIKE with a backslash (Python string: `"\\'"`).
- JOINs between types are supported; `honor_primary=true` restricts to primary associations. Build JOINs from
  a working example in your environment before relying on them *(verify syntax)*.

## Errors

Body: `{"status_code","errors":[{"code","message","text","data","related_property_id","trace","more_info"}],"trace"}`.
`OPError.summary()` prints `code: message data trace=...`. Quote the `trace` UUID when raising an IBM case;
server-side detail is in the Liberty logs (`<OP_HOME>/wlp-usr/servers/<server>/logs`) and Aurora logs
(`<OP_HOME>/aurora/logs/debug`).
