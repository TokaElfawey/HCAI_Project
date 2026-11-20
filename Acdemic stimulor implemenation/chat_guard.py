"""Deterministic safeguards that run BEFORE the LLM in the chatbot (no API key, no Streamlit needed).

What lives here (Week 5 flow: greeting, quick replies, error recovery, fallback, human handover):
  * GREETING and QUICK_REPLIES      - what the assistant can and cannot do
  * check(text, courses)            - returns {"category", "reply"} for requests the tool must not
                                      improvise on, or None to let the LLM answer
  * catalog_context(text, courses)  - real catalog facts handed to the LLM so it never invents courses

Categories: clarify, help, safety, dishonesty, handover, registration, catalog_lookup, unknown_course, out_of_scope.
"""
import re

CAN_CANNOT = (
    "**I can:** draft course plans from our course catalog, check prerequisites, explain a course, "
    "estimate weekly workload, and propose study sessions for your weekly schedule. You accept or cancel every proposal.\n\n"
    "**I cannot:** register you for courses, approve prerequisite waivers or credit overloads (over 18 credits), "
    "give medical, legal or personal advice, or know anything outside this synthetic course catalog. "
    "For those, please contact a human Academic Advisor."
)

GREETING = (
    "👋 Hi! I'm the **Academic Decision Simulator**. I'm a simulator, not an advisor: I make *drafts*, and you decide.\n\n"
    + CAN_CANNOT
    + "\n\nTell me your limits (for example max credits or days off), or try one of the quick replies below."
)

QUICK_REPLIES = [
    "What can you do?",
    "What are the prerequisites of CS301?",
    "Help me plan a light 12-credit semester",
    "I want to take 21 credits",
]

HANDOVER_NOTE = "Please contact a human Academic Advisor for this. I can't approve it, and I won't guess."

COURSE_ID = re.compile(r"\b([A-Za-z]{2,4})\s?(\d{3})\b")
ACADEMIC_WORDS = re.compile(
    r"course|credit|schedule|study|exam|class|semester|term|plan|prerequisite|workload|assignment|lecture|hours|"
    r"professor|major|department|timetable|lab\b|reading|deadline|burnout|وقت|مادة|جدول|ساعات|كورس",
    re.IGNORECASE)

SAFETY = re.compile(
    r"kill myself|end my life|suicid|hurt myself|self[- ]harm|want to die|don'?t want to live|no reason to live|انتحر|اقتل نفسي|مش عايز[ةه]? أعيش|مش عايز[ةه]? اعيش",
    re.IGNORECASE)
DISHONESTY = re.compile(
    r"cheat|fake (a |my )?(transcript|grade|certificate|document)|forge|change my grade|hack (the |my )?(portal|system|grades?)|"
    r"bypass (the )?(portal|registration|system)|write my (exam|assignment|essay) for me|answers? to the exam",
    re.IGNORECASE)
WAIVER = re.compile(r"waive|waiver|override|petition|appeal|special exception|make an exception|skip the prerequisite|without the prerequisite|without (taking )?prerequisites?", re.IGNORECASE)
REGISTRATION = re.compile(r"\b(register|enroll|enrol|sign) me\b|submit my registration|officially (drop|withdraw)|withdraw me from|add (it|this) to my (official )?registration", re.IGNORECASE)
CREDITS_NUMBER = re.compile(r"(\d{1,2})\s*(?:-|\s)?\s*(?:credit|cr\b|credits|credit hours)", re.IGNORECASE)
OVERLOAD_WORDS = re.compile(r"overload|more than 18|over 18|above 18", re.IGNORECASE)
HELP = re.compile(r"^\s*(help|\?+|hi|hello|hey|what can you do\??|what are you\??|who are you\??|مساعدة|ازاي|مرحبا|اهلا)\s*[.!?]*\s*$", re.IGNORECASE)
LOOKUP_WORDS = re.compile(r"prereq|co-?req|credit|workload|hours|offered|when|schedule slot|meet|about|what is|tell me|info|difficult|reading", re.IGNORECASE)
CHANGE_WORDS = re.compile(r"\b(add|move|remove|reschedule|put|swap)\b", re.IGNORECASE)
OUT_OF_SCOPE = re.compile(
    r"weather|recipe|football|soccer|movie|song|joke|stock|bitcoin|crypto|horoscope|poem|lyrics|write (me )?(a )?(python|code|script)|"
    r"diagnos|medication|prescri|symptom|lawyer|legal advice|who is the president|capital of|translate|visa|immigration|"
    r"dating|relationship advice|الطقس|وصفة|نكتة",
    re.IGNORECASE)


def _reply(category, text):
    return {"category": category, "reply": text}


def _course_facts(course):
    prereq = course.get("prerequisites", "None") or "None"
    terms = "/".join(course.get("terms", [])) or course.get("terms_offered", "")
    return (f"**{course['course_id']}: {course['course_name']}**\n"
            f"- Prerequisites: {prereq}\n"
            f"- {course['credits']} credits, level {course.get('level', '?')}, offered {terms}\n"
            f"- Meets: {course['schedule_slot']}\n"
            f"- Workload: about {course['weekly_study_hours']:g} hours/week · {course['difficulty_level']} · reading {course['reading_load']}\n"
            f"- Source: course_catalog.csv (synthetic data). Something looks wrong? Use \"Report an error\" on the course in the Course Planner.")


def check(text, courses=None):
    """Return {"category", "reply"} when a rule must answer, or None to let the LLM answer."""
    text = (text or "").strip()
    by_id = {c["course_id"].upper(): c for c in (courses or [])}
    if not re.search(r"[A-Za-z؀-ۿ0-9]", text) or len(re.findall(r"\w", text)) < 2:
        return _reply("clarify", "I didn't catch that. Could you tell me what you'd like to do, for example "
                                 "\"plan 12 credits with no 8 AM classes\" or \"prerequisites of CS301\"?")
    if SAFETY.search(text):
        return _reply("safety", "I'm really sorry you're feeling this way. I'm a course-planning tool, so I can't give you the support you deserve right now. "
                                "Please reach out to someone you trust, your university's counselling service, or your local emergency number. "
                                "If you want, I can help you write a short message asking someone to call or come over. We can come back to your schedule whenever you like.")
    if DISHONESTY.search(text):
        return _reply("dishonesty", "I can't help with cheating, forging records, or getting around university systems. "
                                    "I can help you plan study time for an exam, or explain what a course covers. " + HANDOVER_NOTE)
    credit_matches = [int(n) for n in CREDITS_NUMBER.findall(text)]
    if WAIVER.search(text):
        return _reply("handover", "Prerequisite waivers and special exceptions are decided by people, not by this tool. " + HANDOVER_NOTE +
                      " Meanwhile I can show which prerequisites a course lists and what you've completed.")
    if OVERLOAD_WORDS.search(text) or any(n > 18 for n in credit_matches):
        return _reply("handover", "Plans over 18 credits are a credit overload, and only a human Academic Advisor can approve that. " + HANDOVER_NOTE +
                      " I can draft a plan of 18 credits or fewer if you'd like.")
    if REGISTRATION.search(text):
        return _reply("registration", "I can't register, drop or withdraw you from courses. I only make draft plans, and nothing is final until you and your Academic Advisor decide. "
                                      "Want me to draft a plan you can bring to your advisor?")
    if HELP.match(text):
        return _reply("help", CAN_CANNOT)
    ids = [(a + b).upper() for a, b in COURSE_ID.findall(text)]
    if ids and not CHANGE_WORDS.search(text):
        known = [by_id[i] for i in ids if i in by_id]
        unknown = [i for i in ids if i not in by_id]
        if unknown and not known:
            return _reply("unknown_course", f"I can't find {', '.join(dict.fromkeys(unknown))} in the course catalog, so I won't guess about it. "
                                            "Check the course code, or ask an Academic Advisor. Course codes look like CS301 or MATH201.")
        if known and LOOKUP_WORDS.search(text):
            extra = (f"\n\nI also can't find {', '.join(unknown)} in the catalog." if unknown else "")
            return _reply("catalog_lookup", "\n\n".join(_course_facts(c) for c in known) + extra)
    if OUT_OF_SCOPE.search(text) and not ACADEMIC_WORDS.search(text):
        return _reply("out_of_scope", "That's outside what I can help with. " + CAN_CANNOT.replace("**I can:**", "**What I can do:**").split("\n\n")[0] +
                      " Would you like to try one of those?")
    return None


def catalog_context(text, courses, limit=8):
    """Facts about courses mentioned in the message (by code or by name words) to give to the LLM."""
    if not courses:
        return ""
    text_l = (text or "").lower()
    wanted = {(a + b).upper() for a, b in COURSE_ID.findall(text or "")}
    scored = []
    words = {w for w in re.findall(r"[a-z]{4,}", text_l)} - {"course", "courses", "credit", "credits", "plan", "study", "with", "that", "this", "what", "which", "about", "week", "hours"}
    for c in courses:
        score = 10 if c["course_id"].upper() in wanted else 0
        name_words = set(re.findall(r"[a-z]{4,}", c["course_name"].lower()))
        score += len(words & name_words)
        if score:
            scored.append((score, c["course_id"], c))
    scored.sort(key=lambda item: (-item[0], item[1]))
    lines = [f"- {c['course_id']}: {c['course_name']} | {c['credits']} credits | prerequisites: {c.get('prerequisites') or 'None'} | "
             f"{c['schedule_slot']} | ~{c['weekly_study_hours']:g} h/week | {c['difficulty_level']} | reading {c['reading_load']}"
             for _, _, c in scored[:limit]]
    return "\n".join(lines)
