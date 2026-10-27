from app.services.information_extractor import (
    TECHNOLOGY_DICTIONARY,
    _extract_job_roles,
    extract_candidate_info,
    extract_experience,
    extract_skills,
)
from app.services.ner_service import ResumeNerService


def test_skill_extraction_handles_special_terms():
    skills = extract_skills("Python, C++, C#, .NET, PyTorch and machine learning")
    assert {"Python", "C++", "C#", "Machine Learning", "PyTorch"}.issubset(skills)


def test_technology_vocabulary_covers_common_ai_cloud_data_and_devops_tools():
    text = "LangChain, Hugging Face, scikit learn, PostgreSQL, AWS, Terraform, Airflow, GitHub Actions, Grafana"
    skills = extract_skills(text)
    assert {"LangChain", "Hugging Face", "Scikit-learn", "PostgreSQL", "AWS", "Terraform",
            "Apache Airflow", "GitHub Actions", "Grafana"}.issubset(skills)
    assert {"ai_ml", "cloud_and_devops", "data_and_analytics", "version_control_and_tools"}.issubset(TECHNOLOGY_DICTIONARY)


def test_skill_aliases_return_one_canonical_entry():
    skills = extract_skills("sklearn, scikit-learn, K8s, Kubernetes, GCP, Google Cloud")
    assert skills.count("Scikit-learn") == 1
    assert skills.count("Kubernetes") == 1
    assert skills.count("Google Cloud Platform") == 1
    assert extract_skills("R and C") == ["C", "R"]
    assert extract_skills("I have experience in r") == []


def test_role_and_experience_rules_cover_tech_titles_and_months():
    roles = _extract_job_roles(["Senior ML Engineer", "Cloud Architect", "Data Engineer"])
    assert roles == ["Machine Learning Engineer", "Cloud Architect", "Data Engineer"]
    assert extract_experience("3 years and 6 months; 18 mos; 2021-2024") == ["3 years and 6 months", "18 mos"]


def test_candidate_profile_is_structured():
    profile = extract_candidate_info("Alex\nSKILLS\nPython, SQL\nEXPERIENCE\nEngineer at Acme - 3 years\nEDUCATION\nB.Tech", "CAND_001", "a.pdf")
    assert profile.candidate_id == "CAND_001"
    assert "Python" in profile.skills
    assert profile.experience
    assert profile.extraction_method in {"rules", "rules_fallback_model_error", "fine_tuned_bert_ner+rules"}


def test_ner_service_reports_missing_local_checkpoint(tmp_path):
    assert ResumeNerService(tmp_path / "not-trained").extract_entities("Python engineer") is None
