🎓 Academic Decision Simulator

Team Ctrl+Z Burnout · Human-Centered AI (HCAI) course project Core HAI principle: User Control and Agency

The Academic Decision Simulator helps university students explore course plans and weekly schedules without being told what to do. It creates drafts, explains them, and lets the student reject, lock, edit and undo anything. Nothing is final without the student's confirmation, and anything outside the tool's limits goes to a human Academic Advisor.

Who it is for
Persona	Need	How the product helps
Lucía, commuter with ADHD	Fewer decisions at once, safe to experiment	Lock limits such as "no 8 AM", reject courses, Undo and Redo, one draft at a time
Samuel, student with dyslexia	Clear, short, readable screens	Colour themes, dyslexia-friendly font and spacing, plain labels, visible limits
Nour, senior international student	Trust, verifiable reasons, strict requirements	Prerequisite checks, "Why this course?", advisor handover for exceptions
Features
#	Feature	Ladder level
1	Constraints dashboard (credits, time, reading load) and one-click persona presets	1. Inform
2	Three-stage onboarding and an "It can / It cannot" panel	1. Inform
3	Human advisor handover for requests over 18 credits	1. Inform
4	Prerequisite check and "Why this course?" explanations	2. Explain
5	Up to three draft plans with Lock, Reject and Restore	3. Allow control
6	Undo and Redo (history of up to 50 steps)	3. Allow control
7	Weekly schedule with AI proposals that apply only after Accept	3. Allow control
8	Display options: colour themes (including High Contrast and Warm Cream) and dyslexia-friendly mode	1. Inform

The levels come from our HAI Principle Ladder v1 (Week 4): 1 Inform → 2 Explain → 3 Allow control → 4 Enable feedback.

Document analysis: uploaded course material (PDF or images) is read with OCR, its workload is estimated, and a study-session schedule is proposed, never applied automatically.

Safety rules
The assistant is a simulator, not an academic advisor.
It never invents courses or prerequisites. Plans come only from the course catalog.
It does not approve credit overloads (more than 18 credits), prerequisite waivers or exceptions. These go to a human Academic Advisor.
AI-suggested schedule changes stay pending until the student accepts them.
Use fictional or synthetic data only. Do not upload real personal documents.
Getting started
1. Requirements
Python 3.10 or newer (recommended)
A Google Gemini API key (optional, see below)
Internet access on the first run (OCR and embedding models are downloaded)
2. Install
bash
git clone https://github.com/TokaElfawey/HCAI_Project.git
cd HCAI_Project/academic_simulator
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

The requirements include torch, docling and sentence-transformers, so the first install can take several minutes. For NVIDIA GPU acceleration, install a CUDA-enabled PyTorch build.

3. Add your API key

Create a file named .env inside the academic_simulator folder (next to Dashboard.py):

GOOGLE_API_KEY=your_key_here

Never commit .env. You can copy .env.example as a starting point.

Without a key, the course planner and weekly schedule still work. Only the general Gemini chat replies are unavailable. Uploaded material can still receive a local workload-based schedule proposal.

4. Run
bash
streamlit run Dashboard.py

Open the address Streamlit prints (usually http://localhost:8501).

Try it (suggested walkthrough)
Follow the onboarding guide, then choose a student preset (Lucía, Samuel or Nour).
Press Generate drafts. Open "Why this course?" on a course.
Reject a course, then press Undo. Try Lock on another course.
Raise the credit limit above 18 to see the advisor handover message.
Open the weekly schedule. Ask the assistant for a change and choose Accept or Cancel.
Switch the colour theme or dyslexia-friendly mode in the display options.
Project structure
HCAI_Project/
├── README.md
├── Ctrl+Z Burnout Week 2-5.pdf         # course deliverables
└── academic_simulator/
    ├── Dashboard.py                    # entry point (Streamlit)
    ├── course_planner.py               # drafts, prerequisites, lock/reject, undo/redo, onboarding
    ├── academic_decision_simulator.py  # weekly schedule, chat, AI proposals
    ├── document_workload_analyzer.py   # OCR + workload estimate for course material
    ├── gemini_llm.py                   # Gemini API wrapper
    ├── project_theme.py                # colour themes and accessibility styling
    ├── requirements.txt
    └── data/
        └── course_catalog.csv          # synthetic course catalog

Files created at run time (not committed): data/academic_simulator_chat.json, data/academic_simulator_schedule.json, data/course_material_chroma/.

Course catalog columns

course_id, course_name, department, credits, weekly_study_hours, prerequisites, schedule_slot, difficulty_level, reading_load, description

Technology
Interface: Streamlit with custom CSS (themes, accessibility styling) and session state for history
LLM: Google Gemini through google-genai, wrapped to accept LangChain-style messages
Rules: deterministic Python code checks prerequisites, limits and schedule overlaps. The LLM never decides these.
Document analysis: Docling and RapidOCR for text extraction, sentence-transformers and ChromaDB for retrieval
Current status
✅ Course planner with drafts, prerequisite checks, Lock, Reject, Undo and Redo
✅ Advisor handover over 18 credits
✅ Weekly schedule with Accept / Cancel proposals
✅ Document workload analysis
✅ Colour themes and dyslexia-friendly mode
🔜 Error reporting and draft rating with re-planning (Ladder level 4)

👥 Contributors

Team Ctrl+Z Burnout

[**Toka Nasr**](https://github.com/TokaElfawey)

[**ِAya Nassser**](https://github.com/ayaah-ahmed)

[**Toka Alaa**](https://github.com/toka-alaa)

[**Mohamed Mostafa**](https://github.com/mohamed291133)

[**Yousif Hisham**](https://github.com/YousifHisham-tech)

Developed as part of the Human-AI Interaction coursework.
