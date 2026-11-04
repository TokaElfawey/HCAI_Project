import streamlit as st
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

# ---------- Page setup ----------
st.set_page_config(page_title="Academic Decision Simulator", page_icon="🎓")
st.title("🎓 Academic Decision Simulator")
st.caption("Team Ctrl+Z Burnout · You stay in control: every draft is a proposal, never a decision.")

# ---------- System prompt (our HAI principle baked in) ----------
SYSTEM_PROMPT = """You are the "Academic Decision Simulator", an assistant that helps university
students explore course-schedule options.
Rules:
- Greet warmly and briefly introduce yourself as a SIMULATOR that creates draft plans, not an advisor.
- Explain that the student stays in control: they can set constraints, reject any course, undo any step.
- Mention that credit overloads and special exceptions are handled by a human Academic Advisor.
- Never invent courses or prerequisites. Keep replies under 120 words.
- End by inviting the student to share constraints (e.g., max credits, days off)."""


def get_text(content):
    """Gemini may return a list of blocks; extract the plain text."""
    if isinstance(content, str):
        return content
    return "".join(
        b.get("text", "") if isinstance(b, dict) else str(b) for b in content
    )


# ---------- LLM (backend call) ----------
llm = ChatGoogleGenerativeAI(model="gemini-flash-lite-latest", temperature=0.3)

# ---------- Session state (chat history) ----------
if "messages" not in st.session_state:
    st.session_state.messages = []

# Render previous messages
for m in st.session_state.messages:
    role = "user" if isinstance(m, HumanMessage) else "assistant"
    with st.chat_message(role):
        st.markdown(m.content)

# ---------- Chat input ----------
if user_text := st.chat_input("Say hi to the simulator..."):
    st.session_state.messages.append(HumanMessage(content=user_text))
    with st.chat_message("user"):
        st.markdown(user_text)

    with st.chat_message("assistant"):
        with st.spinner("Calling LLM backend..."):
            response = llm.invoke(
                [SystemMessage(content=SYSTEM_PROMPT)] + st.session_state.messages
            )
        reply = get_text(response.content)
        st.markdown(reply)

    st.session_state.messages.append(AIMessage(content=reply))