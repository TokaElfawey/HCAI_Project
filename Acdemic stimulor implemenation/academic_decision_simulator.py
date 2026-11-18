import html
import json
import math
import os
import re
import uuid
from datetime import datetime
import streamlit as st
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
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
    # ======================================================
    # 3. GENERATE SCHEDULE HTML
    # ======================================================
    def _generate_schedule_html(self):
        schedule = st.session_state[self.schedule_key]
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
                border-radius: 10px;
            }
            .schedule-table {
                width: max-content;
                min-width: 100%;
                border-collapse: collapse;
                table-layout: fixed;
                text-align: center;
                font-family: Arial, sans-serif;
            }
            .schedule-table th,
            .schedule-table td {
                border: 1px solid #64748b;
                padding: 10px 6px;
                min-width: 78px;
                height: 65px;
                font-size: 12px;
            }
            .schedule-table th {
                background-color: #334155;
                color: white;
                font-weight: bold;
                white-space: nowrap;
            }
            .schedule-table .day-column {
                min-width: 110px;
                width: 110px;
            }
            .schedule-table .day-name {
                background-color: #475569;
                color: white;
                font-weight: bold;
                min-width: 110px;
            }
            .schedule-table .empty-cell {
                background-color: #f1f5f9;
            }
            .schedule-table .work-cell {
                background-color: #bfdbfe;
                color: #1e3a8a;
                font-weight: bold;
                border: 2px solid #3b82f6;
                overflow-wrap: anywhere;
            }
            .schedule-table .work-cell small {
                display: block;
                margin-top: 5px;
                font-weight: normal;
                font-size: 10px;
            }
        </style>
        <div class="schedule-wrapper">
            <table class="schedule-table">
                <thead>
                    <tr>
                        <th class="day-column">Day</th>
        """)
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
    def _build_system_prompt(self):
        return f"""
{self.system_prompt}
CURRENT STUDENT SCHEDULE:
{self.get_schedule_context()}
Instructions:
- Use the current schedule when answering questions.
- Do not invent scheduled activities.
- Do not claim that an activity was added or removed
  unless the backend actually performs that action.
- The student has full control over all schedule decisions.
- When a concrete schedule change would help, include one machine-readable
  proposal at the end of your response in this exact format:
  <schedule_suggestion>
  {{"reason":"short explanation","operations":[
    {{"action":"add","workname":"Activity","day":"Monday","start_time":"10:00","duration_hours":1}}
  ]}}
  </schedule_suggestion>
- Operations may use action "add" or "remove". A remove operation must include
  workname, day, and start_time. Do not include an operation unless the user
  asked for a schedule change or the suggestion is clearly useful. Never say
  the schedule has changed; the student must accept the proposal first.
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
                if action not in ("add", "remove"):
                    raise ValueError("Each change must use action add or remove.")
                for field in ("workname", "day", "start_time"):
                    if not isinstance(operation.get(field), str) or not operation[field].strip():
                        raise ValueError(f"Each change must include a valid {field}.")
                normalized = {"action": action, "workname": operation["workname"].strip(), "day": operation["day"].strip(), "start_time": operation["start_time"].strip()}
                if action == "add":
                    if "duration_hours" not in operation:
                        raise ValueError("An add change must include duration_hours.")
                    normalized["duration_hours"] = operation.get("duration_hours")
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
        for operation in operations:
            if operation["action"] == "add":
                success, message = self._add_work_to_schedule(proposed, operation["workname"], operation["duration_hours"], operation["day"], operation["start_time"])
            else:
                success, message = self._remove_work_from_schedule(proposed, operation["workname"], operation["day"], operation["start_time"])
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
                else:
                    details = f"{operation['workname']} | {operation['day']} | {start}"
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
        # Display conversation history
        for message in messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                self._render_schedule_proposal(message)
        # Chat input
        user_text = st.chat_input("Ask your academic assistant...", key=f"{self.state_key}_chat_input")
        if user_text:
            # Save user message
            messages.append({"role": "user", "content": user_text})
            self._save_messages()
            with st.chat_message("user"):
                st.markdown(user_text)
            if self.llm is None:
                st.error("The chatbot is unavailable until GOOGLE_API_KEY is configured.")
                return
            # Keep the last 20 messages as context
            recent_messages = messages[-20:]
            chat_history = []
            for message in recent_messages:
                if message["role"] == "user":
                    chat_history.append(HumanMessage(content=message["content"]))
                elif message["role"] == "assistant":
                    chat_history.append(AIMessage(content=message["content"]))
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        response = self.llm.invoke([SystemMessage(content=self._build_system_prompt())] + chat_history)
                        reply = self.get_text(response.content)
                        reply, proposal, suggestion_error = self._parse_schedule_suggestion(reply)
                        # Save assistant response
                        assistant_message = {"role": "assistant", "content": reply}
                        if proposal:
                            assistant_message["proposal"] = proposal
                        if suggestion_error:
                            assistant_message["suggestion_error"] = suggestion_error
                        messages.append(assistant_message)
                        self._save_messages()
                        st.rerun()
                    except Exception as error:
                        st.error(f"LLM error: {error}")
    # ======================================================
    # 7. MAIN WIDGET
    # ======================================================
    def render(self):
        dashboard_tab, chatbot_tab = st.tabs(["📊 Dashboard", "💬 Chatbot"])
        with dashboard_tab:
            self.render_dashboard()
        with chatbot_tab:
            self.render_chatbot()
