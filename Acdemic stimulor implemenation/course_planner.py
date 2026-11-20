import copy
import csv
import json
import os
import re
from datetime import datetime, timezone

import streamlit as st

CREDIT_CAP = 18
DEPARTMENTS = {
    "CS": "Computer Science", "ENG": "Engineering", "MATH": "Mathematics",
    "BIO": "Biology", "BUS": "Business", "HUM": "Humanities",
}
ALL_DEPARTMENTS = list(DEPARTMENTS)
DAY_NAMES = {"Mon": "Monday", "Tue": "Tuesday", "Wed": "Wednesday", "Thu": "Thursday", "Fri": "Friday"}
REQUIRED_COLUMNS = {"course_id", "course_name", "department", "level", "credits", "terms_offered", "weekly_study_hours",
                    "prerequisites", "schedule_slot", "difficulty_level", "reading_load", "description"}
WORKLOAD_COMPONENTS = ["lecture", "reading", "assignments", "lab", "exam_prep"]
ERROR_TYPES = ["Wrong prerequisite", "Wrong or conflicting time", "Does not count for my track", "Workload looks wrong", "Other"]
RATING_TAGS = ["Too heavy", "Too light", "Bad meeting times", "Missing a course I need", "Other"]
HOURS_STEP = 5
MIN_HOURS_LIMIT, MAX_HOURS_LIMIT = 15, 70

# Presets. "completed_levels" means "every course of that department at those levels" so the presets
# stay valid when the synthetic catalog is regenerated.
PRESETS = {
    "Lucía (ADHD, No 8am, Max 15)": {
        "max_credits": 15, "max_weekly_hours": 40, "max_heavy_courses": 8, "term": "Fall",
        "no_8am": True, "no_friday": True, "evening_only": False, "low_reading_only": False,
        "departments": ["CS", "MATH", "HUM"], "completed_courses": ["CS101", "MATH101"],
    },
    "Samuel (Dyslexia, Evening, Max 12)": {
        "max_credits": 12, "max_weekly_hours": 30, "max_heavy_courses": 2, "term": "Fall",
        "no_8am": True, "no_friday": True, "evening_only": True, "low_reading_only": True,
        "departments": list(ALL_DEPARTMENTS), "completed_courses": ["CS101", "CS102", "MATH101", "HUM103"],
    },
    "Nour (Senior, Max 18)": {
        "max_credits": 18, "max_weekly_hours": 55, "max_heavy_courses": 2, "term": "Fall",
        "no_8am": False, "no_friday": False, "evening_only": False, "low_reading_only": False,
        "departments": ["CS", "MATH"],
        "completed_levels": {"CS": [1, 2], "MATH": [1, 2], "HUM": [1]},
    },
}


def parse_course_meetings(schedule_slot):
    time_match = re.search(r"(\d{1,2}):(\d{2})\s*(AM|PM)", schedule_slot, flags=re.IGNORECASE)
    if not time_match:
        raise ValueError(f"Unrecognized course meeting time: {schedule_slot}")
    hour = int(time_match.group(1))
    minute = int(time_match.group(2))
    meridiem = time_match.group(3).upper()
    if not 1 <= hour <= 12 or minute not in (0, 30):
        raise ValueError(f"Invalid course meeting time: {schedule_slot}")
    start_hour = hour % 12 + (12 if meridiem == "PM" else 0)
    prefix = schedule_slot[:time_match.start()]
    abbreviations = re.findall(r"\b(?:Mon|Tue|Wed|Thu|Fri)\b", prefix)
    if not abbreviations:
        if "evening" in prefix.lower():
            return {("Evening", start_hour, minute)}
        raise ValueError(f"Unrecognized course meeting days: {schedule_slot}")
    return {(DAY_NAMES[day], start_hour, minute) for day in abbreviations}


def _read_csv(path):
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Data file was not found: {path}. Run data_generation/generate_sucwd.py to create it.")
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


class BurnoutModel:
    """Estimates burnout risk from the synthetic student-term table (SUCWD table 4).

    Risk = share of similar generated student semesters (similar weekly hours and heavy-course count)
    whose outcome was 'struggled' or 'withdrew'. It is an estimate from synthetic data, never advice."""

    def __init__(self, rows):
        self.rows = [(float(r["total_weekly_hours"]), int(r["heavy_courses"]), r["outcome"] != "completed") for r in rows]

    @classmethod
    def load(cls, path):
        if not os.path.isfile(path):
            return cls([])
        return cls(_read_csv(path)[1])

    def estimate(self, hours, heavy_courses):
        if not self.rows:
            return {"level": "Unknown", "rate": None, "n": 0}
        for hour_band, heavy_band in ((3, 1), (5, 2), (8, 99)):
            similar = [bad for h, hv, bad in self.rows if abs(h - hours) <= hour_band and abs(hv - heavy_courses) <= heavy_band]
            if len(similar) >= 30:
                break
        if not similar:
            return {"level": "Unknown", "rate": None, "n": 0}
        rate = sum(similar) / len(similar)
        level = "Low" if rate < 0.20 else ("Medium" if rate < 0.45 else "High")
        return {"level": level, "rate": rate, "n": len(similar)}


class CoursePlanner:
    def __init__(self, state_key="academic_simulator_planner", catalog_path=None, data_dir=None, feedback_path=None):
        self.state_key = f"{state_key}_course_planner_state"
        base = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = data_dir or os.path.join(base, "data")
        self.catalog_path = catalog_path or os.path.join(self.data_dir, "course_catalog.csv")
        self.feedback_path = feedback_path or os.path.join(self.data_dir, "feedback_log.jsonl")
        self.courses = self._load_catalog(self.catalog_path)
        self.course_by_id = {course["course_id"]: course for course in self.courses}
        self._load_prerequisites(os.path.join(self.data_dir, "prerequisites.csv"))
        self._load_workload(os.path.join(self.data_dir, "workload_estimates.csv"))
        self.burnout = BurnoutModel.load(os.path.join(self.data_dir, "student_terms.csv"))
        self.presets = {name: self._resolve_preset(spec) for name, spec in PRESETS.items()}
        first_preset = next(iter(self.presets))
        if self.state_key not in st.session_state:
            st.session_state[self.state_key] = {
                "constraints": copy.deepcopy(self.presets[first_preset]),
                "locked_courses": [],
                "rejected_courses": {},
                "drafts": None,
                "selected_plan": None,
                "onboarding_stage": 1,
                "history": [],
                "redo": [],
                "feedback": [],
                "draft_stats": {"generated": 0, "overloaded": 0},
                "notice": "",
            }
        self.state = st.session_state[self.state_key]
        preset_key = f"{self.state_key}_planner_preset"
        preset_initialized_key = f"{self.state_key}_planner_preset_initialized"
        preset_sync_key = f"{self.state_key}_planner_preset_sync"
        if not st.session_state.get(preset_initialized_key) or st.session_state.get(preset_sync_key):
            st.session_state[preset_key] = self._matching_preset()
            st.session_state[preset_initialized_key] = True
            st.session_state[preset_sync_key] = False
        if not self.state["history"]:
            self._checkpoint("Initial planner state")

    # ------------------------------------------------------------------ data loading
    @staticmethod
    def _load_catalog(path):
        fieldnames, rows = _read_csv(path)
        missing = REQUIRED_COLUMNS - set(fieldnames)
        if missing:
            raise ValueError(f"Course catalog is missing required columns: {', '.join(sorted(missing))}")
        courses, seen_ids = [], set()
        for line_number, row in enumerate(rows, start=2):
            course_id = row["course_id"].strip()
            if not course_id or course_id in seen_ids:
                raise ValueError(f"Course catalog has a missing or duplicate course ID on line {line_number}.")
            try:
                credits = int(row["credits"])
                level = int(row["level"])
                study_hours = float(row["weekly_study_hours"])
                meetings = parse_course_meetings(row["schedule_slot"])
            except (TypeError, ValueError) as error:
                raise ValueError(f"Invalid course record on line {line_number}: {error}") from error
            if credits <= 0 or study_hours < 0:
                raise ValueError(f"Course record on line {line_number} has invalid credits or study hours.")
            course = {key: (value or "").strip() for key, value in row.items()}
            course.update({
                "course_id": course_id, "credits": credits, "level": level, "weekly_study_hours": study_hours,
                "meetings": meetings, "terms": [term.strip() for term in row["terms_offered"].split("/")],
                "prerequisite_groups": [], "workload": {},
            })
            courses.append(course)
            seen_ids.add(course_id)
        if not courses:
            raise ValueError("The course catalog contains no courses.")
        return courses

    def _load_prerequisites(self, path):
        _, rows = _read_csv(path)
        groups = {}
        for row in rows:
            for key in ("course_id", "requires_id"):
                if row[key] not in self.course_by_id:
                    raise ValueError(f"prerequisites.csv mentions an unknown course: {row[key]}")
            group = groups.setdefault(row["course_id"], {}).setdefault(int(row["group_id"]), {"type": row["link_type"], "options": []})
            group["options"].append(row["requires_id"])
        for course_id, by_group in groups.items():
            self.course_by_id[course_id]["prerequisite_groups"] = [by_group[key] for key in sorted(by_group)]

    def _load_workload(self, path):
        _, rows = _read_csv(path)
        for row in rows:
            course = self.course_by_id.get(row["course_id"])
            if course is None:
                raise ValueError(f"workload_estimates.csv mentions an unknown course: {row['course_id']}")
            course["workload"][row["component"]] = (float(row["low"]), float(row["typical"]), float(row["high"]))
        for course in self.courses:
            course["hours_low"] = sum(v[0] for v in course["workload"].values())
            course["hours_high"] = sum(v[2] for v in course["workload"].values())

    def _resolve_preset(self, spec):
        resolved = {key: copy.deepcopy(value) for key, value in spec.items() if key != "completed_levels"}
        completed = list(spec.get("completed_courses", []))
        for department, levels in spec.get("completed_levels", {}).items():
            completed += [c["course_id"] for c in self.courses if c["department"] == department and c["level"] in levels]
        resolved["completed_courses"] = sorted({cid for cid in completed if cid in self.course_by_id})
        return resolved

    # ------------------------------------------------------------------ history (Ladder level 3)
    def _snapshot(self, label):
        return {"label": label, **{key: copy.deepcopy(self.state[key]) for key in
                                   ("constraints", "locked_courses", "rejected_courses", "drafts", "selected_plan")}}

    def _restore(self, snapshot):
        for key in ("constraints", "locked_courses", "rejected_courses", "drafts", "selected_plan"):
            self.state[key] = copy.deepcopy(snapshot[key])
        st.session_state[f"{self.state_key}_planner_preset_sync"] = True

    CONSTRAINT_KEYS = ("max_credits", "max_weekly_hours", "max_heavy_courses", "term", "no_8am", "no_friday",
                       "evening_only", "low_reading_only")

    def _matching_preset(self):
        constraints = self.state["constraints"]
        for name, preset in self.presets.items():
            if (all(constraints.get(key) == preset[key] for key in self.CONSTRAINT_KEYS)
                    and set(constraints.get("departments", [])) == set(preset["departments"])
                    and set(constraints["completed_courses"]) == set(preset["completed_courses"])):
                return name
        return "Custom"

    def _checkpoint(self, label):
        self.state["history"].append(self._snapshot(label))
        if len(self.state["history"]) > 50:
            self.state["history"].pop(0)
        self.state["redo"].clear()

    def undo(self):
        if len(self.state["history"]) < 2:
            return False
        current = self.state["history"].pop()
        self.state["redo"].append(current)
        self._restore(self.state["history"][-1])
        return True

    def redo(self):
        if not self.state["redo"]:
            return False
        snapshot = self.state["redo"].pop()
        self.state["history"].append(copy.deepcopy(snapshot))
        self._restore(snapshot)
        return True

    # ------------------------------------------------------------------ rules (deterministic, never the LLM)
    @staticmethod
    def prerequisites_met(course, completed):
        return all(any(option in completed for option in group["options"])
                   for group in course["prerequisite_groups"] if group["type"] == "prerequisite")

    @staticmethod
    def corequisites_met(course, completed, plan_ids):
        return all(any(option in completed or option in plan_ids for option in group["options"])
                   for group in course["prerequisite_groups"] if group["type"] == "corequisite")

    def _course_fits(self, course, constraints):
        completed = set(constraints["completed_courses"])
        if constraints["no_8am"] and any(hour == 8 for _, hour, _ in course["meetings"]):
            return False
        if constraints["no_friday"] and any(day == "Friday" for day, _, _ in course["meetings"]):
            return False
        if constraints["evening_only"] and not course["schedule_slot"].lower().startswith("evening"):
            return False
        if constraints["low_reading_only"] and course["reading_load"].lower() == "high":
            return False
        if course["department"] not in constraints.get("departments", ALL_DEPARTMENTS):
            return False
        if constraints.get("term") and constraints["term"] not in course["terms"]:
            return False
        return self.prerequisites_met(course, completed)

    @staticmethod
    def _plan_conflicts(course, occupied_meetings):
        return not course["meetings"].isdisjoint(occupied_meetings)

    @staticmethod
    def plan_totals(plan):
        return {"credits": sum(c["credits"] for c in plan), "hours": round(sum(c["weekly_study_hours"] for c in plan), 1),
                "heavy": sum(1 for c in plan if c["difficulty_level"] == "Heavy")}

    def plan_risk(self, plan):
        totals = self.plan_totals(plan)
        return self.burnout.estimate(totals["hours"], totals["heavy"])

    @staticmethod
    def _round_robin(courses):
        by_department = {}
        for course in sorted(courses, key=lambda c: (c["level"], c["course_id"])):
            by_department.setdefault(course["department"], []).append(course)
        ordered = []
        while any(by_department.values()):
            for department in sorted(by_department):
                if by_department[department]:
                    ordered.append(by_department[department].pop(0))
        return ordered

    def _make_drafts(self, constraints=None, locked_courses=None, rejected_courses=None):
        constraints = self.state["constraints"] if constraints is None else constraints
        locked_courses = self.state["locked_courses"] if locked_courses is None else locked_courses
        rejected_courses = self.state["rejected_courses"] if rejected_courses is None else rejected_courses
        if constraints["max_credits"] > CREDIT_CAP:
            return {"status": "handover", "message": f"Requests over {CREDIT_CAP} credits need a human Academic Advisor.", "plans": {}}
        completed = set(constraints["completed_courses"])
        hours_limit = constraints.get("max_weekly_hours") or MAX_HOURS_LIMIT * 10
        heavy_limit = constraints.get("max_heavy_courses", 99)
        eligible = [c for c in self.courses if c["course_id"] not in completed and c["course_id"] not in rejected_courses
                    and self._course_fits(c, constraints)]
        eligible_by_id = {c["course_id"]: c for c in eligible}
        if any(course_id not in eligible_by_id for course_id in locked_courses):
            return {"status": "invalid_locks", "message": "A locked course no longer meets the selected constraints or prerequisite requirements. Unlock it or update the constraints.", "plans": {}}
        locked = [eligible_by_id[course_id] for course_id in locked_courses]
        locked_meetings, locked_credits = set(), 0
        for course in locked:
            if self._plan_conflicts(course, locked_meetings):
                return {"status": "invalid_locks", "message": f"Locked course {course['course_id']} conflicts with another locked course.", "plans": {}}
            locked_meetings.update(course["meetings"])
            locked_credits += course["credits"]
        if locked_credits > constraints["max_credits"]:
            return {"status": "invalid_locks", "message": "Locked courses exceed the selected credit limit. Unlock a course or raise the limit.", "plans": {}}
        locked_ids = {c["course_id"] for c in locked}
        for course in locked:
            if not self.corequisites_met(course, completed, locked_ids):
                needed = ", ".join(o for g in course["prerequisite_groups"] if g["type"] == "corequisite" for o in g["options"])
                return {"status": "invalid_locks", "message": f"{course['course_id']} must be taken together with {needed}. Lock that course too, or unlock {course['course_id']}.", "plans": {}}
        if not eligible:
            return {"status": "empty", "message": "No courses match all current constraints and completed-course prerequisites.", "plans": {}}
        pool = [c for c in eligible if c["course_id"] not in locked_courses]

        def build(sorted_pool, requested_cap):
            plan = list(locked)
            ids = set(locked_ids)
            used_credits = locked_credits
            hours = sum(c["weekly_study_hours"] for c in plan)
            heavy = sum(1 for c in plan if c["difficulty_level"] == "Heavy")
            occupied = set(locked_meetings)
            plan_cap = min(constraints["max_credits"], max(locked_credits, requested_cap))
            added = True
            while added:                     # extra passes let a co-requisite follow the course it needs
                added = False
                for course in sorted_pool:
                    if course["course_id"] in ids:
                        continue
                    if (used_credits + course["credits"] > plan_cap or self._plan_conflicts(course, occupied)
                            or hours + course["weekly_study_hours"] > hours_limit
                            or heavy + (course["difficulty_level"] == "Heavy") > heavy_limit
                            or not self.corequisites_met(course, completed, ids)):
                        continue
                    plan.append(course)
                    ids.add(course["course_id"])
                    used_credits += course["credits"]
                    hours += course["weekly_study_hours"]
                    heavy += course["difficulty_level"] == "Heavy"
                    occupied.update(course["meetings"])
                    added = True
            return plan

        limit = constraints["max_credits"]
        lightest_target = min(limit, max(9, limit - 3))
        plans = {
            "Plan A: Lightest Workload": build(sorted(pool, key=lambda c: (c["weekly_study_hours"], c["course_id"])), lightest_target),
            "Plan B: Fastest Graduation": build(sorted(pool, key=lambda c: (-c["credits"], -c["level"], c["weekly_study_hours"], c["course_id"])), limit),
            "Plan C: Balanced Path": build(self._round_robin(pool), limit),
        }
        return {"status": "ok", "message": "", "plans": plans}

    def is_overloaded(self, plan, constraints=None):
        constraints = constraints or self.state["constraints"]
        return self.plan_totals(plan)["hours"] > constraints.get("max_weekly_hours", 10 ** 6)

    def _regenerate(self):
        self.state["drafts"] = self._make_drafts()
        if self.state["drafts"]["status"] == "ok":
            stats = self.state["draft_stats"]
            for plan in self.state["drafts"]["plans"].values():
                stats["generated"] += 1
                stats["overloaded"] += int(self.is_overloaded(plan))
        if self.state["selected_plan"]:
            title = self.state["selected_plan"]["title"]
            plan = self.state["drafts"]["plans"].get(title)
            self.state["selected_plan"] = {"title": title, "courses": plan} if plan is not None else None

    def apply_constraints(self, constraints):
        if not 6 <= constraints["max_credits"] <= 24:
            raise ValueError("The credit limit must be between 6 and 24.")
        if not MIN_HOURS_LIMIT <= constraints["max_weekly_hours"] <= MAX_HOURS_LIMIT:
            raise ValueError(f"The weekly-hours limit must be between {MIN_HOURS_LIMIT} and {MAX_HOURS_LIMIT}.")
        constraints = copy.deepcopy(constraints)
        constraints["completed_courses"] = sorted(set(constraints["completed_courses"]) & set(self.course_by_id))
        constraints["departments"] = [d for d in constraints.get("departments", ALL_DEPARTMENTS) if d in DEPARTMENTS] or list(ALL_DEPARTMENTS)
        self.state["constraints"] = constraints
        self._regenerate()
        self._checkpoint("Updated course planning constraints")
        st.session_state[f"{self.state_key}_planner_preset_sync"] = True

    def apply_preset(self, name):
        if name not in self.presets:
            raise ValueError(f"Unknown student preset: {name}")
        self.state["constraints"] = copy.deepcopy(self.presets[name])
        self._regenerate()
        self._checkpoint(f"Applied preset: {name}")

    def generate(self):
        self._regenerate()
        self._checkpoint("Generated course drafts")

    def toggle_lock(self, course_id):
        if course_id in self.state["locked_courses"]:
            self.state["locked_courses"].remove(course_id)
            action = "Unlocked"
        else:
            if course_id not in self.course_by_id or course_id in self.state["rejected_courses"]:
                return False
            self.state["locked_courses"].append(course_id)
            action = "Locked"
        self._regenerate()
        self._checkpoint(f"{action} {course_id}")
        return True

    def reject_course(self, course_id, reason="Rejected by student"):
        if course_id not in self.course_by_id:
            return False
        self.state["rejected_courses"][course_id] = reason
        if course_id in self.state["locked_courses"]:
            self.state["locked_courses"].remove(course_id)
        self._regenerate()
        self._checkpoint(f"Rejected {course_id}")
        return True

    def restore_course(self, course_id):
        if course_id not in self.state["rejected_courses"]:
            return False
        self.state["rejected_courses"].pop(course_id)
        self._regenerate()
        self._checkpoint(f"Restored {course_id}")
        return True

    def select_plan(self, title):
        if not self.state["drafts"] or title not in self.state["drafts"]["plans"]:
            return False
        self.state["selected_plan"] = {"title": title, "courses": copy.deepcopy(self.state["drafts"]["plans"][title])}
        self._checkpoint(f"Selected {title}")
        return True

    def clear_selection(self):
        if self.state["selected_plan"] is None:
            return
        self.state["selected_plan"] = None
        self._checkpoint("Cleared selected plan")

    # ------------------------------------------------------------------ feedback (Ladder level 4)
    def _log_feedback(self, entry):
        entry = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"), **entry}
        self.state["feedback"].append(entry)
        try:                                   # the log is a convenience; the app works without it
            with open(self.feedback_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass
        return entry

    def report_course_error(self, course_id, issue, note=""):
        """Level 4: the student reports a problem with one course. The course leaves the drafts at once,
        the drafts are rebuilt, and the report is logged for review. Undo reverses the re-plan."""
        if course_id not in self.course_by_id or issue not in ERROR_TYPES:
            return "That report could not be recorded."
        self._log_feedback({"kind": "error_report", "course_id": course_id, "issue": issue, "note": note.strip()[:500]})
        self.reject_course(course_id, reason=f"Reported: {issue}")
        message = f"Thanks. {course_id} was removed from your drafts and the plans were rebuilt. Your report was saved for review."
        if issue == "Wrong prerequisite":
            message += " Prerequisite waivers or corrections are decided by a human Academic Advisor, not by this tool."
        self.state["notice"] = message
        return message

    def rate_draft(self, title, rating, tags=(), note=""):
        """Level 4: the student rates a draft. 'Too heavy' / 'Too light' re-plan by moving the weekly-hours
        limit; other tags only point to the control the student can use. Undo reverses the re-plan."""
        if not 1 <= int(rating) <= 5:
            return "Please choose a rating from 1 to 5."
        tags = [tag for tag in tags if tag in RATING_TAGS]
        self._log_feedback({"kind": "draft_rating", "draft": title, "rating": int(rating), "tags": tags, "note": note.strip()[:500]})
        constraints = self.state["constraints"]
        old_limit = constraints["max_weekly_hours"]
        changes = []
        new_limit = old_limit
        if "Too heavy" in tags:
            new_limit = max(MIN_HOURS_LIMIT, old_limit - HOURS_STEP)
        elif "Too light" in tags:
            new_limit = min(MAX_HOURS_LIMIT, old_limit + HOURS_STEP)
        if new_limit != old_limit:
            constraints["max_weekly_hours"] = new_limit
            changes.append(f"weekly-hours limit {old_limit} → {new_limit}")
        advice = []
        if "Bad meeting times" in tags:
            advice.append("Use the time boxes (No 8:00 AM, No Friday, Evening only) to change meeting times.")
        if "Missing a course I need" in tags:
            advice.append("Restore a rejected course, or check the completed-course list and the department filter.")
        if changes:
            self._regenerate()
            self._checkpoint("Re-planned from feedback")
            st.session_state[f"{self.state_key}_planner_preset_sync"] = True
            message = f"Thanks. Re-planned with {', '.join(changes)}. You can Undo this."
        else:
            message = "Thanks, your rating was saved. No limits were changed."
        if advice:
            message += " " + " ".join(advice)
        self.state["notice"] = message
        return message

    def feedback_summary(self):
        entries = self.state["feedback"]
        ratings = [e["rating"] for e in entries if e["kind"] == "draft_rating"]
        stats = self.state["draft_stats"]
        return {
            "reports": sum(1 for e in entries if e["kind"] == "error_report"),
            "ratings": len(ratings),
            "average_rating": round(sum(ratings) / len(ratings), 1) if ratings else None,
            "drafts_generated": stats["generated"], "drafts_overloaded": stats["overloaded"],
            "overloaded_share": round(100 * stats["overloaded"] / stats["generated"]) if stats["generated"] else None,
        }

    # ------------------------------------------------------------------ explanations (Ladder level 2)
    def explain_prerequisites(self, course):
        completed = set(self.state["constraints"]["completed_courses"])
        lines = []
        for group in course["prerequisite_groups"]:
            options = " OR ".join(group["options"])
            if group["type"] == "corequisite":
                lines.append(f"Take together with {options} (co-requisite).")
            else:
                done = [o for o in group["options"] if o in completed]
                lines.append(f"Requires {options}: you completed {', '.join(done)} ✓")
        return lines or ["No prerequisites."]

    # ------------------------------------------------------------------ interface
    def _constraint_echo(self):
        c = self.state["constraints"]
        times = [text for flag, text in ((c["no_8am"], "no 8:00 AM"), (c["no_friday"], "no Friday"), (c["evening_only"], "evening only")) if flag]
        parts = [f"up to {c['max_credits']} credits", f"up to {c['max_weekly_hours']} hours/week",
                 ", ".join(times) if times else "any meeting time",
                 "low reading load" if c["low_reading_only"] else "any reading load",
                 f"{c['term']} term", "departments: " + ", ".join(c["departments"]),
                 f"{len(c['completed_courses'])} completed courses"]
        if c["max_heavy_courses"] < 8:
            parts.append(f"at most {c['max_heavy_courses']} heavy courses")
        return "Here's what I understood: " + "; ".join(parts) + "."

    def _render_data_panel(self):
        with st.expander("📊 Where the data comes from (and what it can't tell you)"):
            terms = len(self.burnout.rows)
            links = sum(len(c["prerequisite_groups"]) for c in self.courses)
            st.markdown(
                f"- **Source:** the synthetic SUCWD dataset made by our team: **{len(self.courses)} courses**, "
                f"**{links} prerequisite groups**, workload ranges for every course, and **{terms:,} generated student semesters**.\n"
                "- **It is synthetic.** No real students or university. Released under CC BY 4.0.\n"
                "- **Burnout risk** is the share of *similar generated* semesters where the student struggled or withdrew. "
                "It is a rough signal, not a prediction about you.\n"
                "- **It cannot** see real timetables, seat availability or your degree rules. Ask a human Academic Advisor.")

    def _render_ladder(self):
        with st.expander("🪜 HAI Principle Ladder: where User Control and Agency appears"):
            st.markdown(
                "1. **Inform:** 'Here's what I understood', the data-source panel and the can / cannot panel.\n"
                "2. **Explain:** 'Why this course?' shows the prerequisite path, the workload range and the burnout estimate.\n"
                "3. **Allow control:** Lock, Reject, Restore, Undo and Redo. Nothing is final until you select it.\n"
                "4. **Enable feedback:** 'Report an error' on each course and 'Rate this draft'. Both re-plan, and Undo reverses them.")

    def _render_onboarding(self):
        stage = self.state["onboarding_stage"]
        if stage == 1:
            st.info("👋 **Step 1 of 3 · The system does it.** Course plans are generated from the catalog, prerequisite data, and your limits. Nothing is final.")
            sample = self._make_drafts(copy.deepcopy(self.presets[next(iter(self.presets))]), [], {})
            if sample["status"] == "ok":
                sample_plan = sample["plans"]["Plan C: Balanced Path"]
                st.caption("Example balanced plan: " + (", ".join(c["course_id"] for c in sample_plan) or "No courses fit the example limits."))
            start_col, skip_col = st.columns(2)
            if start_col.button("Try it myself", type="primary", key=f"{self.state_key}_onboarding_try"):
                self.state["onboarding_stage"] = 2
                st.rerun()
            if skip_col.button("Skip guide", key=f"{self.state_key}_onboarding_skip"):
                self.state["onboarding_stage"] = 3
                st.rerun()
        elif stage == 2:
            st.success("🤝 **Step 2 of 3 · Co-pilot.** Choose a student preset or set your own limits. Then generate drafts and try lock, reject, Undo, and Redo. After that, rate a draft or report an error.")
            if st.button("Got it — open the planner", key=f"{self.state_key}_onboarding_done"):
                self.state["onboarding_stage"] = 3
                st.rerun()
        elif st.button("❓ Show planner guide", key=f"{self.state_key}_onboarding_again"):
            self.state["onboarding_stage"] = 1
            st.rerun()

    def _render_sidebar(self):
        with st.sidebar:
            st.divider()
            st.header("🎛️ Course Planning")
            undo_col, redo_col = st.columns(2)
            if undo_col.button("↩️ Undo", key=f"{self.state_key}_planner_undo", disabled=len(self.state["history"]) <= 1):
                self.undo()
                st.rerun()
            if redo_col.button("↪️ Redo", key=f"{self.state_key}_planner_redo", disabled=not self.state["redo"]):
                self.redo()
                st.rerun()
            st.subheader("👤 Student preset")
            preset = st.selectbox("Select a profile", ["Custom"] + list(self.presets), key=f"{self.state_key}_planner_preset")
            if st.button("Apply preset", key=f"{self.state_key}_apply_preset", disabled=preset == "Custom", use_container_width=True):
                self.apply_preset(preset)
                st.rerun()
            if self.state["locked_courses"]:
                st.subheader("🔒 Locked courses")
                for course_id in list(self.state["locked_courses"]):
                    course = self.course_by_id[course_id]
                    if st.button(f"Unlock {course_id}: {course['course_name']}", key=f"{self.state_key}_sidebar_unlock_{course_id}", use_container_width=True):
                        self.toggle_lock(course_id)
                        st.rerun()
            constraints = self.state["constraints"]
            with st.form(f"{self.state_key}_planner_constraints"):
                st.subheader("⚙️ Planning limits")
                max_credits = st.slider("Maximum credits (advisor review above 18)", 6, 24, value=constraints["max_credits"])
                max_weekly_hours = st.slider("My weekly hours limit (class + study)", MIN_HOURS_LIMIT, MAX_HOURS_LIMIT, value=constraints["max_weekly_hours"])
                max_heavy = st.number_input("Max heavy-workload courses", 0, 8, value=constraints["max_heavy_courses"])
                term = st.radio("Term", ["Fall", "Spring"], index=0 if constraints["term"] == "Fall" else 1, horizontal=True)
                departments = st.multiselect("Departments", ALL_DEPARTMENTS, default=constraints["departments"], format_func=lambda d: DEPARTMENTS[d])
                no_8am = st.checkbox("No 8:00 AM classes", value=constraints["no_8am"])
                no_friday = st.checkbox("No Friday classes", value=constraints["no_friday"])
                evening_only = st.checkbox("Evening classes only", value=constraints["evening_only"])
                low_reading_only = st.checkbox("Low reading load", value=constraints["low_reading_only"])
                completed_courses = st.multiselect("Courses already completed", sorted(self.course_by_id), default=constraints["completed_courses"],
                                                   format_func=lambda cid: f"{cid}: {self.course_by_id[cid]['course_name']}")
                if st.form_submit_button("Update limits and generate drafts", type="primary", use_container_width=True):
                    self.apply_constraints({
                        "max_credits": max_credits, "max_weekly_hours": max_weekly_hours, "max_heavy_courses": int(max_heavy),
                        "term": term, "departments": departments, "no_8am": no_8am, "no_friday": no_friday,
                        "evening_only": evening_only, "low_reading_only": low_reading_only, "completed_courses": completed_courses,
                    })
                    st.rerun()
            if self.state["rejected_courses"]:
                st.subheader("🚫 Rejected courses")
                for course_id, reason in sorted(self.state["rejected_courses"].items()):
                    course = self.course_by_id[course_id]
                    st.caption(reason)
                    if st.button(f"Restore {course_id}: {course['course_name']}", key=f"{self.state_key}_restore_{course_id}", use_container_width=True):
                        self.restore_course(course_id)
                        st.rerun()
            summary = self.feedback_summary()
            st.subheader("📣 Feedback so far")
            st.caption(f"Error reports: {summary['reports']} · Ratings: {summary['ratings']}"
                       + (f" (average {summary['average_rating']}/5)" if summary["average_rating"] else ""))
            if summary["overloaded_share"] is not None:
                st.caption(f"Drafts over your weekly-hours limit: {summary['drafts_overloaded']} of {summary['drafts_generated']} ({summary['overloaded_share']}%). Goal: 10% or less.")

    def _render_course_card(self, course, plan_index):
        course_id = course["course_id"]
        locked = course_id in self.state["locked_courses"]
        with st.container(border=True):
            st.markdown(f"**{course_id}: {course['course_name']}** {'🔒 Locked' if locked else ''}")
            st.caption(f"{DEPARTMENTS.get(course['department'], course['department'])} · Level {course['level']} · {course['credits']} credits · "
                       f"{course['weekly_study_hours']:g} hours/week · {course['difficulty_level']} · Reading: {course['reading_load']}")
            st.write(f"Schedule: {course['schedule_slot']}")
            with st.expander("Why this course?"):
                for line in self.explain_prerequisites(course):
                    st.write(f"- {line}")
                st.write(f"- It meets your time limits and is offered in the {self.state['constraints']['term']} term.")
                breakdown = ", ".join(f"{name.replace('_', ' ')} {course['workload'][name][1]:g}h" for name in WORKLOAD_COMPONENTS if name in course["workload"])
                st.write(f"- Weekly workload (typical): {breakdown}. Range {course['hours_low']:.0f} to {course['hours_high']:.0f} hours.")
                st.write(course["description"])
                st.caption(f"Source: course_catalog.csv, prerequisites.csv and workload_estimates.csv, record {course_id} (synthetic data).")
            lock_col, reject_col = st.columns(2)
            if lock_col.button("Unlock" if locked else "🔒 Lock", key=f"{self.state_key}_lock_{plan_index}_{course_id}", use_container_width=True):
                self.toggle_lock(course_id)
                st.rerun()
            if reject_col.button("✖ Reject", key=f"{self.state_key}_reject_{plan_index}_{course_id}", use_container_width=True):
                self.reject_course(course_id)
                st.rerun()
            with st.expander("⚠️ Report an error with this course"):
                with st.form(f"{self.state_key}_report_{plan_index}_{course_id}"):
                    issue = st.selectbox("What is wrong?", ERROR_TYPES)
                    note = st.text_input("Short note (optional, no personal data)", max_chars=200)
                    if st.form_submit_button("Send report and re-plan"):
                        self.report_course_error(course_id, issue, note)
                        st.rerun()

    def _render_rating(self, title, plan_index):
        with st.expander("⭐ Rate this draft"):
            with st.form(f"{self.state_key}_rate_{plan_index}"):
                rating = st.radio("How useful is this draft?", [1, 2, 3, 4, 5], index=2, horizontal=True,
                                  format_func=lambda n: "★" * n + f" ({n})")
                tags = st.multiselect("What should change? (optional)", RATING_TAGS)
                note = st.text_input("Short note (optional, no personal data)", max_chars=200, key=f"{self.state_key}_rate_note_{plan_index}")
                if st.form_submit_button("Send rating and re-plan"):
                    self.rate_draft(title, rating, tags, note)
                    st.rerun()

    def render(self):
        self._render_sidebar()
        st.header("📚 Course Planner")
        st.caption("Compare draft plans built from the synthetic SUCWD catalog. The simulator checks prerequisites, co-requisites, meeting-time conflicts, and your limits; it does not register courses.")
        self._render_onboarding()
        st.caption(self._constraint_echo())
        if self.state["notice"]:
            st.info(self.state["notice"])
            self.state["notice"] = ""
        with st.expander("ℹ️ What the planner can and cannot do"):
            st.markdown(f"- **It can:** generate up to three course drafts, check prerequisites and co-requisites, estimate weekly hours and burnout risk, and let you lock, reject, undo, redo, rate drafts and report errors.\n- **It cannot:** register courses, approve prerequisite waivers, or approve credit overloads above {CREDIT_CAP}. Contact a human Academic Advisor for exceptions.")
        self._render_data_panel()
        self._render_ladder()
        drafts = self.state["drafts"]
        if drafts is None:
            st.info("Set your planning limits in the sidebar, then generate your first course drafts.")
            if st.button("Generate drafts with current limits", type="primary", key=f"{self.state_key}_generate_initial"):
                self.generate()
                st.rerun()
        elif drafts["status"] == "handover":
            st.warning(drafts["message"])
            st.info("Reduce the credit limit to 18 or less to generate draft plans.")
        elif drafts["status"] == "invalid_locks":
            st.warning(drafts["message"])
        elif drafts["status"] == "empty":
            st.warning(drafts["message"] + " Try relaxing one limit or restoring a rejected course.")
        else:
            plans = drafts["plans"]
            if len({tuple(c["course_id"] for c in plan) for plan in plans.values()}) < len(plans):
                st.caption("Some plans are similar because only a few courses fit these constraints.")
            for plan_index, (tab, (title, plan)) in enumerate(zip(st.tabs(list(plans)), plans.items())):
                with tab:
                    totals = self.plan_totals(plan)
                    risk = self.plan_risk(plan)
                    st.markdown(f"**Credits:** {totals['credits']} of {self.state['constraints']['max_credits']} · "
                                f"**Weekly hours:** {totals['hours']:g} of your {self.state['constraints']['max_weekly_hours']} limit")
                    if risk["rate"] is not None:
                        st.caption(f"Burnout risk: **{risk['level']}**. {round(risk['rate'] * 100)}% of {risk['n']} similar generated semesters ended in struggling or withdrawing. Synthetic estimate, not advice.")
                    if self.is_overloaded(plan):
                        st.warning("⚠️ Over your weekly-hours limit because of locked courses. Unlock one or raise the limit.")
                    else:
                        st.success("✓ Prerequisites, co-requisites and meeting conflicts checked")
                    if not plan:
                        st.info("This draft has no courses. Unlock a course or relax a planning limit.")
                    for course in plan:
                        self._render_course_card(course, plan_index)
                    self._render_rating(title, plan_index)
                    if st.button(f"✅ Select {title.split(':')[0]}", key=f"{self.state_key}_select_{plan_index}", type="primary", use_container_width=True):
                        self.select_plan(title)
                        st.rerun()
        selected = self.state["selected_plan"]
        if selected:
            totals = self.plan_totals(selected["courses"])
            st.divider()
            st.success(f"🎉 Draft selected: {selected['title']}. Nothing is final until reviewed by your Academic Advisor.")
            st.markdown(f"**Your limits:** {self.state['constraints']['max_credits']} credits, {self.state['constraints']['max_weekly_hours']} hours/week · "
                        f"**This draft:** {totals['credits']} credits, {totals['hours']:g} hours/week")
            export = {"title": selected["title"], "burnout_risk": self.plan_risk(selected["courses"]),
                      "courses": [{k: v for k, v in c.items() if k not in ("meetings", "workload", "prerequisite_groups")} for c in selected["courses"]],
                      "constraints": self.state["constraints"]}
            export_col, clear_col = st.columns(2)
            export_col.download_button("📥 Export selected plan (JSON)", data=json.dumps(export, indent=2, default=list), file_name="academic_course_plan.json", mime="application/json", use_container_width=True)
            if clear_col.button("Clear selection", key=f"{self.state_key}_clear_selection", use_container_width=True):
                self.clear_selection()
                st.rerun()
