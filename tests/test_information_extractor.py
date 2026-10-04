from app.services.information_extractor import extract_candidate_info, extract_skills


def test_skill_extraction_handles_special_terms():
    skills = extract_skills("Python, C++, C#, .NET, PyTorch and machine learning")
    assert {"Python", "C++", "C#", "Machine Learning", "PyTorch"}.issubset(skills)


def test_candidate_profile_is_structured():
    profile = extract_candidate_info("Alex\nSKILLS\nPython, SQL\nEXPERIENCE\nEngineer at Acme - 3 years\nEDUCATION\nB.Tech", "CAND_001", "a.pdf")
    assert profile.candidate_id == "CAND_001"
    assert "Python" in profile.skills
    assert profile.experience
