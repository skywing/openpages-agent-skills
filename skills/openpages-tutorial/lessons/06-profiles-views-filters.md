# Lesson 06 - Profiles, views and filters

**Time:** 60-90 min · **Changes OpenPages:** 3 views, 2 filters · **SAM:** not needed

## Objectives
- Understand how a profile decides what a user sees.
- Build a Task View with sections and relationship fields, a Grid View and a Creation View with the View Designer.
- Create public filters and use one in a grid.

## Concepts

**Profiles** bundle object types, fields and views for a group of users. Lesson 05's loader already included your types
and fields in the spec's profile. Views are picked per profile.

**View types** (9.2.x View Designer):

| Type | Purpose |
|---|---|
| Task View | work on one object: fields, relationship fields, workflow actions |
| Grid View | list objects: filter, search, bulk update, export |
| Creation View | create an object; must let the user pick the primary parent unless the context sets it |
| Admin View | every field regardless of workflow stage; drives import/export column order |
| Report View | read-only printable summary |

System views exist for every type and are read-only: **Copy view** from the system view of the same type and edit the
copy. The designer autosaves drafts; **Publish** runs full validation. **View Priority** decides which view a user gets
when several apply.

**Relationship fields** show related objects: *Grid* (many), *Card* (few), Chart, Count, Tree. Actions: Children → New,
Add, Delete, Copy Recursive; Parents → Add, Set Primary Parent.

**Filters** (public filters) are saved conditions on one object type, used in grids, relationship fields and Add
dialogs. A user must have the filter in their profile, or the field using it disappears.

## Do

Use the checklist the tooling writes from your spec: `./op plan.py build specs/pxkn.yaml` → `build/PXKN/BUILD.md`,
sections 6 and 7. Turn on **Administration menu > Other > Display Debug Info** while testing: it shows which view is served
and explains "Why can't I save?".

### 1. Task View `PXKNException-Task`
Administration menu > Solution Configuration > Views > View List > *Include system views* > open the system Task View of
*KN Policy Exception* > **Copy view**. Name it `PXKNException-Task`. On the Design tab:
- Section **Request**: Name, Description, Status, Risk Rating, Exception Category, Exception Owner, Requested Expiry
- Section **Justification**: Justification, Inherent Risk Score, Estimated Exposure, Renewal Requested
- Section **Calculated (read-only)**: Days to Expiry, Open Controls, Total Controls (make them read-only)
- Grid relationship field: Children → *KN Compensating Control*; actions New, Add, Delete; columns Name, Status,
  Effectiveness, Coverage Percent
- Card relationship fields: Parents → Process (Add, Set Primary Parent); Parents → Policy (Add)
Publish; fix every validation message.

### 2. Grid View and Creation View
- `PXKNException-Grid`: columns Name, Status, Risk Rating, Requested Expiry, Days to Expiry.
- `PXKNException-Create`: Name, Description, Risk Rating, Exception Category, Justification, Requested Expiry,
  Exception Owner, plus primary parent selection (from the system creation view you copied).
Publish both; set priority/default so your users get them.

### 3. Filters
Object Types > *KN Policy Exception* > Filters: `PXKN Open Exceptions` (Status not equal Expired) and
`PXKN Expiring Soon` (Days to Expiry less or equal 30). The second one becomes useful after lesson 07.

### 4. Use it
Open your Process, create one exception from it (Creation View), add one control from the exception's Controls grid
(Task View). Check the grid view and the *PXKN Open Exceptions* filter show it.

## Check
```bash
./op tutorial check 6            # self-check: confirm each item it lists, then
./op tutorial check 6 --confirm
```
REST cannot read view definitions, so this lesson is a self-check.

## Pitfalls
- A field you cannot find in the designer is not in the profile: back to lesson 05 step 4.
- A creation view without primary parent selection cannot save outside a parent's context.
- Two views with the same priority for one profile: users get whichever OpenPages picks. Set priorities explicitly.
- Workflows reference Task Views but packages do not carry them: views are packaged separately (lesson 12).

## Recap
1. Why copy the system view instead of building from scratch?
2. What happens to a relationship field whose public filter is not in the user's profile?
3. Which view does a user get when several apply?
