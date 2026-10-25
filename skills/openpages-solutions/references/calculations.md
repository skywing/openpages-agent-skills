# GRC Calculations and expressions (9.2.x)

Source: *IBM OpenPages 9.2.x Administrator's Guide*, Chapter 14 "Configuring GRC Calculations", printed pages
348-389 (local copy: `docs/ibm/op_ 9.2.x_administrators_guide.pdf`, PDF pages 370-411; text extract
`docs/ibm/admin-guide-calculations-p346-389.txt`). Page numbers below are the printed ones. Summarised in our own
words; re-check the guide for anything not covered here.

Menu: **Open Administration menu > Solution Configuration > Calculations** (permission *SOX > Administration >
Calculation*). Registry folder: *Platform > Calculation* (`Enabled`, `Always Recalculate on the Object Save`,
`Async ...`, `Concurrent Calculation Jobs`, `Enable Calculation Preview`, `Task View Timeout for Queued Object`). p.348

## 1. Model (p.349-354)

- One **definition per object type** (an object type can have many). Versioned on Publish; can be disabled. The
  object type cannot be changed after creation. Calculations do nothing on **locked** objects.
- A calculation can only **set fields on its own object type**. It can **read** fields from the object itself, from
  **Direct Child / Direct Parent / Ancestor / Descendant** objects and from the **Preference** object. **No siblings.**
  It cannot associate, copy, or set computed fields, workflow system fields, `System Fields:Name/Created By/Creation
  Date/Last Modified By/Last Modification Date`, or relationship fields of Task Views.
- Never use `System Fields:Comment` in a calculation (reserved for File/Signature objects). p.361, 387
- **Operations** run in the order listed (reorder by drag and drop); put **Set Field last**. At least one Set Field.
  | Type | Does | Notes |
  |---|---|---|
  | Input Field | fetches a field from self / related object (Relationship Type, Related Object Type, Relationship Path for Ancestor/Descendant, **Filter By** conditions + Advanced Logic, sort field + direction, *Primary Parent Only*) / Preference object | result of a related-object input is a **list** |
  | Variable | holds an intermediate value from an expression | may use any earlier operation |
  | Set Field | writes `Output Field` = expression | may use any earlier operation, including earlier Set Fields |
  Operation names: A-Z a-z 0-9 _ - space, not starting with a digit or space. An expression must parse before the
  operation can be saved (tip: save `1+2` as a placeholder). p.360-364
- **Applicability**: conditions (Compare field / Using operator / To value, expression, field) restrict which objects
  qualify; several conditions = AND unless *Advanced Logic* (`1 and (2 or 3)`; precedence `() NOT AND OR`). String
  comparisons there are **case-sensitive**. Date fields can use *Adjust Date By*. p.361-363

### Calculation type (p.351, 361) — choose deliberately

| Type | Runs when | Set field in Task View | Use for |
|---|---|---|---|
| **Manual** | **only** a workflow action's *Run calculation* operation | editable | a value that must be fresh at a specific workflow step (e.g. a gate validated right after) |
| **Automatic** | object created; input field changed (UI, workflow stage, FastMap, **API**), including inputs on related objects; association changed; admin bulk run. Asynchronous queue. Cannot be started by a workflow | read-only | values that should always track their inputs |
| **Runtime** | object opened in a Task/Admin/Report view **and** the calculation is configured in the View Designer | display only (Set Field not persisted) | on-screen helpers |

Runtime cannot be converted to Manual/Automatic or back. Automatic runs are queued: a workflow step that validates an
automatic result can race the queue, so use Manual + *Run calculation* for gates.

### Other rules
- New calculations do **not** run on existing objects until a trigger event or an admin **bulk run** (Calculation List >
  select one > run; watch *In Queue / Next In Queue / Error Count*; email to the admin). p.386
- Several calculations may set the same field, but **run order is not guaranteed**: avoid it. p.352
- Cascades across objects are allowed (calc A sets a field that is an input to calc B on another object); watch
  performance, especially Ancestor/Descendant inputs (reverse lookups). Use Applicability, Filter By and *Primary
  Parent Only* to cut the object count. p.355-357
- Field dependency rules are **not** enforced on calculated values; dependent pick lists **are**. p.353
- Preference objects: the one on the closest **primary** parent business entity; design for several. Changing a
  Preference object may not trigger recalculation: bulk-run. p.353
- No scheduler, no undo. p.354

## 2. Expression syntax (p.364-369)

| Element | Rule |
|---|---|
| Field on this object | `[$Field Group:Field Name$]` (spelling and case exact) |
| System field | `[$System Fields:Name$]`, `[$System Fields:Resource ID$]` |
| Earlier operation | `[$Operation Name$]` (exact name and case) |
| Child / parent field (list) | `[$Child:ObjectType/Field Group:Field$]`, `[$Parent:ObjectType/Field Group:Field$]` (capital `C`/`P`) |
| Sorted child list | `[$Child:ObjectType/Group:Field/AscBy:Group:SortField$]` or `.../DescBy:...` |
| Preference field | `[$Preference/Field Group:Field$]` |
| Strings | `'single'` or `"double"`; both case-sensitive. In variables like `[$END_USER$]`, **double**-quoted text is resolved, single-quoted kept literally |
| Case | inside `[$...$]` case-sensitive; outside (function names, keywords) case-insensitive: `sum`=`SUM` |
| Whitespace | spaces and new lines anywhere between tokens |
| Functions | `name(args)`; zero-arg functions need `()`, e.g. `tomorrow()`; nesting allowed; parentheses must balance |
| Comments | `/* ... */`, `/** ... **/`, `// to end of line` |
| Content assist | in the editor type `/date` `/list` `/currency` `/if` `/string` for snippets, `[$` for earlier fields/operations |

Dates are written `2026-10-10` regardless of locale (p.381).

### Operators

| Operator | Applies to | Example → result |
|---|---|---|
| `+` | strings (concatenate) | `"abc" + "def"` → `abcdef` |
| `+ -` | numbers, currency, **dates** (days) | `[$TODAY$] + 10`, `[$Grp:Date$] - 5` |
| `* /` | numbers, currency | `100.00 / (2 + 3)` → `20.00` |
| `( )` | precedence | `10 * ([$N1$] - 30.3)` |
| arithmetic on a **list** | applied to every item | `[$L1$] - 5` → each item minus 5 |
| `== != > < >= <=` | conditions | |
| `AND OR NOT`, `AND NOT` | conditions | `if ([$a$] == 10 OR ([$a$] == 20 AND NOT [$b$] == 15)) ...` |

Enumerated values compare as their **name** string: `[$Grp:Status$] == 'Done'`.

## 3. Lists (p.371-373)

- A related-object Input Field (or a multi-value field) yields a **list**. Index starts at **0**; `at(list, -1)` is
  the last item.
- Filter the list in the **Input Field operation** (*Filter By*), not in the expression: there is no inline WHERE.
  Example: input `GetControls` = child SOXControl with Filter By `Operating Effectiveness == Effective`, then
  `count([$GetControls$])`.
- Set Field with a list result: one value or all-equal values → that value; only one non-empty → that value;
  **different values → nothing set and a calculation error**. Aggregate (`sum`, `max`, `count`, `at`, `join`) first.

## 4. System variables (p.374)

| Variable | Value |
|---|---|
| `[$TODAY$]` | today's date (re-evaluated each run) |
| `[$END_USER$]` | user name of the signed-on user (re-evaluated) |
| `[$DaysFromNow/Group:Date Field$]` | days from today to that date |
| `[$APPLICATION_URL$]`, `[$COGNOS_URL$]`, `[$TASK_VIEW_URL$]` | URLs (`[$System Fields:Task View URL$]` is deprecated) |
| `[$ApplicationText/key$]` | application text |
| `[$Setting/OpenPages/...$]` | a registry setting value |

## 5. Functions

### Strings (p.375-376)
| Function | Notes |
|---|---|
| `format(x)` | human-readable date / currency / actor (`Jane Smith - JSMITH`). Not for dates used in arithmetic |
| `indexOf(s, sub)`, `lastIndexOf(s, sub)` | 0-based position; on a list → list of ints |
| `length(s)` | on a list → applied per item |
| `substring(s, start)`, `substring(s, start, end)` | on a list → per item |
| `split(s, regexDelimiter)` | → list; e.g. `split('abc2def3ghi7','[0-9]')` |
| `join(delimiter, list)` | e.g. `join(', ', [$Child:SOXTask/System Fields:Name$])` |

### Lists and numbers, incl. dates and currency where noted (p.377-379)
| Function | Notes |
|---|---|
| `count(list)` | any list; number of items/objects |
| `sum(list)` | numbers, currency |
| `avg(list)`, `max(list)`, `min(list)` | numbers, currency, dates; also `max(1, 2, 3)` |
| `at(list, i)` | item at index; `-1` = last |
| `list(a, b, ...)` | build a list |
| `append(list, a, b, ...)`, `remove(list, a, ...)` | `remove` drops all occurrences |
| `round(n)`, `round(n, places)` | max 8 places; per item on a list. Round before `sum` of decimals |
| `sqrt(n)`, `square(n)` | per item on a list |

### Dates (p.379-381)
`add_days(d, n)`, `add_months(d, n)`, `add_years(d, n)`, `end_of_month(d)`, `end_of_quarter(d)`, `end_of_year(d)`
(all apply per item to a list of dates), `today()`, `tomorrow()`, `yesterday()`. Plus `[$TODAY$]`, `[$DaysFromNow/...$]`.

### Currency (p.381-382)
`currency(amount, 'CODE'[, exRate])`, `base_amount_of(c)`, `base_code_of(c)`, `local_amount_of(c)`,
`local_code_of(c)`, `ex_rate_of(c)`, `system_ex_rate_of('CODE'[, date])`. Arithmetic on currency values converts
through the base currency: `currency(1500,'USD') + currency(150000.00,'JPY',0.01)` → 3000.00 USD.

### Conditions: if / elif / else / endif (p.382-386)
```
if (cond) then valueA
elif (cond2) then valueB      // elif optional, repeatable
else valueC                   // ALWAYS give an else (missing else -> "Insufficient information" error)
endif
```
Nestable. Condition-only functions/clauses: `exists(x)`, `contains(s, 'text')`, `regex(s, 'pattern')`,
`x in ('a','b')`, `in_group`, `matches_any`, `in_hierarchy`.
Guard aggregates of possibly-empty lists: `if exists(sum([$X$])) then sum([$X$]) else 0 endif`.

## 6. Testing and debugging (p.386-389)

- Publish, then test: **bulk run** as admin (watch In Queue / Error Count; email lists failures, first 100), a
  **Grid View** with the set fields for quick checks, then a Creation View and a Task View as a user.
- Errors are stored **on the object** and cleared when fixed. Each has an ID like `UJA0J1RX75PA-OP-11604`: search the
  first part in the aurora log for the stack trace.
- `Insufficient information` → an `if` without `else`, or a missing default.
- Turn `Enable Calculation Preview` off to isolate preview behaviour; `Always Recalculate on the Object Save = true`
  helps during development only.
- From workflows: *Run calculation* operation (Manual calculations only), placed **before** the validation that reads
  the result. In API tests, assert the set field after the transition (`test_run.py expect_fields`).
- **Set field blank after a gate passed** = the calculation never ran (a run always writes a value, e.g. `0`).
  Isolate it: bulk-run the calculation as admin. Value appears → the workflow is at fault (the Close action edit was
  not **published**, so new instances still run the old version — and the validation was missing too, since blank ≠ 0).
  Still blank → the calculation is not Enabled + **Published** (Save leaves it Draft), wrong object type/applicability,
  or registry *Platform > Calculation > Enabled* is false. Seen on TPR Open Milestones, 2026-10.

## 7. Recipes

| Need | Input Field operation(s) | Set Field expression |
|---|---|---|
| Count children in a state (e.g. open milestones) | `OpenMs`: Direct Child `TPRMilestone`, field `TPR-Ms:Status`, Filter By `TPR-Ms:Status` != `Done` | `if exists([$OpenMs$]) then count([$OpenMs$]) else 0 endif` |
| Count all children | `AllMs`: Direct Child, field `System Fields:Name` | `if exists([$AllMs$]) then count([$AllMs$]) else 0 endif` |
| Sum child amounts | `Loss`: Direct Child `LossImpact`, `OPSS-LossIm:Estimated Loss` | `if exists(sum([$Loss$])) then sum([$Loss$]) else currency(0.00,'USD') endif` |
| Latest child date | `Due`: Direct Child `SOXTask`, `OPSS-AI:Due Date` | `max([$Due$])` |
| Worst of three ratings | three Self inputs `C`,`I`,`A` | `if ([$C$]=='High' OR [$I$]=='High' OR [$A$]=='High') then 'High' elif (...) then 'Medium' else 'Low' endif` |
| Names of children as text | (none) | `join(', ', [$Child:SOXTask/System Fields:Name$])` |
| Days to due | (none) | `[$DaysFromNow/OPSS-Iss:Original Due Date$]` |

In the spec, describe calculations under `calculations:` (see `templates/solution-spec.example.yaml`); `verify_spec.py
--lint-only` checks expression syntax (brackets, quotes, if/else/endif balance, known function names, operation and
field references).
