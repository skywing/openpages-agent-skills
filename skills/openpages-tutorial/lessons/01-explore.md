# Lesson 01 - Explore the object model and create your test Process

**Time:** 45 min · **Changes OpenPages:** one Process object (your test data)

## Objectives
- Read the OpenPages object model: object types, system name vs label, field groups, parents and children.
- See how REST and the UI show the same thing.
- Create the test Process your exceptions will hang under.

## Concepts

**Object types.** Every record in OpenPages is an object of a type: Business Entity (`SOXBusEntity`), Process
(`SOXProcess`), Risk, Control, Issue (`SOXIssue`), Policy (`Policy`)... Each type has a **system name** (permanent,
used by APIs and files) and a **label** (what users see, can change). IBM's platform types start with `SOX` for history.

**Fields** live in **field groups**. REST and the spec name a custom field `"<Field Group>:<Field>"`, e.g.
`"PXKN-Exc:Status"`; system fields have bare names (`Name`, `Description`, `Resource ID`).

**Hierarchy.** Types are connected by relationships (parent → child). Each object has one **primary parent**, which
decides the folder it lives in and, with the role-based security model, who can see it. Most objects sit under a
Business Entity, directly or through other objects. Your Policy Exception will be a child of a Process, and the
Compensating Control a child of the Exception.

**Folders and names.** Objects are stored in folders under their type's root folder. Object names must be unique within
a folder; that matters for automatically created objects (lesson 10).

## Do

### 1. Look at the types from the command line (read-only)
```bash
./op op.py types --grep Process             # system name, label
./op op.py type SOXProcess --fields         # field groups and fields with data types
./op op.py rels SOXProcess                  # parents and children
./op op.py type Policy --fields
./op op.py rels Policy
```
Questions to answer from the output: what is the label of `SOXProcess`? Which field group holds a Process's
description fields? Which types can be parents of a Process?

### 2. Snapshot the schema (optional, read-only)
```bash
./op dump_schema.py --env shared-dev --only SOXProcess,Policy,SOXIssue,SOXTask
```
Writes `schema/shared-dev/` with `SCHEMA.md`: a readable summary you can keep open while you work.

### 3. The same in the UI
Log in to shared-dev. Open **Administration menu > Solution Configuration > Object Types** and open *Process*: compare
the Fields and Relationships tabs with step 1. Change nothing here.

### 4. Create your test Process
In the primary menu open the Business Entity your team uses for training (ask the environment owner which one), then
create a **Process** under it:
- Name: `KN Tutorial Process` (your code; this exact name unless you passed `--process` to `tutorial start`)
- Owner: **yourself** (in lesson 10 the questionnaire respondent is the asset owner)
- Fill whatever else the creation view requires.

Find it again from the command line:
```bash
./op op.py query "SELECT [Resource ID], [Name] FROM [SOXProcess] WHERE [Name] = 'KN Tutorial Process'"
```

## Check
```bash
./op tutorial check 1
```
Passes when exactly one Process with your name exists.

## Pitfalls
- REST cannot look objects up by folder path; scripts use the numeric id or `Type:Name` (the spec's
  `tests.fixtures.process` is `SOXProcess:KN Tutorial Process`).
- Query syntax needs brackets around type and field names, and `SELECT *` is not supported.
- If the query finds 2 objects, someone used your name: rename yours (and `--process` in a fresh `start`).

## Recap
1. Which is permanent: the system name or the label?
2. What does the primary parent decide?
3. How do you address the field `Status` in field group `PXKN-Exc` in REST?
