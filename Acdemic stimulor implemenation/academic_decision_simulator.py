import copy
import html
import json
import math
import os
import re
import uuid
from datetime import datetime
import streamlit as st
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
import chat_guard
from course_planner import CoursePlanner
from project_theme import THEMES
class AcademicDecisionSimulator:
    DAYS = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    def __init__(self, llm, system_prompt, start_hour=8, end_hour=22, state_key="academic_simulator"):
        if not (0 <= start_hour < end_hour <= 24):
            raise ValueError("Invalid schedule hours.")
        self.llm = llm
        self.system_prompt = system_prompt
        self.start_hour = start_hour
        self.end_hour = end_hour
        self.state_key = state_key
        self.course_planner = CoursePlanner(state_key=f"{state_key}_planner")
        self.schedule_key = f"{state_key}_schedule"
        self.messages_key = f"{state_key}_messages"
        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        file_key = re.sub(r"[^a-zA-Z0-9_-]", "_", state_key)
        self.schedule_file = os.path.join(data_dir, f"{file_key}_schedule.json")
        self.messages_file = os.path.join(data_dir, f"{file_key}_chat.json")
        # Initialize Streamlit session state
        if self.schedule_key not in st.session_state:
            st.session_state[self.schedule_key] = self._load_json(self.schedule_file, [])
        if self.messages_key not in st.session_state:
            st.session_state[self.messages_key] = self._load_json(self.messages_file, [])
    @staticmethod
    def _load_json(path, default):
        if not os.path.exists(path):
            return default
        try:
            with open(path, "r", encoding="utf-8") as data_file:
                return json.load(data_file)
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(f"Could not load stored data from {path}: {error}") from error
    @staticmethod
    def _save_json(path, value):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        temporary_path = f"{path}.tmp"
        try:
            with open(temporary_path, "w", encoding="utf-8") as data_file:
                json.dump(value, data_file, ensure_ascii=False, indent=2)
            os.replace(temporary_path, path)
        except OSError as error:
            raise RuntimeError(f"Could not save stored data to {path}: {error}") from error
    def _save_schedule(self, schedule=None):
        self._save_json(self.schedule_file, st.session_state[self.schedule_key] if schedule is None else schedule)
    def _save_messages(self):
        self._save_json(self.messages_file, st.session_state[self.messages_key])
    def clear_chat(self):
        try:
            os.remove(self.messages_file)
        except FileNotFoundError:
            pass
        except OSError as error:
            raise RuntimeError(f"Could not delete chat history at {self.messages_file}: {error}") from error
        st.session_state[self.messages_key] = []
    # ======================================================
    # 1. SCHEDULE MANAGEMENT
    # ======================================================
    def _add_work_to_schedule(self, schedule, workname, duration_hours, day, start_time):
        """
        Add a subject or work activity to the schedule.
        Example:
            set_work(
                workname="Machine Learning",
                duration_hours=2,
                day="Saturday",
                start_time="10:00"
            )
        """
        workname = str(workname or "").strip()
        # Normalize day
        day_lookup = {d.lower(): d for d in self.DAYS}
        day = day_lookup.get(str(day).strip().lower())
        if not workname:
            return False, "Work name cannot be empty."
        if day is None:
            return False, "Invalid day."
        # Validate duration
        try:
            duration = float(duration_hours)
        except (ValueError, TypeError):
            return False, "Duration must be a number."
        if not math.isfinite(duration):
            return False, "Invalid duration."
        if duration <= 0 or not duration.is_integer():
            return False, "Duration must be a positive whole number of hours."
        duration = int(duration)
        # Validate start time
        try:
            parsed_time = datetime.strptime(start_time, "%H:%M")
        except (ValueError, TypeError):
            return False, "Start time must use HH:MM format."
        if parsed_time.minute != 0:
            return False, "Start time must be on an hourly boundary."
        start = parsed_time.hour
        end = start + duration
        # Validate timetable boundaries
        if start < self.start_hour or end > self.end_hour:
            return False, "Work is outside the available timetable."
        # Check overlapping activities
        for item in schedule:
            if item["day"] != day:
                continue
            existing_start = item["start_hour"]
            existing_end = existing_start + item["duration_hours"]
            overlap = start < existing_end and existing_start < end
            if overlap:
                return False, (f"Schedule conflict with " f"{item['workname']} on {day}.")
        # Create activity
        new_work = {"workname": workname, "day": day, "start_hour": start, "duration_hours": duration}
        schedule.append(new_work)
        # Sort activities by day and time
        schedule.sort(key=lambda item: (self.DAYS.index(item["day"]), item["start_hour"]))
        return True, f"{workname} added successfully!"
    def set_work(self, workname, duration_hours, day, start_time):
        schedule = st.session_state[self.schedule_key]
        success, message = self._add_work_to_schedule(schedule, workname, duration_hours, day, start_time)
        if success:
            self._save_schedule()
        return success, message
    # ======================================================
    # 2. REMOVE WORK
    # ======================================================
    def _remove_work_from_schedule(self, schedule, workname, day, start_time):
        try:
            parsed_time = datetime.strptime(start_time, "%H:%M")
            if parsed_time.minute != 0:
                return False, "Invalid start time."
            start_hour = parsed_time.hour
        except (ValueError, TypeError):
            return False, "Invalid start time."
        day_lookup = {d.lower(): d for d in self.DAYS}
        day = day_lookup.get(str(day).strip().lower())
        if day is None:
            return False, "Invalid day."
        for index, item in enumerate(schedule):
            if item["workname"] == workname and item["day"] == day and item["start_hour"] == start_hour:
                schedule.pop(index)
                return True, "Work removed successfully."
        return False, "Work was not found."
    def remove_work(self, workname, day, start_time):
        success, message = self._remove_work_from_schedule(st.session_state[self.schedule_key], workname, day, start_time)
        if success:
            self._save_schedule()
        return success, message
    def _find_work_index(self, schedule, workname, day, start_time):
        workname = str(workname or "").strip()
        if not workname:
            return None, "Work name cannot be empty."
        try:
            parsed_time = datetime.strptime(start_time, "%H:%M")
            if parsed_time.minute != 0:
                return None, "Invalid start time."
            start_hour = parsed_time.hour
        except (ValueError, TypeError):
            return None, "Invalid start time."
        day_lookup = {item.lower(): item for item in self.DAYS}
        day = day_lookup.get(str(day).strip().lower())
        if day is None:
            return None, "Invalid day."
        for index, item in enumerate(schedule):
            if item["workname"] == workname and item["day"] == day and item["start_hour"] == start_hour:
                return index, None
        return None, "Work was not found."
    def _update_work_in_schedule(
        self,
        schedule,
        workname,
        day,
        start_time,
        new_day=None,
        new_start_time=None,
        duration_hours=None,
    ):
        if new_day is None and new_start_time is None and duration_hours is None:
            return False, "Provide at least one new day, start time, or duration."
        index, error = self._find_work_index(schedule, workname, day, start_time)
        if error:
            return False, error
        existing = schedule[index]
        updated_schedule = [dict(item) for item in schedule]
        updated_schedule.pop(index)
        success, message = self._add_work_to_schedule(
            updated_schedule,
            workname,
            existing["duration_hours"] if duration_hours is None else duration_hours,
            existing["day"] if new_day is None else new_day,
            f"{existing['start_hour']:02d}:00" if new_start_time is None else new_start_time,
        )
        if not success:
            return False, message
        schedule[:] = updated_schedule
        return True, f"{workname} updated successfully."
    def update_work(
        self,
        workname,
        day,
        start_time,
        new_day=None,
        new_start_time=None,
        duration_hours=None,
    ):
        success, message = self._update_work_in_schedule(
            st.session_state[self.schedule_key],
            workname,
            day,
            start_time,
            new_day=new_day,
            new_start_time=new_start_time,
            duration_hours=duration_hours,
        )
        if success:
            self._save_schedule()
        return success, message
    # ======================================================
    # 3. GENERATE SCHEDULE HTML
    # ======================================================
    def _generate_schedule_html(self):
        schedule = st.session_state[self.schedule_key]
        palette = THEMES.get(st.session_state.get("academic_theme", "Calm Blue"), THEMES["Calm Blue"])
        hours = range(self.start_hour, self.end_hour)
        table_html = []
        # CSS
        table_html.append("""
        <style>
            .schedule-wrapper {
                width: 100%;
                max-width: 100%;
                overflow-x: auto;
                margin-top: 15px;
                border: 1.5px solid __BORDER__;
                border-radius: 16px;
                background-color: __SURFACE__;
            }
            .schedule-table {
                width: max-content;
                min-width: 100%;
                border-collapse: collapse;
                table-layout: fixed;
                text-align: center;
                font-family: 'Atkinson Hyperlegible', 'Segoe UI', Verdana, sans-serif;
                color: __TEXT__;
            }
            .schedule-table th,
            .schedule-table td {
                border: 1px solid __BORDER__;
                padding: 12px 8px;
                min-width: 78px;
                height: 72px;
                font-size: 0.9rem;
                line-height: 1.4;
            }
            .schedule-table th {
                background-color: __TINT_H__;
                color: __TEXT__;
                font-weight: bold;
                white-space: nowrap;
            }
            .schedule-table .day-column {
                min-width: 110px;
                width: 110px;
            }
            .schedule-table .day-name {
                background-color: __TINT__;
                color: __TEXT__;
                font-weight: bold;
                min-width: 110px;
            }
            .schedule-table .empty-cell {
                background-color: __SURFACE__;
            }
            .schedule-table .work-cell {
                background-color: __USER__;
                color: __TEXT__;
                font-weight: bold;
                border: 2px solid __ACCENT__;
                overflow-wrap: anywhere;
            }
            .schedule-table .work-cell small {
                display: block;
                margin-top: 6px;
                font-weight: normal;
                font-size: 0.8rem;
                line-height: 1.4;
            }
        </style>
        <div class="schedule-wrapper">
            <table class="schedule-table">
                <thead>
                    <tr>
                        <th class="day-column">Day</th>
        """.replace("__BORDER__", palette["border"]).replace("__SURFACE__", palette["surface"]).replace("__TEXT__", palette["text"]).replace("__TINT_H__", palette["tint_h"]).replace("__TINT__", palette["tint"]).replace("__USER__", palette["user"]).replace("__ACCENT__", palette["accent"]))
        # Create hourly headers
        for hour in hours:
            next_hour = hour + 1
            table_html.append(f"""
                <th>
                    {hour:02d}:00
                    <br>
                    {next_hour:02d}:00
                </th>
            """)
        table_html.append("""
                    </tr>
                </thead>
                <tbody>
        """)
        # Create rows for all seven days
        for day in self.DAYS:
            day_items = [item for item in schedule if item["day"] == day]
            # Map starting hour to activity
            start_map = {item["start_hour"]: item for item in day_items}
            table_html.append(f"""
                <tr>
                    <td class="day-name">
                        {html.escape(day)}
                    </td>
            """)
            hour_index = 0
            total_hours = self.end_hour - self.start_hour
            while hour_index < total_hours:
                current_hour = self.start_hour + hour_index
                item = start_map.get(current_hour)
                if item:
                    duration = item["duration_hours"]
                    workname = html.escape(item["workname"])
                    end_hour = current_hour + duration
                    table_html.append(f"""
                        <td colspan="{duration}"
                            class="work-cell">
                            {workname}
                            <small>
                                {current_hour:02d}:00 -
                                {end_hour:02d}:00
                            </small>
                        </td>
                    """)
                    hour_index += duration
                else:
                    table_html.append("""
                        <td class="empty-cell">&nbsp;</td>
                    """)
                    hour_index += 1
            table_html.append("</tr>")
        table_html.append("""
                </tbody>
            </table>
        </div>
        """)
        return "".join(table_html)
    # ======================================================
    # 4. DASHBOARD
    # ======================================================
    def render_dashboard(self):
        st.header("📅 Academic Dashboard")
        schedule = st.session_state[self.schedule_key]
        total_work = len(schedule)
        total_hours = sum(item["duration_hours"] for item in schedule)
        available_hours = (self.end_hour - self.start_hour) * 7 - total_hours
        # Dashboard metrics
        col1, col2, col3 = st.columns(3)
        col1.metric("Scheduled Activities", total_work)
        col2.metric("Total Hours", total_hours)
        col3.metric("Available Hours", available_hours)
        st.divider()
        # Add work form
        st.subheader("➕ Add Subject or Work")
        with st.form(f"{self.state_key}_work_form"):
            col1, col2 = st.columns(2)
            with col1:
                workname = st.text_input("Subject / Work Name", placeholder="Machine Learning")
                day = st.selectbox("Select Day", self.DAYS)
            with col2:
                start_options = [f"{hour:02d}:00" for hour in range(self.start_hour, self.end_hour)]
                start_time = st.selectbox("Starting Time", start_options)
                duration = st.number_input("Duration (Hours)", min_value=1, max_value=(self.end_hour - self.start_hour), value=1, step=1)
            submitted = st.form_submit_button("Add to Schedule")
            if submitted:
                success, message = self.set_work(workname=workname, duration_hours=duration, day=day, start_time=start_time)
                if success:
                    st.success(message)
                else:
                    st.error(message)
        st.divider()
        # Display timetable
        st.subheader("🗓️ Weekly Schedule")
        schedule_html = self._generate_schedule_html()
        # IMPORTANT: Render HTML directly
        st.html(schedule_html, width="stretch")
        # Remove activities
        if schedule:
            st.divider()
            with st.expander("🗑️ Remove an Activity"):
                options = [(f"{item['workname']} | " f"{item['day']} | " f"{item['start_hour']:02d}:00") for item in schedule]
                selected = st.selectbox("Select Activity", options, key=f"{self.state_key}_remove_select")
                if st.button("Remove Selected Activity", key=f"{self.state_key}_remove_button"):
                    selected_index = options.index(selected)
                    item = schedule[selected_index]
                    success, message = self.remove_work(item["workname"], item["day"], f"{item['start_hour']:02d}:00")
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
    # ======================================================
    # 5. CHATBOT UTILITIES
    # ======================================================
    @staticmethod
    def get_text(content):
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(block.get("text", "") if isinstance(block, dict) else str(block) for block in content)
        return str(content)
    # ------------------------------------------------------
    def get_schedule_context(self):
        schedule = st.session_state[self.schedule_key]
        if not schedule:
            return "The student's schedule is currently empty."
        lines = []
        for item in schedule:
            start = item["start_hour"]
            end = start + item["duration_hours"]
            lines.append(f"- {item['day']}: " f"{item['workname']} " f"from {start:02d}:00 to {end:02d}:00")
        return "\n".join(lines)
    # ------------------------------------------------------
    def _build_system_prompt(self, user_text=""):
        study_days = ", ".join(self.DAYS)
        facts = chat_guard.catalog_context(user_text, self.course_planner.courses)
        catalog_block = (
            "COURSE CATALOG FACTS (the only source of truth about courses; if a course is not listed here "
            "or the student's question needs data you do not have, say you cannot find it and suggest a human "
            "Academic Advisor; never invent courses, prerequisites or hours):\n" + (facts or "(no specific course matched this message)")
        )
        return f"""
{self.system_prompt}
CURRENT STUDENT SCHEDULE:
{self.get_schedule_context()}
{catalog_block}
Instructions:
- Use the current schedule when answering questions.
- Only add a study session to a slot that is shown as free in CURRENT STUDENT SCHEDULE.
- Never add an activity over an existing activity. Use update to move or resize an
  existing activity, or remove it before adding a replacement in the same proposal.
- Check every operation against the final schedule after all removes and updates.
- When uploaded course material includes a workload estimate and the user wants a study plan,
  propose study sessions whose total time is guided by that estimate.
- Spread study sessions across the student's available week ({study_days}),
  between {self.start_hour:02d}:00 and {self.end_hour:02d}:00. Avoid existing activities.
- Treat the workload estimate as approximate and explain that the student can adjust it.
- Do not invent scheduled activities.
- Do not claim that an activity was added or removed
  unless the backend actually performs that action.
- The student has full control over all schedule decisions.
- When a concrete schedule change would help, include one machine-readable
  proposal at the end of your response in this exact format:
  <schedule_suggestion>
  {{"reason":"short explanation","operations":[
    {{"action":"add","workname":"Activity","day":"Monday","start_time":"10:00","duration_hours":1}},
    {{"action":"update","workname":"Existing Activity","day":"Monday","start_time":"09:00","new_start_time":"10:00"}}
  ]}}
  </schedule_suggestion>
- Operations may use action "add", "remove", or "update". For "remove" and
  "update", workname, day, and start_time identify the existing activity.
  An update may include new_day, new_start_time, and/or duration_hours; omitted
  fields keep their current values. Use update rather than remove-plus-add when
  moving or resizing an existing course. Put related updates in the same
  proposal when they resolve conflicts with each other's old time slots; the
  backend applies the complete proposal atomically.
- Do not include an operation unless the user asked for a schedule change or
  the suggestion is clearly useful. Never say the schedule has changed; the
  student must accept the proposal first.
"""
    # ======================================================
    # 6. CHATBOT
    # ======================================================
    def _parse_schedule_suggestion(self, reply):
        match = re.search(r"<schedule_suggestion>\s*(.*?)\s*</schedule_suggestion>", reply, flags=re.DOTALL | re.IGNORECASE)
        if not match:
            return reply, None, None
        visible_reply = (reply[: match.start()] + reply[match.end() :]).strip()
        try:
            suggestion = json.loads(match.group(1))
            if not isinstance(suggestion, dict):
                raise ValueError("The suggestion must be a JSON object.")
            operations = suggestion.get("operations")
            if not isinstance(operations, list) or not operations:
                raise ValueError("The suggestion has no schedule changes.")
            if len(operations) > 20:
                raise ValueError("A suggestion cannot contain more than 20 changes.")
            normalized_operations = []
            for operation in operations:
                if not isinstance(operation, dict):
                    raise ValueError("Each schedule change must be an object.")
                action = operation.get("action")
                if action not in ("add", "remove", "update"):
                    raise ValueError("Each change must use action add, remove, or update.")
                for field in ("workname", "day", "start_time"):
                    if not isinstance(operation.get(field), str) or not operation[field].strip():
                        raise ValueError(f"Each change must include a valid {field}.")
                normalized = {"action": action, "workname": operation["workname"].strip(), "day": operation["day"].strip(), "start_time": operation["start_time"].strip()}
                if action == "add":
                    if "duration_hours" not in operation:
                        raise ValueError("An add change must include duration_hours.")
                    normalized["duration_hours"] = operation.get("duration_hours")
                elif action == "update":
                    update_fields = ("new_day", "new_start_time", "duration_hours")
                    if not any(field in operation for field in update_fields):
                        raise ValueError("An update must include at least one new schedule value.")
                    for field in ("new_day", "new_start_time"):
                        if field in operation:
                            if not isinstance(operation[field], str) or not operation[field].strip():
                                raise ValueError(f"An update must include a valid {field}.")
                            normalized[field] = operation[field].strip()
                    if "duration_hours" in operation:
                        normalized["duration_hours"] = operation["duration_hours"]
                normalized_operations.append(normalized)
            proposal = {"id": uuid.uuid4().hex, "reason": str(suggestion.get("reason", "")).strip(), "operations": normalized_operations, "status": "pending"}
            _, validation_error = self._proposed_schedule(proposal["operations"])
            if validation_error:
                return visible_reply, None, validation_error
            return visible_reply, proposal, None
        except (json.JSONDecodeError, ValueError, TypeError) as error:
            return visible_reply, None, str(error)
    def _proposed_schedule(self, operations):
        proposed = [dict(activity) for activity in st.session_state[self.schedule_key]]
        resolved_updates = {}
        for index, operation in enumerate(operations):
            if operation["action"] == "remove":
                success, message = self._remove_work_from_schedule(
                    proposed,
                    operation["workname"],
                    operation["day"],
                    operation["start_time"],
                )
                if not success:
                    return None, message
            elif operation["action"] == "update":
                work_index, message = self._find_work_index(
                    proposed,
                    operation["workname"],
                    operation["day"],
                    operation["start_time"],
                )
                if message:
                    return None, message
                existing = proposed.pop(work_index)
                resolved_updates[index] = {
                    "workname": operation["workname"],
                    "day": operation.get("new_day", existing["day"]),
                    "start_time": operation.get(
                        "new_start_time",
                        f"{existing['start_hour']:02d}:00",
                    ),
                    "duration_hours": operation.get(
                        "duration_hours",
                        existing["duration_hours"],
                    ),
                }
        for index, operation in enumerate(operations):
            if operation["action"] == "add":
                success, message = self._add_work_to_schedule(proposed, operation["workname"], operation["duration_hours"], operation["day"], operation["start_time"])
            elif operation["action"] == "update":
                update = resolved_updates[index]
                success, message = self._add_work_to_schedule(
                    proposed,
                    update["workname"],
                    update["duration_hours"],
                    update["day"],
                    update["start_time"],
                )
            else:
                continue
            if not success:
                return None, message
        return proposed, None
    def _render_schedule_proposal(self, message):
        proposal = message.get("proposal")
        if not proposal:
            if message.get("suggestion_error"):
                st.warning("The assistant's schedule suggestion could not be applied: " f"{message['suggestion_error']}")
            return
        status = proposal.get("status", "pending")
        if status != "pending":
            label = "Accepted" if status == "accepted" else "Cancelled"
            st.caption(f"Schedule suggestion {label.lower()}.")
            return
        updated_schedule, validation_error = self._proposed_schedule(proposal["operations"])
        with st.container(border=True):
            st.markdown("#### 📅 Schedule suggestion")
            if proposal.get("reason"):
                st.write(proposal["reason"])
            for operation in proposal["operations"]:
                action = operation["action"].capitalize()
                start = operation["start_time"]
                if operation["action"] == "add":
                    end_hour = int(start[:2]) + int(operation["duration_hours"])
                    details = f"{operation['workname']} | {operation['day']} | " f"{start}-{end_hour:02d}:00 " f"({operation['duration_hours']} hour(s))"
                elif operation["action"] == "remove":
                    details = f"{operation['workname']} | {operation['day']} | {start}"
                else:
                    work_index, _ = self._find_work_index(
                        st.session_state[self.schedule_key],
                        operation["workname"],
                        operation["day"],
                        operation["start_time"],
                    )
                    duration = operation.get("duration_hours")
                    if duration is None and work_index is not None:
                        duration = st.session_state[self.schedule_key][work_index]["duration_hours"]
                    new_day = operation.get("new_day", operation["day"])
                    new_start = operation.get("new_start_time", operation["start_time"])
                    duration_details = f" ({duration} hour(s))" if duration is not None else ""
                    details = (
                        f"{operation['workname']} | {operation['day']} {operation['start_time']} "
                        f"→ {new_day} {new_start}{duration_details}"
                    )
                st.markdown(f"- **{action}:** {details}")
            if validation_error:
                st.warning(f"This proposal no longer fits the schedule: {validation_error}")
            accept_col, cancel_col = st.columns(2)
            with accept_col:
                accepted = st.button("Accept", key=f"{self.state_key}_accept_{proposal['id']}", disabled=validation_error is not None)
            with cancel_col:
                cancelled = st.button("Cancel", key=f"{self.state_key}_cancel_{proposal['id']}")
        if accepted and updated_schedule is not None:
            self._save_schedule(updated_schedule)
            st.session_state[self.schedule_key] = updated_schedule
            proposal["status"] = "accepted"
            self._save_messages()
            st.rerun()
        if cancelled:
            proposal["status"] = "cancelled"
            self._save_messages()
            st.rerun()
    def _create_local_workload_schedule_response(self, documents):
        estimated_hours = sum(document["workload"]["estimated_hours"] for document in documents)
        scheduled = st.session_state[self.schedule_key]
        file_names = [document["filename"] for document in documents]
        file_label = file_names[0] if len(file_names) == 1 else f"{file_names[0]} and {len(file_names) - 1} more"
        workname = f"Study: {file_label}"[:80]
        occupied = {day: set() for day in self.DAYS}
        for activity in scheduled:
            for hour in range(activity["start_hour"], activity["start_hour"] + activity["duration_hours"]):
                occupied[activity["day"]].add(hour)

        daily_blocks = {}
        for day in self.DAYS:
            blocks = []
            hour = self.start_hour
            while hour < self.end_hour:
                if hour in occupied[day]:
                    hour += 1
                    continue
                start = hour
                while hour < self.end_hour and hour not in occupied[day] and hour - start < 2:
                    hour += 1
                blocks.append((start, hour - start))
            daily_blocks[day] = blocks

        available_hours = sum(duration for blocks in daily_blocks.values() for _, duration in blocks)
        remaining_hours = estimated_hours
        operations = []
        block_round = 0
        while remaining_hours > 0 and len(operations) < 20:
            added_block = False
            for day in self.DAYS:
                if block_round >= len(daily_blocks[day]) or remaining_hours <= 0 or len(operations) >= 20:
                    continue
                start, block_hours = daily_blocks[day][block_round]
                duration = min(block_hours, remaining_hours)
                operations.append({
                    "action": "add",
                    "workname": workname,
                    "day": day,
                    "start_time": f"{start:02d}:00",
                    "duration_hours": duration,
                })
                remaining_hours -= duration
                added_block = True
            if not added_block:
                break
            block_round += 1

        if not operations:
            return {
                "role": "assistant",
                "content": (
                    f"The uploaded material is estimated to need {estimated_hours} study hours, "
                    "but there are no open timetable slots for a study proposal."
                ),
            }

        scheduled_hours = estimated_hours - remaining_hours
        reason = (
            f"The material is estimated at {estimated_hours} study hours. "
            f"This draft schedules {scheduled_hours} hour(s) in available 1–2 hour sessions."
        )
        if remaining_hours:
            reason += f" The remaining {remaining_hours} hour(s) do not fit in this week's available slots."
        reason += f" Activity: {workname}."
        suggestion_json = json.dumps({"reason": reason, "operations": operations})
        draft = (
            f"Based on the uploaded material, I estimate **{estimated_hours} study hours**. "
            f"I drafted **{scheduled_hours} hour(s)** in the current timetable "
            f"({available_hours} hour(s) are open this week). Review the proposal below; "
            "it will only be added if you accept it."
            f"\n<schedule_suggestion>{suggestion_json}</schedule_suggestion>"
        )
        visible_reply, proposal, suggestion_error = self._parse_schedule_suggestion(draft)
        if suggestion_error or proposal is None:
            raise RuntimeError(
                f"Could not create a valid workload-based schedule proposal: {suggestion_error}"
            )
        return {"role": "assistant", "content": visible_reply, "proposal": proposal}
    def render_chatbot(self):
        st.header("💬 Academic Assistant")
        if st.button("🗑️ New Chat", key=f"{self.state_key}_new_chat", help="Delete saved chat history and start a blank conversation."):
            try:
                self.clear_chat()
            except RuntimeError as error:
                st.error(str(error))
            else:
                st.rerun()
        messages = st.session_state[self.messages_key]
        pending_key = f"{self.state_key}_pending_prompt"
        # Greeting (always first, not sent to the model) and quick replies
        with st.chat_message("assistant"):
            st.markdown(chat_guard.GREETING)
            quick_columns = st.columns(len(chat_guard.QUICK_REPLIES))
            for column, quick_text in zip(quick_columns, chat_guard.QUICK_REPLIES):
                if column.button(quick_text, key=f"{self.state_key}_quick_{quick_text}", use_container_width=True):
                    st.session_state[pending_key] = quick_text
        # Display conversation history
        for message_index, message in enumerate(messages):
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                for document_index, document in enumerate(message.get("documents", [])):
                    with st.expander(f"OCR text: {document['filename']}"):
                        st.text_area(
                            "Extracted document text",
                            value=document["text"],
                            height=320,
                            disabled=True,
                            label_visibility="collapsed",
                        )
                        document_key = document.get("document_id") or f"{message_index}_{document_index}"
                        if st.button(
                            "Delete material and embeddings",
                            key=f"{self.state_key}_delete_material_{document_key}",
                            type="secondary",
                        ):
                            from document_workload_analyzer import DocumentWorkloadAnalyzer
                            analyzer = DocumentWorkloadAnalyzer()
                            deleted_vectors = analyzer.delete_embeddings(
                                document_id=document.get("document_id"),
                                filename=document["filename"],
                            )
                            updated_messages = copy.deepcopy(messages)
                            for stored_message in updated_messages:
                                stored_documents = stored_message.get("documents")
                                if not stored_documents:
                                    continue
                                if document.get("document_id"):
                                    stored_documents = [
                                        stored_document for stored_document in stored_documents
                                        if stored_document.get("document_id") != document["document_id"]
                                    ]
                                else:
                                    stored_documents = [
                                        stored_document for stored_document in stored_documents
                                        if stored_document.get("filename") != document["filename"]
                                    ]
                                if stored_documents:
                                    stored_message["documents"] = stored_documents
                                else:
                                    stored_message.pop("documents", None)
                            self._save_json(self.messages_file, updated_messages)
                            st.session_state[self.messages_key] = updated_messages
                            st.success(
                                f"Deleted {document['filename']} and "
                                f"{deleted_vectors} stored embedding(s)."
                            )
                            st.rerun()
                self._render_schedule_proposal(message)
        # Chat input
        submission = st.chat_input(
            "Ask about course material or attach a document...",
            key=f"{self.state_key}_chat_input",
            accept_file=True,
            file_type=["pdf", "docx", "pptx"],
        )
        if not submission and st.session_state.get(pending_key):
            submission = st.session_state.pop(pending_key)
        if submission:
            if isinstance(submission, str):
                user_text = submission.strip()
                uploaded_files = []
            else:
                user_text = submission.text.strip()
                uploaded_files = submission.files
            documents = []
            if uploaded_files:
                try:
                    from document_workload_analyzer import DocumentWorkloadAnalyzer
                    analyzer = DocumentWorkloadAnalyzer()
                    with st.spinner("Reading the material and calculating its workload..."):
                        for uploaded_file in uploaded_files:
                            analysis = analyzer.analyze(
                                uploaded_file.getvalue(),
                                uploaded_file.name,
                            )
                            documents.append({
                                "filename": uploaded_file.name,
                                "document_id": analysis.document_id,
                                "text": analysis.extracted_text,
                                "workload": {
                                    "word_count": analysis.word_count,
                                    "chunks": analysis.chunks,
                                    "topic_count": analysis.topic_count,
                                    "diversity": analysis.diversity,
                                    "estimated_hours": analysis.estimated_hours,
                                    "stored_vectors": analysis.stored_vectors,
                                    "topics": analysis.topics,
                                },
                            })
                except (ImportError, OSError, RuntimeError, ValueError) as error:
                    st.error(f"Could not analyze the uploaded material: {error}")
                    return
            if not user_text and documents:
                user_text = (
                    "Analyze this course material's workload and suggest study sessions "
                    "on my weekly schedule based on it."
                )
            if not user_text and not documents:
                return
            # Save user message
            user_message = {"role": "user", "content": user_text}
            if documents:
                user_message["documents"] = documents
            messages.append(user_message)
            self._save_messages()
            with st.chat_message("user"):
                st.markdown(user_text)
                for document in documents:
                    workload = document["workload"]
                    st.info(
                        f"Estimated study time: **{workload['estimated_hours']} hours** "
                        f"· {workload['word_count']:,} words · "
                        f"{workload['topic_count']} topic groups"
                    )
                    st.caption(
                        f"Topic diversity: {workload['diversity']:.0%}. "
                        f"{workload['stored_vectors']} chunk embeddings saved in Chroma."
                    )
                    with st.expander(f"OCR text: {document['filename']}"):
                        st.text_area(
                            "Extracted document text",
                            value=document["text"],
                            height=320,
                            disabled=True,
                            label_visibility="collapsed",
                        )
            # Safeguards run first: unsafe, out-of-scope, overload / waiver (human handover), catalog lookups.
            guard = None if documents else chat_guard.check(user_text, self.course_planner.courses)
            if guard:
                messages.append({"role": "assistant", "content": guard["reply"], "guard": guard["category"]})
                self._save_messages()
                st.rerun()
            if self.llm is None:
                if documents:
                    messages.append(self._create_local_workload_schedule_response(documents))
                    self._save_messages()
                    st.rerun()
                messages.append({"role": "assistant", "content": (
                    "I can't reach the AI model right now (no GOOGLE_API_KEY is set), so I can't answer open questions. "
                    "I can still look up a course (try \"prerequisites of CS301\"), and the Course Planner page works fully. "
                    "For anything else, please contact a human Academic Advisor."), "guard": "model_unavailable"})
                self._save_messages()
                st.rerun()
            # Keep the last 20 messages as context
            recent_messages = messages[-20:]
            chat_history = []
            for message in recent_messages:
                if message["role"] == "user":
                    content = message["content"]
                    for document in message.get("documents", []):
                        content += (
                            f"\n\nOCR text from {document['filename']}:\n"
                            f"{document['text']}"
                        )
                        workload = document.get("workload")
                        if workload:
                            topic_excerpts = "\n".join(
                                f"- Topic {topic['topic']}: {topic['excerpt']}"
                                for topic in workload["topics"]
                            )
                            content += (
                                f"\n\nWorkload estimate: {workload['estimated_hours']} "
                                f"study hours; {workload['word_count']} words; "
                                f"{workload['topic_count']} topic groups; "
                                f"diversity {workload['diversity']:.0%}.\n"
                                f"Representative topics:\n{topic_excerpts}"
                            )
                    chat_history.append(HumanMessage(content=content))
                elif message["role"] == "assistant":
                    chat_history.append(AIMessage(content=message["content"]))
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        response = self.llm.invoke([SystemMessage(content=self._build_system_prompt(user_text))] + chat_history)
                        reply = self.get_text(response.content)
                        reply, proposal, suggestion_error = self._parse_schedule_suggestion(reply)
                        # Save assistant response
                        assistant_message = {"role": "assistant", "content": reply}
                        if proposal:
                            assistant_message["proposal"] = proposal
                        if suggestion_error:
                            assistant_message["suggestion_error"] = suggestion_error
                        if documents:
                            local_response = self._create_local_workload_schedule_response(documents)
                            assistant_message["content"] = (
                                f"{reply}\n\n{local_response['content']}"
                            ).strip()
                            assistant_message.pop("proposal", None)
                            assistant_message.pop("suggestion_error", None)
                            if "proposal" in local_response:
                                assistant_message["proposal"] = local_response["proposal"]
                        messages.append(assistant_message)
                        self._save_messages()
                        st.rerun()
                    except Exception as error:
                        if documents:
                            st.warning(
                                "The AI chatbot could not respond, so a local workload-based "
                                "schedule proposal is shown instead."
                            )
                            messages.append(self._create_local_workload_schedule_response(documents))
                            self._save_messages()
                            st.rerun()
                        st.error(f"LLM error: {error}")
    # ======================================================
    # 7. MAIN WIDGET
    # ======================================================
    def render(self):
        page = st.segmented_control(
            "Academic simulator page",
            ["📊 Dashboard", "📚 Course Planner", "💬 Chatbot"],
            default="📊 Dashboard",
            key=f"{self.state_key}_active_page",
            label_visibility="collapsed",
        )
        if page == "📊 Dashboard":
            self.render_dashboard()
        elif page == "📚 Course Planner":
            self.course_planner.render()
        elif page == "💬 Chatbot":
            self.render_chatbot()
