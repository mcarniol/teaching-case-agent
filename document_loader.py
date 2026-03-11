"""Load source documents (PDF, DOCX, HTML, TXT) into a uniform format."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pymupdf
from bs4 import BeautifulSoup
from docx import Document


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".html", ".htm", ".txt", ".md"}


def load_pdf(file_path: str) -> str:
    doc = pymupdf.open(file_path)
    pages = [page.get_text() for page in doc]
    doc.close()
    return "\n\n".join(pages)


def load_docx(file_path: str) -> str:
    doc = Document(file_path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def load_html(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def load_text(file_path: str) -> str:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        with open(file_path, "r", encoding="latin-1") as f:
            return f.read()


_LOADERS = {
    ".pdf": load_pdf,
    ".docx": load_docx,
    ".html": load_html,
    ".htm": load_html,
    ".txt": load_text,
    ".md": load_text,
}


def load_document(file_path: str) -> dict:
    """Load a single document and return {filename, content, file_type}."""
    path = Path(file_path)
    ext = path.suffix.lower()
    if ext not in _LOADERS:
        raise ValueError(f"Unsupported file type: {ext}")
    content = _LOADERS[ext](file_path)
    return {
        "filename": path.name,
        "content": content,
        "file_type": ext.lstrip("."),
    }


def load_all_documents(source_dir: str) -> list[dict]:
    """Walk source_dir and load all supported files."""
    documents = []
    for root, _dirs, files in os.walk(source_dir):
        for fname in sorted(files):
            ext = Path(fname).suffix.lower()
            if ext in SUPPORTED_EXTENSIONS:
                fpath = os.path.join(root, fname)
                try:
                    documents.append(load_document(fpath))
                except Exception as e:
                    print(f"Warning: skipping {fpath}: {e}")
    return documents


def load_uploaded_file(uploaded_file) -> dict:
    """Load a Streamlit UploadedFile into the standard format."""
    suffix = Path(uploaded_file.name).suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getbuffer())
        tmp_path = tmp.name
    try:
        doc = load_document(tmp_path)
        doc["filename"] = uploaded_file.name
        return doc
    finally:
        os.unlink(tmp_path)
