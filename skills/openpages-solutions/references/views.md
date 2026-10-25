# Views and the View Designer (9.2.x)

Menu: **Open Administration menu > Solution Configuration > Views** → View List → New View / open a view.

## View types

| Type | Purpose | Designer areas |
|---|---|---|
| Task View | Work on an object (fields, relationship fields, workflow actions) | header, canvas, user guidance |
| Grid View | List objects of one type; filter, search, bulk update, export | canvas |
| Creation View | Create a new object; must provide primary parent selection unless defaulted from context | canvas, user guidance |
| Admin View | All fields + relationships for the profile regardless of workflow stage; field order here drives import/export order | canvas |
| Report View | Read-only printable summary | header, canvas |

System views (≥1 Grid, 1 Creation, ≥1 Task per type) are read-only: set priority/enable/default only. To change one,
**Copy view** (works across view types; only compatible sections are copied).

## Rules of thumb

- Start from **Copy view** of the system view for the same type; it gets the header, parent selection and save
  behavior right. Build from scratch only for Report Views.
- The designer autosaves drafts (light syntax check). **Publish** runs full cross-view validation; fix all errors.
  *Discard Draft* reverts to last published.
- Only one person edits a view at a time; share the designer URL (contains the view's internal name) to collaborate.
- **View Priority** decides which view a user gets when several apply. After an import, priorities can conflict:
  review them.
- JSON tab shows the full definition (may be hidden by the Content-Security-Policy registry settings). Use it to diff,
  not to hand-author.
- Preview tab: up to 50 objects, read-only, ignores workflow stage overrides, so it cannot test stage-specific behavior.
  Use `test_run.py` plus a manual pass for that.
- Turn on **Open Administration menu > Other > Display Debug Info** while testing: shows which view is served (click to
  open it in the designer) and a *Why can't I save?* explanation.

## Relationship fields (the "link/associate" UI)

Kinds: **Card** (few objects, <5), **Grid** (many), **Chart**, **Count**, **Tree**.
Relationship Type: Children, Parents, Ancestors, Descendants (+ Relationship Path), Siblings (Parent Object Type +
Sibling Object Type; no actions), Contextual.
Filters: Folder Filter, Public Filter (users need it in their profile or the field disappears; a filter on an Add
action overrides the field's filter), Filter Rules. Multiple filters are ANDed.

Actions:
- Children: Add, Copy Recursive, Delete, New, Watson Suggestions
- Parents: Add, Set Primary Parent, Watson Suggestions
- 9.2.1: Add/Associate can pass the view definition to an AI model for relationship suggestions; with registry
  *Move object to primary parent folder* = True, Set Primary Parent can also move the object and its descendants.

Organize multiple relationship fields in **tab groups**.

## Spec → view mapping

In the spec, each view lists `sections` (fields) and `relationships` (`kind`, `relationship`, `object_type`, `actions`,
`fields`). `plan.py build` turns that into designer steps. Field references use `Group:Field`; system fields by bare name.

## Export

Views export via Export Configuration / Configuration Packaging (category *Views*) or ObjectManager
(`configuration.manager.dump.responsive.views=true`, filter `<responsiveViews><responsiveView name="..."/>`).
Workflows reference Task Views but **do not carry them**: package views alongside workflows.
