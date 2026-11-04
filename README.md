🎓 Academic Decision Simulator

Team: Ctrl+Z Burnout
Core HAI Principle: User Control and Agency

📖 Overview

The Academic Decision Simulator is an AI-powered advising tool designed to help university students build balanced, stress-free course schedules. Unlike traditional AI planners that dictate a final schedule, our simulator acts as a transparent advisor. It proposes options, explains its reasoning, and places the final decision-making power entirely in the hands of the student.

This project was built with accessibility and cognitive load in mind, specifically catering to students with interaction preferences like Dyslexia and ADHD, as well as students managing complex international or scholarship requirements.

🎯 Core Principle: User Control and Agency

Our guiding philosophy is that the AI is an advisor, not a dictator. The system never auto-saves and never forces a choice. It allows the user to safely explore the consequences of their academic decisions.

✨ Key Features

🎛️ Constraints Dashboard: Students set hard limits (e.g., "Max 15 hours/week", "No 8 AM classes") before the AI generates anything.

↩️ Universal Undo: Every action (changing a limit, rejecting a course) can be instantly reversed. Mistakes cost nothing, reducing decision anxiety.

❌ Granular Reject & Lock: Reject a single course instead of throwing away the whole draft, or "lock" a preferred constraint across regenerations.

🔍 Explainability Tags: Every course recommendation includes a "Why this fits" tag and a clickable prerequisite path to ensure the AI's logic is verifiable.

🧠 Bounded Choices: Generates a maximum of 3 drafts at a time to prevent choice overload.

🏗️ System Architecture

Our tech stack is designed to ensure accurate grounding, state management (for the Undo feature), and a responsive UI.

Frontend Interface: Streamlit (Features custom CSS for accessibility, sliders, and session state management).

Orchestration: LangChain / LangGraph (Manages conversational flows and state checkpoints).

LLM Engine: Hosted LLM API (OpenAI / Gemini) set to low temperature for deterministic, JSON-structured reasoning.

Knowledge Base (RAG): Vector Database (Chroma/FAISS) querying our synthetic dataset to prevent AI hallucinations.

Safeguards: Deterministic Rule Checker (Python scripts that strictly verify prerequisite math and credit limits before displaying to the user).

📊 Dataset (SUCWD)

To strictly preserve student privacy, this project does not use real academic data. We utilize the Synthetic University Course & Workload Dataset (SUCWD), a custom-generated dataset containing 120 synthetic courses and 2,000 mock student records, licensed under CC BY 4.0.

👥 Contributors

Team Ctrl+Z Burnout

ayaah-ahmed

toka-alaa

mohamed291133

YousifHisham-tech

Developed as part of the Human-AI Interaction coursework.
