# SUCWD: Synthetic University Course and Workload Dataset

Made by Team Ctrl+Z Burnout for the Academic Decision Simulator. **Everything here is synthetic.** No real student,
course, or university is described, so there are no privacy or consent limits.

**License:** data under CC BY 4.0, generation script (`../data_generation/generate_sucwd.py`) under MIT.

Regenerate (same seed gives identical files): `python data_generation/generate_sucwd.py [--seed N]`

| File | Rows | What it holds |
|---|---|---|
| `course_catalog.csv` | 120 | 6 departments (CS, ENG, MATH, BIO, BUS, HUM) x 20 courses: id, name, level 1-4, credits, terms offered (Fall / Spring), weekly hours, prerequisite text, meeting slot, difficulty, reading load, description |
| `prerequisites.csv` | ~220 | One row per link: `course_id, requires_id, link_type (prerequisite / corequisite), group_id`. Rows with the same `group_id` are alternatives (**either/or**). Different groups are all required. Chains reach 4+ courses. Co-requisites link a lab or workshop to its lecture |
| `workload_estimates.csv` | 600 | For each course and each component (lecture, reading, assignments, lab, exam_prep): `low, typical, high` hours per week. Built from the rule of thumb of about 2 outside hours per class hour, scaled by course type (programming, lab and project courses are heavier) |
| `student_terms.csv` | 2,000 | Anonymous generated student semesters: courses taken, credits, total weekly hours, heavy-course count, `outcome` (completed / struggled / withdrew). Risk of a bad outcome rises with weekly hours and heavy courses |

## How the app uses each table
- **Catalog + prerequisites:** the rule checker (prerequisites, either/or, co-requisites, terms, meeting conflicts). The LLM never decides these.
- **Workload:** weekly-hours totals, the "Why this course?" breakdown and the user's own weekly-hours limit.
- **Student terms:** the burnout-risk estimate shown on every draft (share of similar generated semesters that ended in struggling or withdrawing).

## Limits
Hours and outcomes are generated from simple rules, so burnout risk shows the *shape* of the idea, not real student behaviour.
Do not use it for real advising or for claims about real students.
