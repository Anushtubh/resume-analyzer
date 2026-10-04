import re
from dataclasses import asdict, dataclass, field
from typing import Any

from app.services.preprocessing import detect_sections, preprocess_text
from app.utils.text_utils import canonicalize_skill


SKILL_DICTIONARY = [
    "Python", "Java", "C++", "C", "C#", "JavaScript", "TypeScript", "SQL", "MySQL",
    "PostgreSQL", "MongoDB", "HTML", "CSS", "React", "Node.js", "FastAPI", "Django",
    "Flask", "Machine Learning", "Deep Learning", "NLP", "Computer Vision", "TensorFlow",
    "PyTorch", "Keras", "Scikit-learn", "Pandas", "NumPy", "AWS", "Azure", "Docker",
    "Kubernetes", "Git", "GitHub", "Power BI", "Tableau", "Spark", "Hugging Face", "FAISS",
]


@dataclass
class CandidateProfile:
    candidate_id: str
    filename: str
    raw_text: str = ""
    clean_text: str = ""
    skills: list[str] = field(default_factory=list)
    education: list[str] = field(default_factory=list)
    companies: list[str] = field(default_factory=list)
    job_roles: list[str] = field(default_factory=list)
    experience: list[str] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def embedding_text(self) -> str:
        fields = [self.clean_text, "Skills: " + ", ".join(self.skills),
                  "Experience: " + ", ".join(self.experience),
                  "Projects: " + ", ".join(self.projects),
                  "Education: " + ", ".join(self.education)]
        return "\n".join(part for part in fields if part.strip())


def extract_skills(text: str, skill_dictionary: list[str] | None = None) -> list[str]:
    dictionary = skill_dictionary or SKILL_DICTIONARY
    found = []
    for skill in sorted(dictionary, key=len, reverse=True):
        pattern = rf"(?<![\w+#.]){re.escape(skill)}(?![\w+#.])"
        if re.search(pattern, text, flags=re.IGNORECASE) and canonicalize_skill(skill) not in {canonicalize_skill(x) for x in found}:
            found.append(skill)
    return sorted(found, key=canonicalize_skill)


def _section_values(sections: dict[str, str], *names: str) -> list[str]:
    value = "\n".join(sections.get(name, "") for name in names).strip()
    return [line.lstrip("- ").strip() for line in value.splitlines() if line.strip()]


def extract_candidate_info(text: str, candidate_id: str, filename: str) -> CandidateProfile:
    clean = preprocess_text(text)
    sections = detect_sections(clean)
    experience = _section_values(sections, "experience", "work experience", "employment")
    projects = _section_values(sections, "projects")
    education = _section_values(sections, "education")
    certifications = _section_values(sections, "certifications")
    roles = []
    for line in experience[:8]:
        if re.search(r"engineer|developer|scientist|analyst|manager|architect|intern", line, re.I):
            roles.append(line)
    years = re.findall(r"(?:\b\d+(?:\.\d+)?\+?\s*(?:years?|yrs?)\b)", clean, flags=re.I)
    companies = []
    for line in experience:
        match = re.search(r"(?:at|@|with)\s+([A-Z][\w& .-]{2,})", line)
        if match:
            companies.append(match.group(1).strip(" .,-"))
    return CandidateProfile(
        candidate_id=candidate_id,
        filename=filename,
        raw_text=text,
        clean_text=clean,
        skills=extract_skills(clean),
        education=education,
        companies=sorted(set(companies)),
        job_roles=roles,
        experience=sorted(set(years)),
        projects=projects,
        certifications=certifications,
    )
