import streamlit as st
THEMES = {
    "Calm Blue": {
        "bg": "#F3F8FC",
        "surface": "#FFFFFF",
        "side": "#E8F1F9",
        "text": "#1F2D3D",
        "muted": "#4A5B6D",
        "border": "#BCD0E3",
        "accent": "#2F6690",
        "accent_h": "#255579",
        "tint": "#E6F0F9",
        "tint_h": "#D3E5F5",
        "bot": "#E4F0FA",
        "user": "#FFF1D6",
        "head1": "#D3E6F8",
        "head2": "#D9F1E6",
        "focus": "#1D4ED8",
    },
    "Warm Cream": {
        "bg": "#FBF6EA",
        "surface": "#FFFEFA",
        "side": "#F4ECD8",
        "text": "#2E2A24",
        "muted": "#5B5446",
        "border": "#DACBAA",
        "accent": "#2F6690",
        "accent_h": "#255579",
        "tint": "#F4EAD3",
        "tint_h": "#EADCBD",
        "bot": "#EDF3E3",
        "user": "#FCE9D0",
        "head1": "#F5E9CC",
        "head2": "#E9F1DC",
        "focus": "#1D4ED8",
    },
    "High Contrast": {
        "bg": "#FFFFFF",
        "surface": "#FFFFFF",
        "side": "#F2F2F2",
        "text": "#111111",
        "muted": "#222222",
        "border": "#111111",
        "accent": "#0B3D91",
        "accent_h": "#082C6C",
        "tint": "#FFFFFF",
        "tint_h": "#E3EAF8",
        "bot": "#FFFFFF",
        "user": "#F2F2F2",
        "head1": "#FFFFFF",
        "head2": "#FFFFFF",
        "focus": "#B00020",
    },
}
def apply_project_theme():
    with st.sidebar:
        st.subheader("♿ Appearance")
        theme_name = st.radio("Colors", list(THEMES), key="academic_theme", horizontal=True)
        text_size = st.radio("Text size", ["Normal", "Large", "Extra large"], key="academic_text_size", horizontal=True)
        dyslexia_mode = st.checkbox("Easy-to-read font and spacing", key="academic_dyslexia_mode")
    palette = THEMES[theme_name]
    font_size = {"Normal": 18, "Large": 21, "Extra large": 24}[text_size]
    font_family = "'Lexend', 'Verdana', sans-serif" if dyslexia_mode else "'Atkinson Hyperlegible', 'Segoe UI', 'Verdana', sans-serif"
    letter_spacing = "0.04em" if dyslexia_mode else "normal"
    line_height = "2.0" if dyslexia_mode else "1.7"
    border_width = "2.5px" if theme_name == "High Contrast" else "1.5px"
    css = """
    <style>
    :root {
        --app-bg: __bg__;
        --surface: __surface__;
        --side: __side__;
        --text: __text__;
        --muted: __muted__;
        --border: __border__;
        --accent: __accent__;
        --accent-hover: __accent_h__;
        --tint: __tint__;
        --tint-hover: __tint_h__;
        --bot: __bot__;
        --user: __user__;
        --head1: __head1__;
        --head2: __head2__;
        --focus: __focus__;
        --border-width: __border_width__;
    }
    html { font-size: __font_size__px; }
    .stApp {
        background: var(--app-bg);
        color: var(--text);
        color-scheme: light;
        font-family: __font_family__;
        letter-spacing: __letter_spacing__;
    }
    .stApp [data-testid="stMarkdownContainer"] p,
    .stApp [data-testid="stMarkdownContainer"] li,
    .stApp label,
    .stApp h1,
    .stApp h2,
    .stApp h3,
    .stApp h4 { color: var(--text); line-height: __line_height__; }
    .stApp [data-testid="stCaptionContainer"],
    .stApp [data-testid="stCaptionContainer"] *,
    .stApp small { color: var(--muted) !important; opacity: 1 !important; }
    .stApp [data-testid="stCaptionContainer"] { font-size: 0.9rem; line-height: 1.5; }
    .stApp [data-testid="stMarkdownContainer"] p,
    .stApp [data-testid="stMarkdownContainer"] li,
    .stApp [data-testid="stMarkdownContainer"] blockquote,
    .stApp [data-testid="stAlert"] p {
        max-width: 78ch;
        font-size: 1rem;
        text-wrap: pretty;
    }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stSidebar"] {
        background: var(--side);
        border-right: var(--border-width) solid var(--border);
    }
    .stApp h1 {
        padding: 0.65rem 1rem;
        border: var(--border-width) solid var(--border);
        border-radius: 18px;
        background: linear-gradient(120deg, var(--head1), var(--head2));
    }
    .stApp button[data-testid^="stBaseButton"],
    .stApp button[kind] {
        min-height: 46px;
        border-radius: 14px;
        font-weight: 700;
        box-shadow: none;
        background: var(--tint);
        color: var(--text);
        border: var(--border-width) solid var(--border);
        transition: background 0.15s ease, border-color 0.15s ease;
    }
    .stApp button[data-testid^="stBaseButton"] *,
    .stApp button[kind] * { color: inherit !important; white-space: normal !important; }
    .stApp button[data-testid^="stBaseButton"]:hover,
    .stApp button[kind]:hover {
        background: var(--tint-hover);
        border-color: var(--accent);
        color: var(--text);
    }
    .stApp button[data-testid="stBaseButton-primary"],
    .stApp button[kind="primary"],
    .stApp [data-testid="stForm"] button {
        background: var(--accent);
        color: #FFFFFF;
        border: var(--border-width) solid var(--accent);
    }
    .stApp button[data-testid="stBaseButton-primary"]:hover,
    .stApp button[kind="primary"]:hover,
    .stApp [data-testid="stForm"] button:hover {
        background: var(--accent-hover);
        border-color: var(--accent-hover);
        color: #FFFFFF;
    }
    .stApp button:disabled {
        opacity: 0.5;
        cursor: not-allowed;
        background: var(--tint);
        border-color: var(--border);
    }
    .stApp *:focus-visible {
        outline: 3px solid var(--focus) !important;
        outline-offset: 2px !important;
    }
    .stApp input,
    .stApp textarea {
        color: var(--text) !important;
        background: var(--surface) !important;
        font-size: 1rem !important;
        line-height: 1.5;
        min-height: 46px;
    }
    .stApp [data-testid="stTextAreaRootElement"],
    .stApp [data-testid="stTextAreaRootElement"] textarea,
    .stApp [data-testid="stTextArea"] [data-baseweb="textarea"],
    .stApp [data-testid="stTextArea"] textarea:disabled {
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
        background: #FFFFFF !important;
        opacity: 1 !important;
    }
    .stApp [data-baseweb="input"],
    .stApp [data-baseweb="base-input"] {
        background: var(--surface) !important;
        border-radius: 14px !important;
        border: var(--border-width) solid var(--border) !important;
    }
    .stApp [data-baseweb="select"] > div {
        background: var(--surface);
        border-radius: 14px;
        border: var(--border-width) solid var(--border);
        min-height: 46px;
    }
    .stApp [data-baseweb="select"] * { color: var(--text); font-size: 0.95rem; }
    .stApp a { color: var(--accent); text-decoration-thickness: 0.08em; text-underline-offset: 0.15em; }
    .stApp a:hover { color: var(--accent-hover); }
    .stApp [data-testid="stMetric"],
    .stApp [data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--surface);
        border: var(--border-width) solid var(--border);
        border-radius: 16px;
        padding: 0.75rem;
    }
    .stApp [data-testid="stChatMessage"] {
        color: var(--text) !important;
        background: var(--bot) !important;
        border: var(--border-width) solid var(--border);
        border-radius: 16px;
        padding: 0.75rem;
    }
    .stApp [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"],
    .stApp [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] *,
    .stApp [data-testid="stChatMessage"] [data-testid="stCaptionContainer"] *,
    .stApp [data-testid="stChatMessage"] li,
    .stApp [data-testid="stChatMessage"] p,
    .stApp [data-testid="stChatMessage"] span,
    .stApp [data-testid="stChatMessage"] strong {
        color: var(--text) !important;
        opacity: 1 !important;
    }
    .stApp [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
        background: var(--bot) !important;
    }
    .stApp [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
        background: var(--user) !important;
    }
    .stApp [data-testid="stChatMessage"] code {
        color: var(--text) !important;
        background: var(--tint) !important;
    }
    .stApp [data-testid="stChatMessage"] [data-testid="stAlertContainer"] {
        color: var(--text) !important;
        background: var(--surface) !important;
        border: var(--border-width) solid var(--border) !important;
        opacity: 1 !important;
    }
    .stApp [data-testid="stChatMessage"] [data-testid="stAlertContainer"] * {
        color: var(--text) !important;
        opacity: 1 !important;
    }
    .stApp [data-testid="stChatInput"] textarea::placeholder {
        color: var(--muted) !important;
        opacity: 1 !important;
    }
    .stApp [data-baseweb="tab-list"] { gap: 6px; }
    .stApp button[data-baseweb="tab"] {
        min-height: 46px;
        border-radius: 12px 12px 0 0;
        font-weight: 700;
    }
    .stApp button[data-baseweb="tab"]:hover { background: var(--tint); }
    .stApp [data-testid="stExpander"] {
        border: var(--border-width) solid var(--border);
        border-radius: 14px;
        background: var(--surface);
    }
    .stApp [data-testid="stExpander"] summary:hover { background: var(--tint); }
    .stApp [data-testid="stAlert"] { border-radius: 14px; }
    @media (prefers-reduced-motion: reduce) {
        * { transition: none !important; animation: none !important; }
    }
    </style>
    """
    for key, value in palette.items():
        css = css.replace(f"__{key}__", value)
    css = css.replace("__border_width__", border_width)
    css = css.replace("__font_size__", str(font_size))
    css = css.replace("__font_family__", font_family)
    css = css.replace("__letter_spacing__", letter_spacing)
    css = css.replace("__line_height__", line_height)
    st.markdown(css, unsafe_allow_html=True)
    return palette
