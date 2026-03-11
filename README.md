# Teaching Case Study Agent

An AI-powered tool that drafts Harvard Business School-style teaching cases from source documents. Upload SEC filings, press releases, court documents, Form 990s, or news articles, and the agent extracts structured facts and drafts a complete case with teaching note.

## Features

- **PDF, DOCX, HTML, and TXT support** — handles SEC filings, legal documents, and more
- **5 case types** — Corporate Scandal, Nonprofit/Gov, Revenue Recognition, Financial Analysis, General
- **3 audience levels** — Undergraduate, MAcc, MBA
- **Step-by-step workflow** — extract facts, draft sections, generate teaching note
- **Human-in-the-loop** — review and edit every section before proceeding
- **Streamlit web UI** — no command line needed

## Quick Start

### 1. Clone and set up

```bash
git clone <your-repo-url>
cd teaching-case-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Add your API key

```bash
cp .env.example .env
# Edit .env and replace "your-key-here" with your Anthropic API key
```

Get an API key at [console.anthropic.com](https://console.anthropic.com/).

### 3. Run the app

```bash
streamlit run app.py
```

Open the URL shown in the terminal (usually http://localhost:8501).

## Usage

1. **Upload** source documents using the file uploader (PDF, DOCX, HTML, TXT)
2. **Configure** case type, audience, and course context in the sidebar
3. **Extract Facts** — the agent reads all documents and organizes key facts
4. **Draft Sections** — sections are drafted sequentially, each building on the last
5. **Draft Teaching Note** — generates synopsis, learning objectives, teaching plan, and model answers
6. **Export** — download the case and teaching note as markdown files

## CLI Usage

```bash
python agent.py \
  --source-dir inputs/ \
  --output-dir outputs/ \
  --case-type corporate_scandal \
  --audience macc \
  --course-context "Intermediate Accounting II, Week 10"
```

Options: `--case-type` (corporate_scandal, nonprofit_gov, revenue_recognition, financial_analysis, general), `--audience` (undergrad, macc, mba), `--model` (claude-sonnet-4-6, claude-haiku-4-5, claude-opus-4-6).

## Deploy to Streamlit Cloud

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect your repo
3. Set `app.py` as the main file
4. Add your `ANTHROPIC_API_KEY` in **Settings > Secrets**:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```
5. Deploy — colleagues access the app via a public URL

## Supported File Types

| Extension | Library |
|-----------|---------|
| `.pdf` | PyMuPDF |
| `.docx` | python-docx |
| `.html`, `.htm` | BeautifulSoup |
| `.txt`, `.md` | Built-in |

## Cost Estimate

| Model | Approximate cost per full case |
|-------|-------------------------------|
| claude-sonnet-4-6 | $0.50 - $2.00 |
| claude-haiku-4-5 | $0.05 - $0.20 |
| claude-opus-4-6 | $3.00 - $10.00 |

## Project Structure

```
teaching-case-agent/
├── app.py               # Streamlit web UI
├── agent.py             # Core pipeline (CaseAgent class)
├── prompts.py           # All LLM prompts and instructions
├── document_loader.py   # PDF/DOCX/HTML/TXT extraction
├── requirements.txt     # Python dependencies
├── .env.example         # API key template
├── .gitignore
├── .streamlit/
│   └── config.toml      # Streamlit theme and upload config
├── inputs/              # Drop source documents here (CLI mode)
└── outputs/             # Generated drafts (CLI mode)
```
