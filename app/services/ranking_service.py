from dataclasses import dataclass, asdict

from app.services.information_extractor import CandidateProfile
from app.services.matching_service import MatchBreakdown, calculate_match


@dataclass
class RankedCandidate:
    candidate: CandidateProfile
    match: MatchBreakdown
    final_score: float

    def to_dict(self):
        return {"candidate": self.candidate.to_dict(), "match": self.match.to_dict(), "final_score": self.final_score}


def calculate_final_score(semantic: float, skill: float, experience: float, education: float,
                         weights: dict[str, float] | None = None) -> float:
    weights = weights or {"semantic": 0.5, "skill": 0.3, "experience": 0.1, "education": 0.1}
    if abs(sum(weights.values()) - 1.0) > 1e-6:
        raise ValueError("Scoring weights must sum to 1.0")
    components = {"semantic": semantic, "skill": skill, "experience": experience, "education": education}
    if any(not 0 <= value <= 1 for value in components.values()):
        raise ValueError("Score components must be between 0 and 1")
    return round(sum(components[name] * weights[name] for name in components), 10)


def rank_candidates(candidates: list[CandidateProfile], retrievals: list[dict], jd_text: str) -> list[RankedCandidate]:
    by_id = {candidate.candidate_id: candidate for candidate in candidates}
    ranked = []
    for retrieval in retrievals:
        candidate = by_id.get(retrieval["candidate_id"])
        if not candidate:
            continue
        match = calculate_match(jd_text, candidate, retrieval["similarity"])
        score = calculate_final_score(match.semantic_similarity, match.skill_match,
                                      match.experience_match, match.education_match)
        ranked.append(RankedCandidate(candidate, match, score))
    return sorted(ranked, key=lambda item: item.final_score, reverse=True)
