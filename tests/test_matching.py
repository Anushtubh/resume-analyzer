from app.services.information_extractor import CandidateProfile
from app.services.matching_service import calculate_skill_match
from app.services.ranking_service import calculate_final_score


def test_skill_match():
    score, matched, missing = calculate_skill_match(["Python", "SQL", "AWS"], ["Python", "SQL"])
    assert score == 2 / 3
    assert matched == ["Python", "SQL"]
    assert missing == ["AWS"]


def test_core_scoring_formula():
    assert calculate_final_score(0.9, 0.8, 1.0, 1.0) == 0.89


def test_ranking_orders_candidates():
    from app.services.ranking_service import rank_candidates

    candidates = [CandidateProfile("A", "a.pdf", clean_text="Python"), CandidateProfile("B", "b.pdf", clean_text="Python")]
    results = rank_candidates(candidates, [{"candidate_id": "A", "similarity": 0.7}, {"candidate_id": "B", "similarity": 0.9}], "Python")
    assert [item.candidate.candidate_id for item in results] == ["B", "A"]
