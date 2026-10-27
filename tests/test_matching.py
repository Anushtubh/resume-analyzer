from app.services.information_extractor import CandidateProfile
from app.services.matching_service import _years, calculate_experience_match, calculate_skill_match
from app.services.ranking_service import calculate_final_score


def test_skill_match():
    score, matched, missing = calculate_skill_match(["Python", "SQL", "AWS"], ["Python", "SQL"])
    assert score == 2 / 3
    assert matched == ["Python", "SQL"]
    assert missing == ["AWS"]


def test_core_scoring_formula():
    assert calculate_final_score(0.9, 0.8, 1.0, 1.0) == 0.89


def test_experience_parser_handles_years_months_and_plus():
    assert _years("Minimum 3+ years") == 3
    assert _years("2 years and 6 months") == 2.5
    assert _years("18 months") == 1.5


def test_experience_match_uses_months_as_fraction_of_year():
    candidate = CandidateProfile("A", "a.pdf", experience=["2 years and 6 months"])
    assert calculate_experience_match("3+ years required", candidate) == 2.5 / 3


def test_ranking_orders_candidates():
    from app.services.ranking_service import rank_candidates

    candidates = [CandidateProfile("A", "a.pdf", clean_text="Python"), CandidateProfile("B", "b.pdf", clean_text="Python")]
    results = rank_candidates(candidates, [{"candidate_id": "A", "similarity": 0.7}, {"candidate_id": "B", "similarity": 0.9}], "Python")
    assert [item.candidate.candidate_id for item in results] == ["B", "A"]
