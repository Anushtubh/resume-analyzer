import re
from dataclasses import dataclass, asdict

from app.services.information_extractor import CandidateProfile, extract_skills
from app.utils.text_utils import canonicalize_skill


@dataclass
class MatchBreakdown:
    semantic_similarity: float
    skill_match: float
    experience_match: float
    education_match: float
    matched_skills: list[str]
    missing_skills: list[str]

    def to_dict(self):
        return asdict(self)


def _years(text: str) -> float | None:
    values = [float(value) for value in re.findall(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)", text or "", re.I)]
    return max(values) if values else None


def calculate_skill_match(required: list[str], candidate: list[str]) -> tuple[float, list[str], list[str]]:
    candidate_keys = {canonicalize_skill(skill) for skill in candidate}
    matched = [skill for skill in required if canonicalize_skill(skill) in candidate_keys]
    missing = [skill for skill in required if canonicalize_skill(skill) not in candidate_keys]
    return (len(matched) / len(required) if required else 1.0, matched, missing)


def calculate_experience_match(jd_text: str, candidate: CandidateProfile) -> float:
    required, actual = _years(jd_text), _years(" ".join(candidate.experience) + " " + candidate.clean_text)
    if required is None:
        return 1.0 if actual is not None else 0.5
    if actual is None:
        return 0.0
    return min(actual / required, 1.0)


def calculate_education_match(jd_text: str, candidate: CandidateProfile) -> float:
    jd = (jd_text or "").casefold()
    education = " ".join(candidate.education + [candidate.clean_text]).casefold()
    degree_terms = ("bachelor", "b.tech", "btech", "master", "m.tech", "mtech", "computer science", "engineering", "degree")
    required = [term for term in degree_terms if term in jd]
    return 1.0 if not required else float(any(term in education for term in required))


def calculate_match(jd_text: str, candidate: CandidateProfile, semantic_similarity: float) -> MatchBreakdown:
    required_skills = extract_skills(jd_text)
    skill_score, matched, missing = calculate_skill_match(required_skills, candidate.skills)
    semantic = max(0.0, min(1.0, float(semantic_similarity)))
    return MatchBreakdown(semantic, skill_score, calculate_experience_match(jd_text, candidate),
                         calculate_education_match(jd_text, candidate), matched, missing)
