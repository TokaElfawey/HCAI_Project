import os
import streamlit as st
from academic_decision_simulator import AcademicDecisionSimulator
from gemini_llm import GeminiLLM
def load_environment_file():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    try:
        with open(env_path, "r", encoding="utf-8-sig") as env_file:
            for line_number, raw_line in enumerate(env_file, start=1):
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[len("export "):].lstrip()
                name, separator, value = line.partition("=")
                name = name.strip()
                if not separator or not name:
                    raise ValueError(f"Invalid .env entry on line {line_number}.")
                value = value.strip()
                if value.startswith(("'", '"')):
                    if len(value) < 2 or value[-1] != value[0]:
                        raise ValueError(f"Unclosed quote in .env on line {line_number}.")
                    value = value[1:-1]
                else:
                    value = value.split("#", 1)[0].rstrip()
                os.environ.setdefault(name, value)
    except FileNotFoundError:
        return
    except OSError as error:
        raise RuntimeError(f"Could not read environment file {env_path}: {error}") from error
def main():
    st.set_page_config(page_title="Academic Decision Simulator", page_icon="🎓", layout="wide")
    load_environment_file()
    st.title("🎓 Academic Decision Simulator")
    st.caption("Team Ctrl+Z Burnout · You stay in control: every draft is a proposal, never a decision.")
    system_prompt = """
    You are an Academic Decision Simulator.
    Your responsibilities:
    - Help students organize their academic schedules.
    - Help students prioritize their subjects.
    - Analyze their weekly workload.
    - Suggest improvements to their schedules.
    - Help students explore different scheduling options.
    Rules:
    - You are a simulator, not an academic advisor.
    - Never invent courses or prerequisites.
    - The student stays in control.
    - Credit overloads and special exceptions must be handled by a human Academic Advisor.
    - Keep responses under 120 words.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if api_key:
        try:
            llm = GeminiLLM(api_key)
        except ImportError as error:
            llm = None
            st.warning(
                f"Gemini replies are unavailable: {error}. "
                "Uploaded material can still receive a local workload-based schedule proposal."
            )
    else:
        llm = None
        st.warning(
            "Set GOOGLE_API_KEY to enable general chatbot replies. "
            "Uploaded material can still receive a local workload-based schedule proposal."
        )
    simulator = AcademicDecisionSimulator(llm=llm, system_prompt=system_prompt, start_hour=8, end_hour=22)
    if not os.path.exists(simulator.schedule_file):
        demo_activities = [("Machine Learning", 2, "Saturday", "10:00"), ("Deep Learning", 3, "Sunday", "12:00"), ("Computer Vision", 2, "Monday", "14:00"), ("Data Structures", 1, "Wednesday", "09:00"), ("Python", 2, "Thursday", "16:00")]
        for workname, duration, day, start_time in demo_activities:
            simulator.set_work(workname=workname, duration_hours=duration, day=day, start_time=start_time)
    simulator.render()
if __name__ == "__main__":
    main()
