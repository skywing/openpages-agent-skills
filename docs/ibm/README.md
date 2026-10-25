# IBM documentation (not in git)

IBM's manuals are IBM copyright and large, so they are git-ignored. Download them into this folder:

| File | Source | Used for |
|---|---|---|
| `op_ 9.2.x_administrators_guide.pdf` | IBM OpenPages 9.2.x documentation, Administrator's Guide (PDF) | object types, fields, workflows, calculations (ch. 14, printed pp. 348-389), ObjectManager, migration |
| `op_user_guide.pdf` | IBM OpenPages 9.2.x documentation, User Guide (PDF) | questionnaire templates and programs |
| `admin-guide-calculations-p346-389.txt` | local extract: `pdftotext -layout -f <first> -l <last> "op_ 9.2.x_administrators_guide.pdf" ...` | source for `skills/openpages-solutions/references/calculations.md` |

Online: https://www.ibm.com/docs/en/openpages/9.2.x
The skill's `references/*.md` are our own notes with page citations, so the skill works without these files.
