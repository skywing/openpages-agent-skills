# Lesson 07 - GRC calculations: automatic and manual

**Time:** 60 min · **Changes OpenPages:** 2 calculations · **SAM:** not needed

## Objectives
- Choose between Automatic, Manual and Runtime calculations.
- Write expressions: field references, related-object lists, `if ... else ... endif`, `count`, `exists`, date helpers.
- Know why a calculated value can be stale or blank.

## Concepts

A **calculation** belongs to one object type and sets fields **on that type only**. It reads fields from the object
itself, direct children/parents, ancestors/descendants and the Preference object; never from siblings. Operations run in
order: *Input Field* (fetch a value; a related object's field is a **list**), *Variable*, *Set Field* (last).

| Type | Runs when | Use for |
|---|---|---|
| **Automatic** | the object is created, an input changes (UI, workflow, API, FastMap), an association changes; queued | values that track their inputs |
| **Manual** | only a workflow action's *Run calculation* operation | a gate that must be fresh at that moment |
| **Runtime** | the object is opened in a view configured for it; never saved | on-screen helpers |

Your two calculations (spec `calculations:`):
```text
PXKN Days to Expiry   (automatic)  input  Expiry = self PXKN-Exc:Requested Expiry
   set PXKN-Exc:Days to Expiry = if exists([$Expiry$]) then [$DaysFromNow/PXKN-Exc:Requested Expiry$] else 0 endif

PXKN Control Counts   (manual)     input  OpenCtl = child PXKNControl, field PXKN-Ctl:Status, Filter By Status = Proposed
                                   input  AllCtl  = child PXKNControl, field System Fields:Name (no filter)
   set PXKN-Exc:Open Controls  = if exists([$OpenCtl$]) then count([$OpenCtl$]) else 0 endif
   set PXKN-Exc:Total Controls = if exists([$AllCtl$])  then count([$AllCtl$])  else 0 endif
```
Why both counts: "open = 0" is also true for an exception with **no** controls. The workflow validates `Total >= 1` as well.

**Stale values.** Automatic calculations re-run on change, not on a schedule. *Days to Expiry* is correct on the day the
date was saved and then drifts. Ways out: recompute when read (a Runtime calculation on the view), filter on the date
itself (`Requested Expiry <= today + 30`), or an admin bulk run. Keep the field for the lesson; know its limit.

**Blank result = never ran.** A manual calculation's field stays blank until a published workflow runs it. New
calculations do not run on existing objects until a trigger or a bulk run.

## Do

Administration menu > Solution Configuration > **Calculations** > New.

1. `PXKN Days to Expiry`: object type *KN Policy Exception*, type **Automatic**. Operations: Input Field `Expiry` (self,
   `PXKN-Exc:Requested Expiry`), Set Field `PXKN-Exc:Days to Expiry` with the expression above. Tip: an expression must
   parse before it saves; type `/if` or `[$` in the editor for content assist. Publish.
2. `PXKN Control Counts`: type **Manual**. Input `OpenCtl`: Relationship *Direct Child*, Related Object Type
   *KN Compensating Control*, field `PXKN-Ctl:Status`, **Filter By** Status = Proposed. Input `AllCtl`: same child type,
   field `System Fields:Name`, no filter. Two Set Field operations. Publish. (It cannot run yet: lesson 08 adds the
   workflow operation.)
3. Try the automatic one: open your exception, set Requested Expiry to a date 20 days ahead, save, refresh after a few
   seconds: Days to Expiry = 20. Change the date again and watch it follow. The *PXKN Expiring Soon* filter now lists it.
4. Lint your expressions (the same rules the editor applies, offline):
   ```bash
   ./op verify_spec.py specs/pxkn.yaml --lint-only
   ```

## Check
```bash
./op tutorial check 7            # self-check, then --confirm
```

## Pitfalls
- `[$...$]` references are case- and spelling-exact, including the field group.
- Every `if` needs `else ... endif`.
- A related-object input is a list: `count()`, `sum()`, `exists()` work on lists; comparing a list to a value does not.
- Two calculations setting the same field run in no guaranteed order: avoid it.
- A workflow validating an **automatic** result can race the queue: gates use Manual + Run calculation (lesson 08).

## Recap
1. Why is the control count manual and not automatic?
2. Why does *Days to Expiry* go stale, and what are two ways around it?
3. What does a blank calculated field after a workflow action tell you?
