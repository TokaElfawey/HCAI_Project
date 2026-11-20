#!/usr/bin/env python3
"""Generate the Synthetic University Course and Workload Dataset (SUCWD).

Team Ctrl+Z Burnout - Academic Decision Simulator.
Scripts: MIT License.  Generated data: CC BY 4.0.  No real person or university is described.

Output (four linked tables, written to ../data by default):
    course_catalog.csv     120 courses, 6 departments, level, credits, terms offered, meeting slot
    prerequisites.csv      prerequisite / co-requisite links, with either/or groups
    workload_estimates.csv weekly hours per component as a (low, typical, high) range
    student_terms.csv      2,000 anonymous generated "student semesters" with an outcome

Run:  python generate_sucwd.py            (same seed -> identical files)
      python generate_sucwd.py --seed 7   (a different synthetic university)
Only the Python standard library is used.
"""
import argparse
import csv
import math
import os
import random

DEPARTMENTS = {
    "CS": "Computer Science",
    "ENG": "Engineering",
    "MATH": "Mathematics",
    "BIO": "Biology",
    "BUS": "Business",
    "HUM": "Humanities",
}

# Per department: names for level 1 (5 courses), level 2 (4), level 3 (4), level 4 (5).
# Level 2 and 3 also get an automatic companion course (index 5) taken together with index 4
# (a laboratory or a workshop), linked by a co-requisite.  Tuple = (name, topics, kind).
# kind: lecture | programming | lab | reading | project | seminar
CURRICULUM = {
    "CS": [
        ("Introduction to Programming", "Python basics, loops and data structures", "programming"),
        ("Discrete Mathematics for Computing", "logic, sets, proofs and counting", "lecture"),
        ("Computing and Society", "ethics, privacy and the impact of software", "seminar"),
        ("Digital Logic Design", "gates, circuits and number systems", "lecture"),
        ("Web Development Fundamentals", "HTML, CSS and basic JavaScript", "programming"),
        ("Object-Oriented Programming", "classes, inheritance and design principles", "programming"),
        ("Data Structures", "lists, trees, graphs and hashing", "programming"),
        ("Computer Organization", "processors, memory and assembly language", "lecture"),
        ("Databases", "relational modelling, SQL and transactions", "lecture"),
        ("Algorithms", "design, analysis and complexity", "lecture"),
        ("Operating Systems", "processes, scheduling and file systems", "programming"),
        ("Software Engineering", "requirements, testing and teamwork", "project"),
        ("Computer Networks", "protocols, routing and network security basics", "lecture"),
        ("Machine Learning", "supervised learning, evaluation and neural networks", "programming"),
        ("Computer Security", "threats, cryptography and secure design", "lecture"),
        ("Distributed Systems", "consensus, replication and fault tolerance", "programming"),
        ("Human-Computer Interaction", "usability, prototyping and evaluation", "project"),
        ("Computer Science Capstone", "a team project from proposal to demo", "project"),
    ],
    "ENG": [
        ("Engineering Design Fundamentals", "teamwork, sketching and design process", "project"),
        ("Statics", "forces, equilibrium and structures", "lecture"),
        ("Engineering Graphics", "technical drawing and CAD basics", "project"),
        ("Introduction to Electrical Circuits", "voltage, current and basic circuits", "lecture"),
        ("Materials Science", "metals, polymers and material properties", "lecture"),
        ("Dynamics", "motion, energy and momentum of bodies", "lecture"),
        ("Thermodynamics", "energy, entropy and heat engines", "lecture"),
        ("Circuit Analysis", "network theorems, AC circuits and filters", "lecture"),
        ("Fluid Mechanics", "fluid statics, flow and pipe systems", "lecture"),
        ("Control Systems", "feedback, stability and controller design", "lecture"),
        ("Signals and Systems", "Fourier analysis and system response", "lecture"),
        ("Engineering Economics", "cost analysis and project evaluation", "lecture"),
        ("Heat Transfer", "conduction, convection and radiation", "lecture"),
        ("Mechatronics", "sensors, actuators and embedded control", "project"),
        ("Renewable Energy Systems", "solar, wind and storage design", "lecture"),
        ("Robotics", "kinematics, planning and robot programming", "programming"),
        ("Engineering Ethics and Safety", "professional responsibility and risk", "seminar"),
        ("Engineering Capstone", "design, build and test a real system", "project"),
    ],
    "MATH": [
        ("Calculus I", "limits, derivatives and applications", "lecture"),
        ("Calculus II", "integration, series and sequences", "lecture"),
        ("Linear Algebra", "vectors, matrices and eigenvalues", "lecture"),
        ("Introduction to Statistics", "descriptive statistics and inference basics", "lecture"),
        ("Mathematical Reasoning", "proof techniques and problem solving", "seminar"),
        ("Multivariable Calculus", "partial derivatives and multiple integrals", "lecture"),
        ("Differential Equations", "first and second order equations and systems", "lecture"),
        ("Probability", "random variables, distributions and expectation", "lecture"),
        ("Numerical Methods", "root finding, interpolation and error analysis", "programming"),
        ("Real Analysis", "convergence, continuity and rigorous calculus", "lecture"),
        ("Abstract Algebra", "groups, rings and fields", "lecture"),
        ("Mathematical Statistics", "estimation, hypothesis tests and regression", "lecture"),
        ("Optimization", "linear programming and convex methods", "programming"),
        ("Complex Analysis", "analytic functions and contour integrals", "lecture"),
        ("Topology", "open sets, continuity and compactness", "lecture"),
        ("Stochastic Processes", "Markov chains and random walks", "lecture"),
        ("Graph Theory", "paths, trees, colouring and networks", "lecture"),
        ("Mathematics Capstone", "an independent research problem", "project"),
    ],
    "BIO": [
        ("General Biology", "cells, genetics and the diversity of life", "lecture"),
        ("Introduction to Ecology", "populations, ecosystems and conservation", "lecture"),
        ("Biology of Cells", "cell structure, membranes and energy", "lecture"),
        ("Human Anatomy Basics", "body systems and their organisation", "reading"),
        ("Scientific Writing for Biology", "reading papers and writing reports", "seminar"),
        ("Genetics", "inheritance, mutation and gene expression", "lecture"),
        ("Microbiology", "bacteria, viruses and infection", "lecture"),
        ("Biochemistry", "proteins, enzymes and metabolism", "lecture"),
        ("Cell Biology", "organelles, signalling and the cell cycle", "lecture"),
        ("Molecular Biology", "DNA replication, transcription and translation", "lecture"),
        ("Physiology", "how organs and systems function", "lecture"),
        ("Evolutionary Biology", "selection, adaptation and phylogenies", "reading"),
        ("Immunology", "innate and adaptive immune responses", "lecture"),
        ("Neuroscience", "neurons, circuits and behaviour", "lecture"),
        ("Bioinformatics", "sequence analysis and biological databases", "programming"),
        ("Developmental Biology", "embryo patterning and differentiation", "lecture"),
        ("Biotechnology", "cloning, CRISPR and industrial applications", "lecture"),
        ("Biology Research Capstone", "a supervised mini research project", "project"),
    ],
    "BUS": [
        ("Principles of Management", "planning, organising and leading teams", "lecture"),
        ("Financial Accounting", "statements, ledgers and reporting", "lecture"),
        ("Microeconomics", "demand, supply and market structures", "lecture"),
        ("Business Communication", "emails, reports and presentations", "seminar"),
        ("Introduction to Marketing", "segmentation, branding and the marketing mix", "lecture"),
        ("Managerial Accounting", "budgets, costing and decision making", "lecture"),
        ("Macroeconomics", "growth, inflation and fiscal policy", "lecture"),
        ("Business Statistics", "sampling, regression and forecasting", "lecture"),
        ("Marketing Research", "surveys, experiments and consumer insight", "lecture"),
        ("Corporate Finance", "valuation, risk and capital structure", "lecture"),
        ("Operations Management", "process design, quality and inventory", "lecture"),
        ("Organizational Behavior", "motivation, culture and group dynamics", "reading"),
        ("Business Analytics", "dashboards, data cleaning and prediction", "programming"),
        ("Strategic Management", "competitive advantage and case analysis", "reading"),
        ("Entrepreneurship", "ideas, business models and pitching", "project"),
        ("Supply Chain Management", "logistics, sourcing and distribution", "lecture"),
        ("Business Ethics", "responsibility, governance and sustainability", "reading"),
        ("Business Capstone", "a consulting project for a case company", "project"),
    ],
    "HUM": [
        ("Introduction to Philosophy", "knowledge, reality and reasoning", "reading"),
        ("World History", "major civilisations and turning points", "reading"),
        ("Academic Writing", "argument, structure and citation", "seminar"),
        ("Introduction to Literature", "poetry, prose and drama", "reading"),
        ("Introduction to Linguistics", "sounds, words and sentence structure", "lecture"),
        ("Ethics", "major moral theories and applied cases", "reading"),
        ("Modern History", "revolutions, empires and nation states", "reading"),
        ("Creative Writing", "workshops in short fiction and poetry", "seminar"),
        ("Comparative Religion", "major traditions and how they are studied", "reading"),
        ("Political Theory", "justice, power and the state", "reading"),
        ("Literary Criticism", "schools of interpretation and close reading", "reading"),
        ("Cultural Studies", "media, identity and popular culture", "reading"),
        ("Philosophy of Mind", "consciousness, language and cognition", "reading"),
        ("Contemporary Debates", "structured debate on current questions", "seminar"),
        ("Gender and Society", "gender, institutions and social change", "reading"),
        ("Digital Humanities", "text mining and digital archives", "programming"),
        ("History of Ideas", "how concepts travel across eras", "reading"),
        ("Humanities Capstone", "a thesis-style independent essay", "project"),
    ],
}

# How the "outside class" work of each kind is split (reading, assignments, lab, exam_prep).
COMPONENT_SPLIT = {
    "lecture":     (0.30, 0.35, 0.00, 0.35),
    "programming": (0.10, 0.60, 0.15, 0.15),
    "lab":         (0.15, 0.25, 0.40, 0.20),
    "reading":     (0.55, 0.25, 0.00, 0.20),
    "project":     (0.15, 0.55, 0.10, 0.20),
    "seminar":     (0.45, 0.40, 0.00, 0.15),
}
# Heavier kinds need more than the base "2 hours outside per class hour".
KIND_MULTIPLIER = {"lecture": 1.00, "programming": 1.25, "lab": 1.20, "reading": 1.10, "project": 1.30, "seminar": 0.90}
DEFAULT_CREDITS = {"lecture": 3, "programming": 3, "lab": 4, "reading": 3, "project": 3, "seminar": 2}

CROSS_DEPARTMENT = {"CS": "MATH", "ENG": "MATH", "BIO": "MATH", "BUS": "MATH"}
DAY_SLOTS = ["8:00 AM", "10:00 AM", "12:00 PM", "2:00 PM", "4:00 PM"]
EVENING_SLOTS = ["5:00 PM", "6:00 PM", "7:00 PM", "8:00 PM"]
FRIDAY_SLOTS = ["10:00 AM", "12:00 PM", "2:00 PM"]


def course_id(dept, level, index):
    return f"{dept}{level}{index:02d}"


def build_courses(rng):
    """Return the list of course dicts (without schedule/prerequisite text yet)."""
    courses = []
    for dept, rows in CURRICULUM.items():
        cursor = 0
        for level, count in ((1, 5), (2, 4), (3, 4), (4, 5)):
            lecture_for_companion = None
            for index in range(1, count + 1):
                name, topics, kind = rows[cursor]
                cursor += 1
                credits = DEFAULT_CREDITS[kind]
                if level == 4 and index == 5:
                    credits = 4
                if dept in ("MATH",) and level == 1 and index <= 3:
                    credits = 4 if index == 1 else 3
                course = {
                    "course_id": course_id(dept, level, index), "course_name": name, "department": dept,
                    "level": level, "credits": credits, "kind": kind,
                    "topics": topics, "companion_of": None,
                }
                courses.append(course)
                if index == 4 and level in (2, 3):
                    lecture_for_companion = course
            if lecture_for_companion is not None:
                lab_like = dept in ("CS", "ENG", "BIO")
                lecture = lecture_for_companion
                suffix = "Laboratory" if lab_like else "Workshop"
                courses.append({
                    "course_id": course_id(dept, level, 5),
                    "course_name": f"{lecture['course_name']} {suffix}",
                    "department": dept, "level": level,
                    "credits": 4 if lab_like else 2,
                    "kind": "lab" if lab_like else "seminar",
                    "topics": f"hands-on practice that goes with {lecture['course_name']}",
                    "companion_of": lecture["course_id"],
                })
    # Terms offered (a companion is always offered when its lecture is).
    by_id = {c["course_id"]: c for c in courses}
    for c in courses:
        if c["companion_of"]:
            continue
        roll = rng.random()
        if c["level"] == 1:
            c["terms"] = "Fall/Spring" if roll < 0.70 else ("Fall" if roll < 0.85 else "Spring")
        else:
            c["terms"] = "Fall/Spring" if roll < 0.40 else ("Fall" if roll < 0.70 else "Spring")
    for c in courses:
        if c["companion_of"]:
            c["terms"] = by_id[c["companion_of"]]["terms"]
    return courses


def build_prerequisites(courses, rng):
    """Return rows (course_id, requires_id, link_type, group_id). Prerequisites always point to a
    lower level, so the graph has no cycles; a co-requisite points to a same-level lecture."""
    by_id = {c["course_id"]: c for c in courses}
    rows = []
    for c in courses:
        dept, level = c["department"], c["level"]
        if level == 1:
            continue
        group = 0

        def add(options, link_type="prerequisite"):
            nonlocal group
            group += 1
            for option in options:
                rows.append((c["course_id"], option, link_type, group))

        if c["companion_of"]:
            # A companion needs what its lecture needs, plus the lecture itself at the same time.
            lecture_id = c["companion_of"]
            lecture_groups = {}
            for row in [r for r in rows if r[0] == lecture_id and r[2] == "prerequisite"]:
                lecture_groups.setdefault(row[3], []).append(row[1])
            for options in lecture_groups.values():
                add(options)
            add([lecture_id], "corequisite")
            continue
        index = int(c["course_id"][-2:])
        previous = course_id(dept, level - 1, index)
        if previous not in by_id or by_id[previous]["companion_of"]:
            previous = course_id(dept, level - 1, 1)
        alternative_index = index % 4 + 1
        alternative = course_id(dept, level - 1, alternative_index)
        if rng.random() < 0.25 and alternative != previous and alternative in by_id:
            add(sorted([previous, alternative]))                  # either/or
        else:
            add([previous])
        if rng.random() < 0.55:                                    # a second, independent prerequisite
            other = rng.choice([k for k in range(1, 5) if k != index] or [1])
            second = course_id(dept, level - 1, other)
            if second in by_id and second != previous:
                add([second])
        cross_dept = CROSS_DEPARTMENT.get(dept)
        if cross_dept and rng.random() < 0.55:
            cross_level = min(level - 1, 2)
            first = course_id(cross_dept, cross_level, rng.randint(1, 4))
            if rng.random() < 0.4:
                second = course_id(cross_dept, cross_level, rng.randint(1, 4))
                add(sorted({first, second}))
            else:
                add([first])
    return sorted(set(rows))


def build_workload(courses):
    """Return {course_id: {component: (low, typical, high)}}."""
    workload = {}
    for c in courses:
        kind, credits, level = c["kind"], c["credits"], c["level"]
        lecture_hours = credits - (1 if kind == "lab" else 0)
        outside = 2.0 * credits * KIND_MULTIPLIER[kind] * (1 + 0.05 * (level - 1))
        reading, assignments, lab, exam = (round(outside * share, 2) for share in COMPONENT_SPLIT[kind])
        if kind == "lab":
            lab += 1.0                                          # the in-class laboratory hour
        typical = {"lecture": float(lecture_hours), "reading": reading, "assignments": assignments, "lab": lab, "exam_prep": exam}
        spread_high = 1.25 + 0.05 * (level - 1)
        workload[c["course_id"]] = {
            name: (value, value, value) if name == "lecture"
            else (round(value * 0.75, 1), round(value, 1), round(value * spread_high, 1))
            for name, value in typical.items()
        }
    return workload


def format_requirements(course_id_, rows):
    groups = {}
    for cid, option, link_type, group in rows:
        if cid == course_id_:
            groups.setdefault((link_type, group), []).append(option)
    if not groups:
        return "None"
    parts = []
    for (link_type, _), options in sorted(groups.items(), key=lambda item: item[0][1]):
        text = options[0] if len(options) == 1 else "(" + " OR ".join(options) + ")"
        parts.append(f"co-req {text}" if link_type == "corequisite" else text)
    return " AND ".join(parts)


def assign_labels_and_schedule(courses, workload, rng):
    by_id = {c["course_id"]: c for c in courses}
    totals = {cid: sum(v[1] for v in comps.values()) for cid, comps in workload.items()}
    ordered = sorted(totals.values())
    light_cut = ordered[int(len(ordered) * 0.25)]
    heavy_cut = ordered[int(len(ordered) * 0.80)]
    for c in courses:
        total = totals[c["course_id"]]
        c["weekly_study_hours"] = round(total, 1)
        c["difficulty_level"] = "Light" if total <= light_cut else ("Heavy" if total >= heavy_cut else "Moderate")
        reading = workload[c["course_id"]]["reading"][1]
        c["reading_load"] = "Low" if reading < 1.8 else ("Medium" if reading < 3.2 else "High")
        roll = rng.random()
        if c["credits"] <= 2 or c["companion_of"]:
            roll = rng.choice([0.9, 0.97, 0.2])
        while True:
            if roll < 0.35:
                slot = f"Mon/Wed {rng.choice(DAY_SLOTS)}"
            elif roll < 0.70:
                slot = f"Tue/Thu {rng.choice(DAY_SLOTS)}"
            elif roll < 0.78:
                slot = f"Fri {rng.choice(FRIDAY_SLOTS)}"
            else:
                slot = f"Evening {rng.choice(EVENING_SLOTS)}"
            # A laboratory must never sit in exactly the same slot as its own lecture.
            if not c["companion_of"] or slot != by_id[c["companion_of"]].get("schedule_slot"):
                break
            roll = rng.random()
        c["schedule_slot"] = slot
        c["description"] = (
            f"{c['course_name']}: {c['topics']}. A level-{c['level']} {DEPARTMENTS[c['department']].lower()} "
            f"course ({c['credits']} credits)."
        )


def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))


def build_student_terms(courses, workload, rng, count=2000):
    """Generate anonymous student semesters. Burnout risk rises with weekly hours and with the number
    of heavy courses; the app then *estimates* risk from these rows instead of using a fixed rule."""
    typical = {c["course_id"]: sum(v[1] for v in workload[c["course_id"]].values()) for c in courses}
    rows = []
    depts = list(DEPARTMENTS)
    for number in range(1, count + 1):
        term = rng.choice(["Fall", "Spring"])
        year = rng.choices([1, 2, 3, 4], weights=[28, 28, 24, 20])[0]
        major = rng.choice(depts)
        target = rng.choices([9, 12, 15, 18], weights=[10, 35, 40, 15])[0]
        pool = [c for c in courses if term in c["terms"].split("/") and c["level"] <= year + 1]
        weights = []
        for c in pool:
            w = 3.0 if c["level"] == year else (2.0 if c["level"] == year - 1 else 1.0)
            w *= 3.0 if c["department"] == major else (1.5 if c["department"] == "MATH" else 1.0)
            weights.append(w)
        chosen, credits, tries = [], 0, 0
        while credits < target and tries < 60:
            tries += 1
            pick = rng.choices(pool, weights=weights)[0]
            if pick in chosen or credits + pick["credits"] > target + 1:
                continue
            chosen.append(pick)
            credits += pick["credits"]
        hours = sum(typical[c["course_id"]] for c in chosen) * min(1.25, max(0.8, rng.gauss(1.0, 0.10)))
        heavy = sum(1 for c in chosen if c["difficulty_level"] == "Heavy")
        p_bad = min(0.9, 0.04 + 0.80 * sigmoid((hours - 52.0) / 5.0) + 0.02 * heavy)
        roll = rng.random()
        if roll < p_bad:
            outcome = "withdrew" if rng.random() < 0.35 else "struggled"
        else:
            outcome = "completed"
        rows.append({
            "student_term_id": f"ST{number:04d}", "term": term, "year_level": year,
            "course_ids": "|".join(sorted(c["course_id"] for c in chosen)),
            "num_courses": len(chosen), "total_credits": credits,
            "total_weekly_hours": round(hours, 1), "heavy_courses": heavy, "outcome": outcome,
        })
    return rows


def write_csv(path, fieldnames, rows):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--out", default=os.path.join(here, "..", "data"))
    parser.add_argument("--student-terms", type=int, default=2000)
    args = parser.parse_args()
    rng = random.Random(args.seed)
    os.makedirs(args.out, exist_ok=True)

    courses = build_courses(rng)
    links = build_prerequisites(courses, rng)
    workload = build_workload(courses)
    assign_labels_and_schedule(courses, workload, rng)
    terms = build_student_terms(courses, workload, rng, args.student_terms)

    catalog_rows = []
    for c in courses:
        catalog_rows.append({
            "course_id": c["course_id"], "course_name": c["course_name"], "department": c["department"],
            "level": c["level"], "credits": c["credits"], "terms_offered": c["terms"],
            "weekly_study_hours": c["weekly_study_hours"],
            "prerequisites": format_requirements(c["course_id"], links),
            "schedule_slot": c["schedule_slot"], "difficulty_level": c["difficulty_level"],
            "reading_load": c["reading_load"], "description": c["description"],
        })
    write_csv(os.path.join(args.out, "course_catalog.csv"), list(catalog_rows[0]), catalog_rows)
    write_csv(os.path.join(args.out, "prerequisites.csv"), ["course_id", "requires_id", "link_type", "group_id"],
              [dict(zip(("course_id", "requires_id", "link_type", "group_id"), row)) for row in links])
    workload_rows = []
    for c in courses:
        for component, (low, typical, high) in workload[c["course_id"]].items():
            workload_rows.append({"course_id": c["course_id"], "component": component, "low": low, "typical": typical, "high": high})
    write_csv(os.path.join(args.out, "workload_estimates.csv"), ["course_id", "component", "low", "typical", "high"], workload_rows)
    write_csv(os.path.join(args.out, "student_terms.csv"), list(terms[0]), terms)

    outcomes = {name: sum(1 for t in terms if t["outcome"] == name) for name in ("completed", "struggled", "withdrew")}
    either_or = len({(r[0], r[3]) for r in links if sum(1 for x in links if x[0] == r[0] and x[3] == r[3]) > 1})
    print(f"courses: {len(courses)} | prerequisite links: {len(links)} (either/or groups: {either_or}) | "
          f"workload rows: {len(workload_rows)} | student terms: {len(terms)} {outcomes}")


if __name__ == "__main__":
    main()
