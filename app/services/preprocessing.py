import re

from app.utils.text_utils import normalize_whitespace


SECTION_HEADERS = {
    "summary", "profile", "skills", "technical skills", "education", "experience",
    "work experience", "employment", "projects", "certifications", "achievements",
}


def preprocess_text(text: str) -> str:
    """Clean extracted text while preserving technical terms and useful punctuation."""
    text = normalize_whitespace(text)
    text = re.sub(r"[\u200b\ufeff]", "", text)
    text = re.sub(r"[ \t]*[-–—][ \t]*", " - ", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def detect_sections(text: str) -> dict[str, str]:
    """Best-effort section splitter for common resume headings."""
    lines = [line.strip() for line in preprocess_text(text).splitlines() if line.strip()]
    sections: dict[str, list[str]] = {header: [] for header in SECTION_HEADERS}
    current = "summary"
    for line in lines:
        normalized = re.sub(r"[^a-z ]", "", line.casefold()).strip()
        if normalized in SECTION_HEADERS:
            current = normalized
        else:
            sections.setdefault(current, []).append(line)
    return {key: "\n".join(value).strip() for key, value in sections.items() if value}
