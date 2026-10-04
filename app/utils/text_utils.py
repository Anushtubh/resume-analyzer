import re


def normalize_whitespace(text: str) -> str:
    """Normalize line endings, bullets, repeated spaces, and blank lines."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u2022", "- ").replace("\u25cf", "- ").replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def canonicalize_skill(skill: str) -> str:
    return re.sub(r"\s+", " ", skill.strip()).casefold()
