"""Core pipeline for the Teaching Case Study Agent."""

from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from document_loader import load_all_documents
from prompts import (
    AUDIENCE_CALIBRATION,
    CASE_TYPE_GUIDANCE,
    EXTRACTION_PROMPT,
    SECTION_INSTRUCTIONS,
    SECTION_ORDER,
    SYSTEM_PROMPT,
    TEACHING_NOTE_PROMPT,
)

DEFAULT_MODEL = "claude-sonnet-4-6"
MAX_INPUT_CHARS = 600_000  # ~150K tokens, leave headroom in 200K window


class CaseAgent:
    """Orchestrates the 3-step case drafting pipeline."""

    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL):
        self.client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        self.model = model

    def _build_system_prompt(self, case_type: str, audience: str) -> list[dict]:
        """Compose system prompt with prompt caching enabled."""
        combined = (
            SYSTEM_PROMPT + "\n\n"
            + CASE_TYPE_GUIDANCE.get(case_type, CASE_TYPE_GUIDANCE["general"]) + "\n\n"
            + AUDIENCE_CALIBRATION.get(audience, AUDIENCE_CALIBRATION["undergrad"])
        )
        return [{"type": "text", "text": combined, "cache_control": {"type": "ephemeral"}}]

    def _call_api(self, system: list[dict], user_message: str, max_tokens: int = 4096) -> str:
        """Single API call, returns text response."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text

    # ── Step 1: Extract facts ────────────────────────────────────────────────

    def extract_facts(self, documents: list[dict], case_type: str, audience: str = "undergrad") -> str:
        """Extract structured facts from source documents."""
        doc_bundle = ""
        for doc in documents:
            doc_bundle += f"\n\n=== SOURCE: {doc['filename']} ({doc['file_type']}) ===\n"
            doc_bundle += doc["content"]

        if len(doc_bundle) > MAX_INPUT_CHARS:
            doc_bundle = doc_bundle[:MAX_INPUT_CHARS] + "\n\n[TRUNCATED — document bundle exceeded size limit]"

        system = self._build_system_prompt(case_type, audience)
        user_msg = EXTRACTION_PROMPT + doc_bundle
        return self._call_api(system, user_msg, max_tokens=8192)

    # ── Step 2: Draft sections ───────────────────────────────────────────────

    def draft_section(
        self,
        facts: str,
        section_name: str,
        prior_sections: dict,
        case_type: str,
        audience: str = "undergrad",
    ) -> str:
        """Draft a single case section, building on prior sections."""
        system = self._build_system_prompt(case_type, audience)

        prior_context = ""
        if prior_sections:
            prior_context = "\n\n--- PREVIOUSLY DRAFTED SECTIONS ---\n"
            for name, text in prior_sections.items():
                prior_context += f"\n## {name.replace('_', ' ').title()}\n{text}\n"

        instruction = SECTION_INSTRUCTIONS[section_name]
        user_msg = (
            f"## Extracted Facts\n{facts}\n\n"
            f"{prior_context}\n\n"
            f"## Your Task\n{instruction}"
        )
        return self._call_api(system, user_msg, max_tokens=3000)

    def draft_all_sections(
        self,
        facts: str,
        case_type: str,
        audience: str = "undergrad",
        callback=None,
    ) -> dict:
        """Draft all sections sequentially. callback(section_name, text) called after each."""
        sections = {}
        for section_name in SECTION_ORDER:
            text = self.draft_section(facts, section_name, sections, case_type, audience)
            sections[section_name] = text
            if callback:
                callback(section_name, text)
        return sections

    # ── Step 3: Teaching note ────────────────────────────────────────────────

    def draft_teaching_note(
        self, case_text: str, course_context: str, audience: str, case_type: str
    ) -> str:
        """Draft the instructor teaching note."""
        system = self._build_system_prompt(case_type, audience)
        prompt = TEACHING_NOTE_PROMPT.format(audience=audience, course_context=course_context)
        user_msg = f"## Complete Case\n{case_text}\n\n## Your Task\n{prompt}"
        return self._call_api(system, user_msg, max_tokens=8192)

    # ── Assembly and output ──────────────────────────────────────────────────

    @staticmethod
    def assemble_case(sections: dict) -> str:
        """Join all sections into a single markdown document."""
        parts = []
        for name in SECTION_ORDER:
            if name in sections:
                title = name.replace("_", " ").title()
                parts.append(f"# {title}\n\n{sections[name]}")
        return "\n\n---\n\n".join(parts)

    @staticmethod
    def write_outputs(output_dir: str, case_text: str, teaching_note: str) -> dict:
        """Write case and teaching note to timestamped markdown files."""
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        case_path = os.path.join(output_dir, f"case_{timestamp}.md")
        note_path = os.path.join(output_dir, f"teaching_note_{timestamp}.md")

        with open(case_path, "w") as f:
            f.write(case_text)
        with open(note_path, "w") as f:
            f.write(teaching_note)

        return {"case": case_path, "teaching_note": note_path}

    # ── Full pipeline ────────────────────────────────────────────────────────

    def run_full_pipeline(
        self,
        source_dir: str,
        output_dir: str,
        case_type: str,
        audience: str,
        course_context: str,
        progress_callback=None,
    ) -> dict:
        """Run the complete 3-step pipeline (CLI entry point)."""
        print("Step 1: Loading and extracting facts...")
        documents = load_all_documents(source_dir)
        if not documents:
            raise FileNotFoundError(f"No supported documents found in {source_dir}")
        print(f"  Loaded {len(documents)} documents")

        facts = self.extract_facts(documents, case_type, audience)
        print(f"  Extracted {len(facts):,} chars of structured facts")

        print("\nStep 2: Drafting case sections...")
        def _cli_callback(section_name, _text):
            print(f"  Drafted: {section_name.replace('_', ' ').title()}")

        sections = self.draft_all_sections(
            facts, case_type, audience, callback=progress_callback or _cli_callback
        )

        case_text = self.assemble_case(sections)

        print("\nStep 3: Drafting teaching note...")
        teaching_note = self.draft_teaching_note(case_text, course_context, audience, case_type)

        output_files = self.write_outputs(output_dir, case_text, teaching_note)
        print(f"\nDone. Outputs saved to {output_dir}")

        return {
            "facts": facts,
            "sections": sections,
            "case_text": case_text,
            "teaching_note": teaching_note,
            "output_files": output_files,
        }


if __name__ == "__main__":
    load_dotenv()

    parser = argparse.ArgumentParser(description="Teaching Case Study Agent")
    parser.add_argument("--source-dir", default="inputs/")
    parser.add_argument("--output-dir", default="outputs/")
    parser.add_argument("--case-type", default="general", choices=list(CASE_TYPE_GUIDANCE.keys()))
    parser.add_argument("--audience", default="undergrad", choices=list(AUDIENCE_CALIBRATION.keys()))
    parser.add_argument("--course-context", default="")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    agent = CaseAgent(model=args.model)
    result = agent.run_full_pipeline(
        args.source_dir, args.output_dir, args.case_type, args.audience, args.course_context
    )
    print(f"\n  Case:          {result['output_files']['case']}")
    print(f"  Teaching note: {result['output_files']['teaching_note']}")
