import copy
import csv
import json
import os
import re
import streamlit as st
CREDIT_CAP = 18
PRESETS = {
    "Lucía (ADHD, No 8am, Max 15)": {
        "max_credits": 15,
        "no_8am": True,
        "no_friday": True,
        "evening_only": False,
        "low_reading_only": False,
        "completed_courses": ["CS101", "MATH101"],
    },
    "Samuel (Dyslexia, Evening, Max 12)": {
        "max_credits": 12,
        "no_8am": True,
        "no_friday": True,
        "evening_only": True,
        "low_reading_only": True,
        "completed_courses": ["CS101", "CS102", "MATH101", "GEN101"],
    },
    "Nour (Senior, Max 18)": {
        "max_credits": 18,
        "no_8am": False,
        "no_friday": False,
        "evening_only": False,
        "low_reading_only": False,
        "completed_courses": ["CS101", "CS102", "CS201", "CS202", "CS203", "CS301", "CS302", "CS303", "MATH101", "MATH102", "MATH201"],
    },
}
DAY_NAMES = {"Mon": "Monday", "Tue": "Tuesday", "Wed": "Wednesday", "Thu": "Thursday", "Fri": "Friday"}
REQUIRED_COLUMNS = {"course_id", "course_name", "department", "credits", "weekly_study_hours", "prerequisites", "schedule_slot", "difficulty_level", "reading_load", "description"}
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
class CoursePlanner:
    def __init__(self, state_key="academic_simulator_planner", catalog_path=None):
        self.state_key = f"{state_key}_course_planner_state"
        self.catalog_path = catalog_path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "course_catalog.csv")
        self.courses = self._load_catalog(self.catalog_path)
        self.course_by_id = {course["course_id"]: course for course in self.courses}
        default_constraints = copy.deepcopy(PRESETS["Lucía (ADHD, No 8am, Max 15)"])
        default_constraints["completed_courses"] = [course_id for course_id in default_constraints["completed_courses"] if course_id in self.course_by_id]
        if self.state_key not in st.session_state:
            st.session_state[self.state_key] = {
                "constraints": default_constraints,
                "locked_courses": [],
                "rejected_courses": {},
                "drafts": None,
                "selected_plan": None,
                "onboarding_stage": 1,
                "history": [],
                "redo": [],
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
    @staticmethod
    def _load_catalog(path):
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Course catalog was not found: {path}")
        courses = []
        seen_ids = set()
        with open(path, "r", encoding="utf-8-sig", newline="") as catalog_file:
            reader = csv.DictReader(catalog_file)
            missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"Course catalog is missing required columns: {', '.join(sorted(missing))}")
            for line_number, row in enumerate(reader, start=2):
                course_id = row["course_id"].strip()
                if not course_id or course_id in seen_ids:
                    raise ValueError(f"Course catalog has a missing or duplicate course ID on line {line_number}.")
                try:
                    credits = int(row["credits"])
                    study_hours = float(row["weekly_study_hours"])
                    meetings = parse_course_meetings(row["schedule_slot"])
                except (TypeError, ValueError) as error:
                    raise ValueError(f"Invalid course record on line {line_number}: {error}") from error
                if credits <= 0 or study_hours < 0:
                    raise ValueError(f"Course record on line {line_number} has invalid credits or study hours.")
                course = {key: value.strip() for key, value in row.items()}
                course["course_id"] = course_id
                course["credits"] = credits
                course["weekly_study_hours"] = study_hours
                course["meetings"] = meetings
                course["prerequisite_ids"] = [] if course["prerequisites"].lower() in ("", "none") else [item.strip() for item in course["prerequisites"].split(",")]
                courses.append(course)
                seen_ids.add(course_id)
        if not courses:
            raise ValueError("The course catalog contains no courses.")
        return courses
    def _snapshot(self, label):
        return {
            "label": label,
            "constraints": copy.deepcopy(self.state["constraints"]),
            "locked_courses": copy.deepcopy(self.state["locked_courses"]),
            "rejected_courses": copy.deepcopy(self.state["rejected_courses"]),
            "drafts": copy.deepcopy(self.state["drafts"]),
            "selected_plan": copy.deepcopy(self.state["selected_plan"]),
        }
    def _restore(self, snapshot):
        for key in ("constraints", "locked_courses", "rejected_courses", "drafts", "selected_plan"):
            self.state[key] = copy.deepcopy(snapshot[key])
        st.session_state[f"{self.state_key}_planner_preset_sync"] = True
    def _matching_preset(self):
        constraint_keys = ("max_credits", "no_8am", "no_friday", "evening_only", "low_reading_only")
        for name, preset in PRESETS.items():
            completed = {course_id for course_id in preset["completed_courses"] if course_id in self.course_by_id}
            if all(self.state["constraints"][key] == preset[key] for key in constraint_keys) and set(self.state["constraints"]["completed_courses"]) == completed:
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
    @staticmethod
    def _course_fits(course, constraints):
        if constraints["no_8am"] and any(hour == 8 for _, hour, _ in course["meetings"]):
            return False
        if constraints["no_friday"] and any(day == "Friday" for day, _, _ in course["meetings"]):
            return False
        if constraints["evening_only"] and not course["schedule_slot"].lower().startswith("evening"):
            return False
        if constraints["low_reading_only"] and course["reading_load"].lower() == "high":
            return False
        if not set(course["prerequisite_ids"]).issubset(constraints["completed_courses"]):
            return False
        return True
    @staticmethod
    def _plan_conflicts(course, occupied_meetings):
        return not course["meetings"].isdisjoint(occupied_meetings)
    def _make_drafts(self, constraints=None, locked_courses=None, rejected_courses=None):
        constraints = self.state["constraints"] if constraints is None else constraints
        locked_courses = self.state["locked_courses"] if locked_courses is None else locked_courses
        rejected_courses = self.state["rejected_courses"] if rejected_courses is None else rejected_courses
        if constraints["max_credits"] > CREDIT_CAP:
            return {"status": "handover", "message": f"Requests over {CREDIT_CAP} credits need a human Academic Advisor.", "plans": {}}
        completed = set(constraints["completed_courses"])
        eligible = [
            course for course in self.courses
            if course["course_id"] not in completed
            and course["course_id"] not in rejected_courses
            and self._course_fits(course, constraints)
        ]
        eligible_by_id = {course["course_id"]: course for course in eligible}
        if any(course_id not in eligible_by_id for course_id in locked_courses):
            return {"status": "invalid_locks", "message": "A locked course no longer meets the selected constraints or prerequisite requirements. Unlock it or update the constraints.", "plans": {}}
        locked = [eligible_by_id[course_id] for course_id in locked_courses]
        locked_meetings = set()
        locked_credits = 0
        for course in locked:
            if self._plan_conflicts(course, locked_meetings):
                return {"status": "invalid_locks", "message": f"Locked course {course['course_id']} conflicts with another locked course.", "plans": {}}
            locked_meetings.update(course["meetings"])
            locked_credits += course["credits"]
        if locked_credits > constraints["max_credits"]:
            return {"status": "invalid_locks", "message": "Locked courses exceed the selected credit limit. Unlock a course or raise the limit.", "plans": {}}
        if not eligible:
            return {"status": "empty", "message": "No courses match all current constraints and completed-course prerequisites.", "plans": {}}
        pool = [course for course in eligible if course["course_id"] not in locked_courses]
        def build(sorted_pool, requested_cap):
            plan = list(locked)
            used_credits = locked_credits
            occupied = set(locked_meetings)
            plan_cap = min(constraints["max_credits"], max(locked_credits, requested_cap))
            for course in sorted_pool:
                if used_credits + course["credits"] > plan_cap or self._plan_conflicts(course, occupied):
                    continue
                plan.append(course)
                used_credits += course["credits"]
                occupied.update(course["meetings"])
            return plan
        limit = constraints["max_credits"]
        lightest_target = min(limit, max(9, limit - 3))
        plans = {
            "Plan A: Lightest Workload": build(sorted(pool, key=lambda course: (course["weekly_study_hours"], course["course_id"])), lightest_target),
            "Plan B: Fastest Graduation": build(sorted(pool, key=lambda course: (-course["credits"], course["weekly_study_hours"], course["course_id"])), limit),
            "Plan C: Balanced Path": build(sorted(pool, key=lambda course: course["course_id"]), limit),
        }
        return {"status": "ok", "message": "", "plans": plans}
    def _regenerate(self):
        self.state["drafts"] = self._make_drafts()
        if self.state["selected_plan"]:
            title = self.state["selected_plan"]["title"]
            plan = self.state["drafts"]["plans"].get(title)
            self.state["selected_plan"] = {"title": title, "courses": plan} if plan is not None else None
    def apply_constraints(self, constraints):
        if not 6 <= constraints["max_credits"] <= 24:
            raise ValueError("The credit limit must be between 6 and 24.")
        known_ids = set(self.course_by_id)
        constraints = copy.deepcopy(constraints)
        constraints["completed_courses"] = sorted(set(constraints["completed_courses"]) & known_ids)
        self.state["constraints"] = constraints
        self._regenerate()
        self._checkpoint("Updated course planning constraints")
        st.session_state[f"{self.state_key}_planner_preset_sync"] = True
    def apply_preset(self, name):
        if name not in PRESETS:
            raise ValueError(f"Unknown student preset: {name}")
        constraints = copy.deepcopy(PRESETS[name])
        constraints["completed_courses"] = [course_id for course_id in constraints["completed_courses"] if course_id in self.course_by_id]
        self.state["constraints"] = constraints
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
    def reject_course(self, course_id):
        if course_id not in self.course_by_id:
            return False
        self.state["rejected_courses"][course_id] = "Rejected by student"
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
        self.state["selected_plan"] = {
            "title": title,
            "courses": copy.deepcopy(self.state["drafts"]["plans"][title]),
        }
        self._checkpoint(f"Selected {title}")
        return True
    def clear_selection(self):
        if self.state["selected_plan"] is None:
            return
        self.state["selected_plan"] = None
        self._checkpoint("Cleared selected plan")
    def _render_onboarding(self):
        stage = self.state["onboarding_stage"]
        if stage == 1:
            st.info("👋 **Step 1 of 3 · Explore a draft.** Course plans are generated from the catalog, prerequisite data, and your limits. Nothing is final.")
            sample = self._make_drafts(copy.deepcopy(PRESETS["Lucía (ADHD, No 8am, Max 15)"]), [], {})
            if sample["status"] == "ok":
                sample_plan = sample["plans"]["Plan C: Balanced Path"]
                st.caption("Example balanced plan: " + (", ".join(course["course_id"] for course in sample_plan) or "No courses fit the example limits."))
            start_col, skip_col = st.columns(2)
            if start_col.button("Try it myself", type="primary", key=f"{self.state_key}_onboarding_try"):
                self.state["onboarding_stage"] = 2
                st.rerun()
            if skip_col.button("Skip guide", key=f"{self.state_key}_onboarding_skip"):
                self.state["onboarding_stage"] = 3
                st.rerun()
        elif stage == 2:
            st.success("🤝 **Step 2 of 3 · Co-pilot.** Choose a student preset or set your own credit, time, reading, and completed-course limits. Then generate drafts and try lock, reject, Undo, and Redo.")
            if st.button("Got it — open the planner", key=f"{self.state_key}_onboarding_done"):
                self.state["onboarding_stage"] = 3
                st.rerun()
        else:
            if st.button("❓ Show planner guide", key=f"{self.state_key}_onboarding_again"):
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
            preset = st.selectbox("Select a profile", ["Custom"] + list(PRESETS), key=f"{self.state_key}_planner_preset")
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
                no_8am = st.checkbox("No 8:00 AM classes", value=constraints["no_8am"])
                no_friday = st.checkbox("No Friday classes", value=constraints["no_friday"])
                evening_only = st.checkbox("Evening classes only", value=constraints["evening_only"])
                low_reading_only = st.checkbox("Low reading load", value=constraints["low_reading_only"])
                completed_courses = st.multiselect("Courses already completed", sorted(self.course_by_id), default=constraints["completed_courses"])
                submitted = st.form_submit_button("Update limits and generate drafts", type="primary", use_container_width=True)
                if submitted:
                    self.apply_constraints({
                        "max_credits": max_credits,
                        "no_8am": no_8am,
                        "no_friday": no_friday,
                        "evening_only": evening_only,
                        "low_reading_only": low_reading_only,
                        "completed_courses": completed_courses,
                    })
                    st.rerun()
            if self.state["rejected_courses"]:
                st.subheader("🚫 Rejected courses")
                for course_id in sorted(self.state["rejected_courses"]):
                    course = self.course_by_id[course_id]
                    if st.button(f"Restore {course_id}: {course['course_name']}", key=f"{self.state_key}_restore_{course_id}", use_container_width=True):
                        self.restore_course(course_id)
                        st.rerun()
    def _render_course_card(self, course, plan_index):
        course_id = course["course_id"]
        locked = course_id in self.state["locked_courses"]
        with st.container(border=True):
            st.markdown(f"**{course_id}: {course['course_name']}** {'🔒 Locked' if locked else ''}")
            st.caption(f"{course['department']} · {course['credits']} credits · {course['weekly_study_hours']:g} study hours/week · {course['difficulty_level']} · Reading: {course['reading_load']}")
            st.write(f"Schedule: {course['schedule_slot']}")
            with st.expander("Why this course?"):
                prerequisites = ", ".join(course["prerequisite_ids"]) or "None"
                st.write(f"Prerequisites: {prerequisites}.")
                st.write(f"All required prerequisites are in your completed-course list. The meeting time fits the selected limits.")
                st.write(course["description"])
            lock_col, reject_col = st.columns(2)
            if lock_col.button("Unlock" if locked else "🔒 Lock", key=f"{self.state_key}_lock_{plan_index}_{course_id}", use_container_width=True):
                self.toggle_lock(course_id)
                st.rerun()
            if reject_col.button("✖ Reject", key=f"{self.state_key}_reject_{plan_index}_{course_id}", use_container_width=True):
                self.reject_course(course_id)
                st.rerun()
    def render(self):
        self._render_sidebar()
        st.header("📚 Course Planner")
        st.caption("Compare draft plans built from the HAI course catalog. The simulator checks listed prerequisites, meeting-time conflicts, and your limits; it does not register courses.")
        self._render_onboarding()
        with st.expander("ℹ️ What the planner can and cannot do"):
            st.markdown(f"- **It can:** generate up to three course drafts, check listed prerequisites, estimate weekly study hours, and let you lock, reject, undo, or redo changes.\n- **It cannot:** register courses, approve prerequisite waivers, or approve credit overloads above {CREDIT_CAP}. Contact a human Academic Advisor for exceptions.")
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
            if len({tuple(course["course_id"] for course in plan) for plan in plans.values()}) < len(plans):
                st.caption("Some plans are similar because only a few courses fit these constraints.")
            plan_tabs = st.tabs(list(plans))
            for plan_index, (tab, (title, plan)) in enumerate(zip(plan_tabs, plans.items())):
                with tab:
                    credits = sum(course["credits"] for course in plan)
                    study_hours = sum(course["weekly_study_hours"] for course in plan)
                    st.markdown(f"**Credits:** {credits} of {self.state['constraints']['max_credits']} · **Estimated study load:** {study_hours:g} hours/week")
                    st.success("✓ Prerequisites and course meeting conflicts checked")
                    if not plan:
                        st.info("This draft has no courses. Unlock a course or relax a planning limit.")
                    for course in plan:
                        self._render_course_card(course, plan_index)
                    if st.button(f"✅ Select {title.split(':')[0]}", key=f"{self.state_key}_select_{plan_index}", type="primary", use_container_width=True):
                        self.select_plan(title)
                        st.rerun()
        selected = self.state["selected_plan"]
        if selected:
            credits = sum(course["credits"] for course in selected["courses"])
            hours = sum(course["weekly_study_hours"] for course in selected["courses"])
            st.divider()
            st.success(f"🎉 Draft selected: {selected['title']}. Nothing is final until reviewed by your Academic Advisor.")
            st.markdown(f"**Your limit:** {self.state['constraints']['max_credits']} credits · **This draft:** {credits} credits, {hours:g} study hours/week")
            export = {"title": selected["title"], "courses": [{key: value for key, value in course.items() if key != "meetings"} for course in selected["courses"]], "constraints": self.state["constraints"]}
            export_col, clear_col = st.columns(2)
            export_col.download_button("📥 Export selected plan (JSON)", data=json.dumps(export, indent=2), file_name="academic_course_plan.json", mime="application/json", use_container_width=True)
            if clear_col.button("Clear selection", key=f"{self.state_key}_clear_selection", use_container_width=True):
                self.clear_selection()
                st.rerun()
