"""Streamlit UI for the Teaching Case Study Agent."""

from __future__ import annotations

import os

import streamlit as st
from dotenv import load_dotenv

from agent import CaseAgent
from document_loader import load_uploaded_file
from prompts import (
    CASE_TYPE_GUIDANCE,
    AUDIENCE_CALIBRATION,
    SECTION_DISPLAY_NAMES,
    SECTION_ORDER,
)

load_dotenv()

# ── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Teaching Case Agent",
    page_icon=":mortar_board:",
    layout="wide",
)

# ── Session state defaults ───────────────────────────────────────────────────

_DEFAULTS = {
    "documents": [],
    "facts": None,
    "sections": {},
    "teaching_note": None,
}
for key, default in _DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_api_key() -> str | None:
    """Resolve API key: Streamlit secrets > env var > sidebar input."""
    # Streamlit Cloud stores secrets in st.secrets
    try:
        key = st.secrets.get("ANTHROPIC_API_KEY")
        if key:
            return key
    except Exception:
        pass
    return os.getenv("ANTHROPIC_API_KEY")


CASE_TYPE_OPTIONS = {
    "corporate_scandal": "Corporate Accounting Scandal",
    "nonprofit_gov": "Nonprofit / Government",
    "revenue_recognition": "Revenue Recognition",
    "financial_analysis": "Financial Statement Analysis",
    "general": "General Business Case",
}

AUDIENCE_OPTIONS = {
    "undergrad": "Undergraduate",
    "macc": "MAcc",
    "mba": "MBA",
}

MODEL_OPTIONS = [
    "claude-sonnet-4-6",
    "claude-haiku-4-5",
    "claude-opus-4-6",
]


# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("Teaching Case Agent")
    st.caption("HBS-style case drafting from source documents")
    st.divider()

    case_type_label = st.selectbox("Case Type", list(CASE_TYPE_OPTIONS.values()))
    case_type = [k for k, v in CASE_TYPE_OPTIONS.items() if v == case_type_label][0]

    audience_label = st.selectbox("Target Audience", list(AUDIENCE_OPTIONS.values()))
    audience = [k for k, v in AUDIENCE_OPTIONS.items() if v == audience_label][0]

    course_context = st.text_area(
        "Course Context",
        placeholder="e.g., Intermediate Accounting II, Week 10 revenue recognition module. "
        "Students have completed ASC 230 and basic ratio analysis.",
        height=120,
    )

    model = st.selectbox("Model", MODEL_OPTIONS)

    st.divider()

    api_key = _get_api_key()
    if not api_key:
        api_key = st.text_input("Anthropic API Key", type="password")
    if not api_key:
        st.warning("Add your API key to continue.")
    else:
        st.success("API key configured", icon="✅")

    st.divider()
    st.caption(
        "Cost estimate: ~$0.50-2.00 per full case with Sonnet. "
        "Haiku is cheaper for quick drafts."
    )


# ── Main area ────────────────────────────────────────────────────────────────

st.header("Step 1: Upload Source Documents")

uploaded_files = st.file_uploader(
    "Drop source documents here (SEC filings, press releases, court docs, Form 990s, news articles)",
    accept_multiple_files=True,
    type=["pdf", "docx", "txt", "md", "html", "htm"],
)

if uploaded_files:
    # Process uploads only if the file list changed
    current_names = sorted(f.name for f in uploaded_files)
    cached_names = sorted(d["filename"] for d in st.session_state.documents)
    if current_names != cached_names:
        docs = []
        for uf in uploaded_files:
            try:
                doc = load_uploaded_file(uf)
                docs.append(doc)
            except Exception as e:
                st.error(f"Failed to load {uf.name}: {e}")
        st.session_state.documents = docs

    if st.session_state.documents:
        with st.expander(f"Loaded {len(st.session_state.documents)} documents", expanded=False):
            for d in st.session_state.documents:
                st.write(f"**{d['filename']}** ({d['file_type']}) — {len(d['content']):,} chars")

# ── Extract facts ────────────────────────────────────────────────────────────

col_extract, col_clear = st.columns([1, 4])
with col_extract:
    extract_clicked = st.button(
        "Extract Facts",
        disabled=not st.session_state.documents or not api_key,
        type="primary",
    )

if extract_clicked and api_key:
    agent = CaseAgent(api_key=api_key, model=model)
    with st.status("Extracting facts from source documents...", expanded=True) as status:
        st.write(f"Processing {len(st.session_state.documents)} documents...")
        facts = agent.extract_facts(st.session_state.documents, case_type, audience)
        st.session_state.facts = facts
        st.session_state.sections = {}  # reset downstream
        st.session_state.teaching_note = None
        status.update(label="Facts extracted!", state="complete")

if st.session_state.facts:
    with st.expander("Extracted Facts (editable)", expanded=True):
        st.session_state.facts = st.text_area(
            "Review and edit before drafting",
            st.session_state.facts,
            height=400,
            label_visibility="collapsed",
        )

# ── Draft case sections ─────────────────────────────────────────────────────

st.header("Step 2: Draft Case Sections")

col_draft, _ = st.columns([1, 4])
with col_draft:
    draft_clicked = st.button(
        "Draft All Sections",
        disabled=not st.session_state.facts or not api_key,
        type="primary",
    )

if draft_clicked and api_key:
    agent = CaseAgent(api_key=api_key, model=model)
    progress_bar = st.progress(0, text="Starting...")
    status_container = st.status("Drafting case sections...", expanded=True)

    sections = {}
    for i, section_name in enumerate(SECTION_ORDER):
        display_name = SECTION_DISPLAY_NAMES[section_name]
        progress_bar.progress(
            (i) / len(SECTION_ORDER),
            text=f"Drafting: {display_name}...",
        )
        status_container.write(f"Drafting: {display_name}...")
        text = agent.draft_section(
            st.session_state.facts, section_name, sections, case_type, audience
        )
        sections[section_name] = text

    st.session_state.sections = sections
    st.session_state.teaching_note = None  # reset downstream
    progress_bar.progress(1.0, text="All sections drafted!")
    status_container.update(label="All sections drafted!", state="complete")

if st.session_state.sections:
    for section_name in SECTION_ORDER:
        if section_name in st.session_state.sections:
            display_name = SECTION_DISPLAY_NAMES[section_name]
            with st.expander(display_name, expanded=False):
                st.session_state.sections[section_name] = st.text_area(
                    f"Edit {display_name}",
                    st.session_state.sections[section_name],
                    height=300,
                    key=f"edit_{section_name}",
                    label_visibility="collapsed",
                )

# ── Teaching note ────────────────────────────────────────────────────────────

st.header("Step 3: Teaching Note")

col_tn, _ = st.columns([1, 4])
with col_tn:
    tn_clicked = st.button(
        "Draft Teaching Note",
        disabled=not st.session_state.sections or not api_key,
        type="primary",
    )

if tn_clicked and api_key:
    agent = CaseAgent(api_key=api_key, model=model)
    case_text = CaseAgent.assemble_case(st.session_state.sections)
    with st.status("Drafting teaching note...", expanded=True) as status:
        st.write("This may take a minute...")
        tn = agent.draft_teaching_note(case_text, course_context, audience, case_type)
        st.session_state.teaching_note = tn
        status.update(label="Teaching note drafted!", state="complete")

if st.session_state.teaching_note:
    with st.expander("Teaching Note (editable)", expanded=True):
        st.session_state.teaching_note = st.text_area(
            "Review and edit teaching note",
            st.session_state.teaching_note,
            height=500,
            label_visibility="collapsed",
        )

# ── Export ───────────────────────────────────────────────────────────────────

st.header("Step 4: Export")

col1, col2, _ = st.columns([1, 1, 3])

with col1:
    if st.session_state.sections:
        case_md = CaseAgent.assemble_case(st.session_state.sections)
        st.download_button(
            "Download Case (.md)",
            case_md,
            file_name="teaching_case.md",
            mime="text/markdown",
        )
    else:
        st.button("Download Case (.md)", disabled=True)

with col2:
    if st.session_state.teaching_note:
        st.download_button(
            "Download Teaching Note (.md)",
            st.session_state.teaching_note,
            file_name="teaching_note.md",
            mime="text/markdown",
        )
    else:
        st.button("Download Teaching Note (.md)", disabled=True)
