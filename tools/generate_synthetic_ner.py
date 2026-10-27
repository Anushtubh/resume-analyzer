"""Create reproducible, fictional, span-annotated resume examples for NER.

Annotations are produced alongside the text from typed segments, rather than
by searching generated prose after the fact. The resulting tokens use the
same uncased WordPiece vocabulary and BIO schema as the existing project data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from pathlib import Path

from transformers import AutoTokenizer


LABELS = [
    "O", "B-SKILL", "I-SKILL", "B-EDUCATION", "I-EDUCATION",
    "B-COMPANY", "I-COMPANY", "B-JOB_ROLE", "I-JOB_ROLE",
    "B-EXPERIENCE", "I-EXPERIENCE", "B-PROJECT", "I-PROJECT",
    "B-CERTIFICATION", "I-CERTIFICATION",
]

ROLES = [
    "Machine Learning Engineer", "Data Scientist", "NLP Engineer",
    "Data Analyst", "Backend Software Engineer", "Cloud Engineer",
    "DevOps Engineer", "Full Stack Developer", "Computer Vision Engineer",
    "AI Research Engineer", "Data Engineer", "Software Developer",
    "MLOps Engineer", "Business Intelligence Analyst", "QA Automation Engineer",
]
SKILLS = [
    "Python", "Java", "C++", "JavaScript", "TypeScript", "SQL", "PostgreSQL",
    "MySQL", "MongoDB", "Redis", "Pandas", "NumPy", "scikit-learn",
    "PyTorch", "TensorFlow", "Keras", "Hugging Face Transformers", "spaCy",
    "LangChain", "Computer Vision", "Natural Language Processing", "Deep Learning",
    "Machine Learning", "Apache Spark", "Airflow", "dbt", "Kafka", "FastAPI",
    "Django", "Flask", "React", "Node.js", "Spring Boot", "Docker", "Kubernetes",
    "AWS", "Microsoft Azure", "Google Cloud Platform", "Terraform", "Linux",
    "Git", "GitHub Actions", "Power BI", "Tableau", "MLflow", "ONNX",
    "OpenCV", "REST APIs", "CI/CD", "Jenkins", "R", "Excel",
]
EDUCATION = [
    "B.Tech in Computer Science", "Bachelor of Science in Data Science",
    "Master of Science in Artificial Intelligence", "M.Tech in Information Technology",
    "Bachelor of Engineering in Software Engineering", "Master of Computer Applications",
    "Bachelor of Science in Mathematics", "B.E. in Electronics and Communication",
    "Master of Science in Computer Science", "Bachelor of Computer Applications",
]
COMPANIES = [
    "Northstar Analytics", "BluePeak Systems", "Cedar Labs", "Vertex Cloud Works",
    "Juniper Data Studio", "Meridian Software Group", "Orchid AI Research",
    "Summit Digital Services", "Brightline Technologies", "Riverstone Products",
    "Atlas Platform Engineering", "Silver Fern Consulting", "Pioneer Robotics",
    "Coastal Metrics", "Redwood Applications",
]
PROJECTS = [
    "Customer Churn Prediction Platform", "Clinical Document Search Assistant",
    "Real-Time Fraud Detection Pipeline", "Retail Demand Forecasting System",
    "Multilingual Support Ticket Classifier", "Product Recommendation Engine",
    "Cloud Cost Anomaly Dashboard", "Visual Quality Inspection Service",
    "Streaming Event Analytics Platform", "Candidate Skill Taxonomy Explorer",
    "Invoice Extraction and Validation Workflow", "Energy Load Forecasting Model",
    "API Latency Monitoring Toolkit", "Semantic Knowledge Base Search",
    "Automated Model Drift Monitor",
]
CERTIFICATIONS = [
    "AWS Certified Machine Learning - Specialty", "Microsoft Certified Azure AI Engineer",
    "Google Cloud Professional Data Engineer", "Certified Kubernetes Administrator",
    "TensorFlow Developer Certificate", "Databricks Certified Data Engineer Associate",
    "HashiCorp Certified Terraform Associate", "AWS Certified Solutions Architect",
    "Professional Scrum Master I", "Microsoft Power BI Data Analyst Associate",
]
ACTION = [
    "Designed and delivered", "Built and maintained", "Led development of",
    "Implemented and supported", "Prototyped and deployed", "Improved and operated",
    "Developed and scaled", "Modernized and monitored",
]
OUTCOMES = [
    "reduced processing time by {n}%", "improved forecast accuracy by {n}%",
    "cut cloud spend by {n}%", "supported {n} daily requests",
    "increased analyst throughput by {n}%", "lowered production incidents by {n}%",
    "shortened release cycles by {n}%", "raised data quality to {n}%",
]
OPENERS = [
    "Professional Profile", "Career Summary", "About Me", "Summary",
    "Technical Profile", "Profile",
]
SKILL_HEADERS = ["Technical Skills", "Core Competencies", "Tools and Technologies", "Skills"]
ROLE_WORDING = [
    "working as a", "currently serving as", "most recently a", "joined as a",
    "held the position of", "contributed in the role of",
]
EXP_WORDING = [
    "with {n} years of professional experience", "bringing {n}+ years in technology",
    "with more than {n} years of industry experience", "for {n} years",
]

# Additional resume-informed vocabulary. Kept separate from the original
# generators so regenerating the earlier batches remains reproducible.
TECHNICAL_SKILLS_V3 = [
    "Python", "C++", "SQL", "JavaScript", "TypeScript", "React", "React Native",
    "Node.js", "FastAPI", "Flask", "REST APIs", "MongoDB", "MySQL", "ChromaDB",
    "Pandas", "NumPy", "scikit-learn", "XGBoost", "LightGBM", "CatBoost",
    "PyTorch", "TensorFlow", "Keras", "OpenCV", "YOLOv8", "MediaPipe",
    "Computer Vision", "Machine Learning", "Deep Learning", "Natural Language Processing",
    "Reinforcement Learning", "PPO", "SUMO", "CityFlow", "LangChain", "LangGraph",
    "Hugging Face", "RAG", "Vector Embeddings", "LLM Evaluation", "Prompt Engineering",
    "Gemini API", "SHAP", "Feature Engineering", "Exploratory Data Analysis",
    "Data Visualization", "Model Evaluation", "Cross-validation", "Class Imbalance Handling",
    "Isotonic Calibration", "MAE", "RMSE", "R-squared", "Precision and Recall",
    "F1-score", "ROC-AUC", "Matplotlib", "Seaborn", "Streamlit", "Git", "GitHub",
    "Jupyter", "Docker", "AWS", "HTML", "CSS", "Three.js", "PyMuPDF",
]
ROLES_V3 = [
    "AI Engineer", "Machine Learning Engineer", "Data Scientist", "Data Analyst",
    "AI and Data Science Intern", "Machine Learning Intern", "Data Science Intern",
    "Computer Vision Engineer", "NLP Engineer", "Applied AI Engineer",
    "Full Stack AI Developer", "Research Intern", "Analytics Engineer",
    "Software Engineer", "Business Data Analyst", "Robotics Engineer",
]
EDUCATION_V3 = [
    "B.Tech in Artificial Intelligence and Data Science", "B.E. in Computer Engineering",
    "Bachelor of Engineering in Information Technology", "B.Sc. in Data Science",
    "Bachelor of Technology in Computer Science", "M.Sc. in Artificial Intelligence",
    "Bachelor of Engineering in Electronics and Computer Engineering",
]
COMPANIES_V3 = [
    "Northstar Analytics Studio", "Cedar AI Lab", "BluePeak Data Systems",
    "Meridian Digital Works", "Orbit Data Research", "Juniper Software Lab",
    "Riverstone AI Studio", "Summit Product Engineering", "Atlas Innovation Group",
    "Brightline Applied Research", "Pinecone Technology Studio", "Coastal Robotics Lab",
]
PROJECTS_V3 = [
    ("Urban Mobility Signal Optimization Simulator", "simulated adaptive traffic signals and compared reinforcement-learning policies"),
    ("Explainable Policy Document Review Assistant", "retrieved evidence from policy documents and surfaced traceable review suggestions"),
    ("Multimodal Exercise Form Feedback Prototype", "estimated pose landmarks and summarized movement repetitions for a demo workflow"),
    ("Retail Demand and Inventory Forecasting Study", "compared regression baselines and translated forecast errors into planning insights"),
    ("Customer Segmentation and Campaign Analysis", "used exploratory analysis and clustering to describe interpretable customer groups"),
    ("Visual Defect Triage Demonstrator", "classified sample images and exposed confidence and review states to a simple interface"),
    ("Activity Recognition from Wearable Signals", "prepared time-series features and evaluated multiple classification approaches"),
    ("Context-Aware Course Recommendation Prototype", "combined interaction signals with content similarity for ranked suggestions"),
    ("Health Information Retrieval Demo", "indexed curated reference material and returned answer snippets with source context"),
    ("Road Scene Object Detection Dashboard", "ran object detection on sample clips and summarized counts in an interactive dashboard"),
    ("Demand Forecast Error Analysis Toolkit", "reported MAE and RMSE across seasonal validation windows"),
    ("Calibrated Risk Classification Experiment", "compared boosted-tree baselines and reviewed calibration and class-level metrics"),
    ("Agent Workflow for Structured Research Notes", "orchestrated retrieval and validation steps with explicit human review"),
    ("Service Request Topic Classification API", "served a text classification baseline through a lightweight REST endpoint"),
    ("Interactive Dataset Quality Explorer", "visualized missingness, outliers, and data-quality checks for analysts"),
    ("Personalized Product Similarity Search", "generated vector representations and retrieved related catalog items"),
]
CERTIFICATIONS_V3 = [
    "Applied Machine Learning Foundations Certificate", "Practical Deep Learning Workshop Certificate",
    "Cloud Fundamentals Learning Certificate", "Data Analytics with Python Certificate",
    "Responsible AI and Model Evaluation Workshop", "Computer Vision Foundations Certificate",
    "Generative AI Application Development Workshop",
]


def build_resume_pattern_set_three(rng: random.Random, index: int) -> list[tuple[str, str]]:
    """Technical student/early-career resumes informed by the supplied examples.

    Uses only fictional identities/employers and generalized project themes;
    each entity is annotated at composition time for trustworthy span labels.
    """
    parts: list[tuple[str, str]] = []
    domains = {
        "analytics": {
            "projects": [3, 4, 10, 11, 14],
            "skills": ["Python", "SQL", "Pandas", "NumPy", "scikit-learn", "XGBoost", "LightGBM", "CatBoost", "SHAP", "Feature Engineering", "Exploratory Data Analysis", "Data Visualization", "Model Evaluation", "Cross-validation", "Class Imbalance Handling", "Isotonic Calibration", "MAE", "RMSE", "R-squared", "Precision and Recall", "F1-score", "ROC-AUC", "Matplotlib", "Seaborn", "Streamlit", "Power BI"],
            "roles": ["Data Scientist", "Data Analyst", "Analytics Engineer", "Business Data Analyst", "AI and Data Science Intern", "Data Science Intern"],
        },
        "computer_vision": {
            "projects": [2, 5, 9],
            "skills": ["Python", "C++", "NumPy", "PyTorch", "TensorFlow", "Keras", "OpenCV", "YOLOv8", "MediaPipe", "Computer Vision", "Deep Learning", "Model Evaluation", "Streamlit", "React Native", "Node.js", "MongoDB"],
            "roles": ["Computer Vision Engineer", "Machine Learning Intern", "AI and Data Science Intern", "Applied AI Engineer", "Research Intern"],
        },
        "generative_ai": {
            "projects": [1, 8, 12, 13],
            "skills": ["Python", "Natural Language Processing", "LangChain", "LangGraph", "ChromaDB", "RAG", "Vector Embeddings", "LLM Evaluation", "Prompt Engineering", "Gemini API", "Hugging Face", "FastAPI", "Flask", "REST APIs", "PyMuPDF", "Streamlit", "Git", "Jupyter"],
            "roles": ["NLP Engineer", "AI Engineer", "Applied AI Engineer", "Full Stack AI Developer", "Machine Learning Intern", "AI and Data Science Intern"],
        },
        "recommendation": {
            "projects": [7, 15, 3, 4],
            "skills": ["Python", "SQL", "Pandas", "NumPy", "scikit-learn", "Machine Learning", "Feature Engineering", "Model Evaluation", "Cross-validation", "Vector Embeddings", "FastAPI", "MongoDB", "Matplotlib", "Seaborn", "Streamlit", "Git", "Jupyter"],
            "roles": ["Machine Learning Engineer", "Data Scientist", "AI and Data Science Intern", "Machine Learning Intern", "Software Engineer"],
        },
        "simulation": {
            "projects": [0, 9, 2, 5],
            "skills": ["Python", "C++", "NumPy", "PyTorch", "TensorFlow", "OpenCV", "YOLOv8", "Computer Vision", "Deep Learning", "Reinforcement Learning", "PPO", "SUMO", "CityFlow", "Model Evaluation", "Git", "Jupyter"],
            "roles": ["Robotics Engineer", "AI Engineer", "Machine Learning Intern", "Research Intern", "Applied AI Engineer"],
        },
        "full_stack_ai": {
            "projects": [1, 12, 13, 14],
            "skills": ["Python", "JavaScript", "TypeScript", "React", "React Native", "Node.js", "FastAPI", "Flask", "REST APIs", "MongoDB", "MySQL", "HTML", "CSS", "Three.js", "LangChain", "LangGraph", "RAG", "Vector Embeddings", "ChromaDB", "Streamlit", "Git", "Docker"],
            "roles": ["Full Stack AI Developer", "Software Engineer", "AI Engineer", "Applied AI Engineer", "AI and Data Science Intern"],
        },
    }
    domain_name = rng.choice(list(domains))
    domain = domains[domain_name]
    role = rng.choice(domain["roles"])
    degree = rng.choice(EDUCATION_V3)
    skills = rng.sample(domain["skills"], rng.randint(7, min(12, len(domain["skills"]))))
    project_count = rng.randint(2, min(4, len(domain["projects"])))
    projects = [PROJECTS_V3[i] for i in rng.sample(domain["projects"], project_count)]
    employers = rng.sample(COMPANIES_V3, rng.choice([0, 0, 1, 1, 2]))
    certs = rng.sample(CERTIFICATIONS_V3, rng.choice([0, 0, 1, 2]))
    years = rng.choice(["6 months", "8 months", "1 year", "1.5 years", "2 years", "3 years"])
    pattern = index % 18

    if pattern % 6 == 0:
        _add(parts, "PROFILE\nAspiring ")
        _add(parts, role, "JOB_ROLE")
        _add(parts, " focused on applied AI, careful experimentation, and useful software prototypes.\n\n")
    elif pattern % 6 == 1:
        _add(parts, "CAREER INTEREST: ")
        _add(parts, role, "JOB_ROLE")
        _add(parts, " | EARLY-CAREER TECHNICAL PROFILE\n\n")
    elif pattern % 6 == 2:
        _add(parts, "SUMMARY\nCombines academic work in data and computing with project experience as a ")
        _add(parts, role, "JOB_ROLE")
        _add(parts, ".\n\n")
    elif pattern % 6 == 3:
        _add(parts, "TARGET ROLE — ")
        _add(parts, role, "JOB_ROLE")
        _add(parts, "\nTECHNICAL EXPERIENCE — ")
        _add(parts, years, "EXPERIENCE")
        _add(parts, " across internships, labs, and project teams.\n\n")
    elif pattern % 6 == 4:
        _add(parts, "ABOUT\nA developing technology professional with ")
        _add(parts, years, "EXPERIENCE")
        _add(parts, " of hands-on project and internship work, seeking ")
        _add(parts, role, "JOB_ROLE")
        _add(parts, " opportunities.\n\n")
    else:
        _add(parts, "TECHNICAL CANDIDATE\n")
        _add(parts, role, "JOB_ROLE")
        _add(parts, " | project-led experience: ")
        _add(parts, years, "EXPERIENCE")
        _add(parts, "\n\n")

    sections = ["education", "skills", "projects", "experience", "achievements", "certifications"]
    layout = pattern % 6
    if layout == 1:
        sections = ["skills", "projects", "education", "achievements", "experience", "certifications"]
    elif layout == 2:
        sections = ["projects", "skills", "experience", "education", "certifications", "achievements"]
    elif layout == 3:
        sections = ["education", "experience", "projects", "skills", "certifications", "achievements"]
    elif layout == 4:
        sections = ["achievements", "projects", "skills", "education", "experience", "certifications"]
    elif layout == 5:
        sections = ["skills", "education", "experience", "certifications", "projects", "achievements"]

    for section in sections:
        if section == "education":
            _add(parts, rng.choice(["EDUCATION", "ACADEMIC BACKGROUND", "EDUCATION & COURSEWORK", "QUALIFICATIONS"]) + "\n")
            _add(parts, degree, "EDUCATION")
            _add(parts, "; coursework includes algorithms, statistics, and applied computing.\n\n")
        elif section == "skills":
            _add(parts, rng.choice(["TECHNICAL SKILLS", "TECH STACK", "TOOLS AND METHODS", "TECHNOLOGY PROFILE"]) + "\n")
            for i, skill in enumerate(rng.sample(skills, len(skills))):
                _add(parts, rng.choice(["", "• ", "- "]) if i else "")
                _add(parts, skill, "SKILL")
                _add(parts, rng.choice(["\n", ", ", " | ", "; "]))
            _add(parts, "\n")
        elif section == "projects":
            _add(parts, rng.choice(["PROJECTS", "SELECTED TECHNICAL PROJECTS", "PROJECT PORTFOLIO", "APPLIED WORK"]) + "\n")
            for title, description in projects:
                _add(parts, rng.choice(["• ", "- ", "Project: "]))
                _add(parts, title, "PROJECT")
                _add(parts, " — ")
                _add(parts, description + ". Stack: ")
                tools_used = rng.sample(skills, min(len(skills), rng.randint(2, 5)))
                for j, skill in enumerate(tools_used):
                    if j:
                        _add(parts, rng.choice([", ", " + ", " and "]))
                    _add(parts, skill, "SKILL")
                _add(parts, ".\n")
            _add(parts, "\n")
        elif section == "experience":
            if employers:
                _add(parts, rng.choice(["INTERNSHIP / TEAM EXPERIENCE", "EXPERIENCE", "RESEARCH AND INDUSTRY EXPOSURE"]) + "\n")
                for employer in employers:
                    _add(parts, "Contributed as a ")
                    _add(parts, role, "JOB_ROLE")
                    _add(parts, " with ")
                    _add(parts, years, "EXPERIENCE")
                    _add(parts, " at ")
                    _add(parts, employer, "COMPANY")
                    _add(parts, ", supporting data preparation, prototype evaluation, and team documentation.\n")
                _add(parts, "\n")
        elif section == "achievements":
            # Achievements are realistic synthetic resume prose, but the
            # existing NER schema has no ACHIEVEMENT class; leave untagged.
            _add(parts, rng.choice(["ACHIEVEMENTS", "HIGHLIGHTS", "COMMUNITY AND RECOGNITION"]) + "\n")
            achievements = [
                "Presented a working prototype at a campus innovation showcase.",
                "Collaborated in a small student team and documented reproducible experiments.",
                "Completed a peer-reviewed project demonstration with clear evaluation notes.",
                "Contributed to technical workshops and peer mentoring in a campus community.",
                "Earned recognition in a student technology challenge for a practical demo.",
                "Compared baseline and tuned models and summarized trade-offs for reviewers.",
                "Built an accessible dashboard to communicate results to non-technical users.",
                "Shared project findings through a short poster or technical presentation.",
            ]
            for achievement in rng.sample(achievements, rng.randint(1, 2)):
                _add(parts, "• " + achievement + "\n")
            _add(parts, "\n")
        elif section == "certifications" and certs:
            _add(parts, rng.choice(["CERTIFICATIONS", "WORKSHOPS", "PROFESSIONAL DEVELOPMENT"]) + "\n")
            for cert in certs:
                _add(parts, "• ")
                _add(parts, cert, "CERTIFICATION")
                _add(parts, "\n")
            _add(parts, "\n")
    _add(parts, "Additional interests include responsible AI, clear communication, and continued technical learning.\n")
    return parts


def _append_segment(parts: list[tuple[str, str]], text: str, entity: str = "O") -> None:
    if not text:
        return
    if parts and parts[-1][1] == "O" and entity == "O":
        previous, _ = parts.pop()
        parts.append((previous + text, "O"))
    else:
        parts.append((text, entity))


def _add(parts: list[tuple[str, str]], text: str, entity: str = "O") -> None:
    _append_segment(parts, text, entity)


def _skills_line(rng: random.Random, skills: list[str]) -> str:
    separator = rng.choice([", ", " | ", "; ", " • "])
    return separator.join(skills)


def build_resume(rng: random.Random, index: int) -> list[tuple[str, str]]:
    parts: list[tuple[str, str]] = []
    role = rng.choice(ROLES)
    exp_years = rng.randint(0, 16)
    company_count = rng.choice([1, 1, 2, 2, 3])
    companies = rng.sample(COMPANIES, company_count)
    education = rng.choice(EDUCATION)
    skill_count = rng.randint(5, 11)
    skills = rng.sample(SKILLS, skill_count)
    projects = rng.sample(PROJECTS, rng.randint(1, 3))
    certifications = rng.sample(CERTIFICATIONS, rng.randint(0, 2))
    phrasing = index % 8

    if phrasing in {0, 1, 4}:
        _add(parts, rng.choice(OPENERS) + "\n")
        _add(parts, "A ")
        _add(parts, role, "JOB_ROLE")
        _add(parts, " ")
        exp_text = rng.choice(EXP_WORDING).format(n=exp_years)
        _add(parts, exp_text, "EXPERIENCE")
        _add(parts, ". I enjoy solving practical problems and delivering dependable software.\n\n")
    elif phrasing in {2, 5}:
        _add(parts, f"{role} | {exp_years} years in the industry\n")
        # The title and tenure are represented as separate entities, matching
        # the source corpus' distinction between role and experience spans.
        # Rebuild the first line with explicit typed spans.
        parts.pop()
        _add(parts, role, "JOB_ROLE")
        _add(parts, f" | {exp_years} years in the industry\n\n")
        _add(parts, "Career Overview\n")
        _add(parts, f"Technology professional with {exp_years} years of experience supporting product teams.\n\n")
    else:
        _add(parts, "CAREER OBJECTIVE\n")
        _add(parts, "Seeking to apply my background as a ")
        _add(parts, role, "JOB_ROLE")
        _add(parts, " to customer-focused products.\n\n")

    if phrasing % 3 == 0:
        _add(parts, "Professional Experience\n")
        for company in companies:
            _add(parts, f"{rng.choice(ROLE_WORDING)} ")
            _add(parts, role, "JOB_ROLE")
            _add(parts, " at ")
            _add(parts, company, "COMPANY")
            _add(parts, f" ({rng.randint(2014, 2024)}–{rng.randint(2024, 2026)}):\n")
            _add(parts, f"{rng.choice(ACTION)} ")
            _add(parts, rng.sample(skills, min(len(skills), rng.randint(2, 4)))[0], "SKILL")
            _add(parts, "-based services and data workflows; ")
            _add(parts, rng.choice(OUTCOMES).format(n=rng.choice([12, 18, 23, 31, 37, 42])))
            _add(parts, ". Collaborated with engineering and business stakeholders.\n")
        _add(parts, "\n")
    else:
        _add(parts, "Experience\n")
        _add(parts, "Over the course of my career, I have worked with teams at ")
        for pos, company in enumerate(companies):
            if pos:
                _add(parts, " and ")
            _add(parts, company, "COMPANY")
        _add(parts, f". I have {exp_years} years of relevant experience in software delivery.\n\n")

    _add(parts, rng.choice(SKILL_HEADERS) + "\n")
    for pos, skill in enumerate(skills):
        if pos:
            _add(parts, rng.choice([", ", " • ", " | ", "; "]))
        _add(parts, skill, "SKILL")
    _add(parts, "\n\n")

    _add(parts, rng.choice(["Selected Projects", "Projects", "Project Work", "Portfolio Projects"]) + "\n")
    for project in projects:
        _add(parts, "- ")
        _add(parts, project, "PROJECT")
        _add(parts, ": applied ")
        mentioned = rng.sample(skills, min(len(skills), rng.randint(1, 3)))
        for pos, skill in enumerate(mentioned):
            if pos:
                _add(parts, " and ")
            _add(parts, skill, "SKILL")
        _add(parts, " to create a reliable solution for internal users.\n")
    _add(parts, "\nEducation\n")
    _add(parts, education, "EDUCATION")
    _add(parts, f" | {rng.choice([2012, 2014, 2016, 2018, 2020, 2022, 2024])}\n")
    if certifications:
        _add(parts, "\nCertifications\n")
        for certificate in certifications:
            _add(parts, "- ")
            _add(parts, certificate, "CERTIFICATION")
            _add(parts, "\n")
    _add(parts, "\nAdditional Information\nEnjoys mentoring teammates, documenting systems, and learning new tools.\n")
    return parts


def build_resume_pattern_set_two(rng: random.Random, index: int) -> list[tuple[str, str]]:
    """A second pattern family with different section order and sentence forms."""
    parts: list[tuple[str, str]] = []
    role = rng.choice(ROLES)
    years = rng.randint(0, 18)
    employers = rng.sample(COMPANIES, rng.choice([1, 1, 2, 3]))
    degree = rng.choice(EDUCATION)
    skills = rng.sample(SKILLS, rng.randint(5, 12))
    projects = rng.sample(PROJECTS, rng.randint(1, 3))
    credentials = rng.sample(CERTIFICATIONS, rng.randint(0, 2))
    pattern = index % 12
    tenure = f"{years} years"

    # Twelve visibly different resume layouts/section orders. Entities are
    # emitted as typed spans as the prose is composed, never inferred later.
    if pattern in {0, 6}:
        _add(parts, "TARGET POSITION\n")
        _add(parts, role, "JOB_ROLE")
        _add(parts, "\nCAREER LENGTH\n")
        _add(parts, tenure, "EXPERIENCE")
        _add(parts, " in software and data teams\n\n")
    elif pattern in {1, 7}:
        _add(parts, "CAREER SNAPSHOT | ")
        _add(parts, role, "JOB_ROLE")
        _add(parts, " | ")
        _add(parts, tenure, "EXPERIENCE")
        _add(parts, " delivering production systems\n\n")
    elif pattern in {2, 8}:
        _add(parts, "PROFILE\nMy work has centered on ")
        _add(parts, role, "JOB_ROLE")
        _add(parts, " responsibilities, backed by ")
        _add(parts, tenure, "EXPERIENCE")
        _add(parts, " of hands-on delivery.\n\n")
    elif pattern in {3, 9}:
        _add(parts, "ROLE: ")
        _add(parts, role, "JOB_ROLE")
        _add(parts, "\nTENURE: ")
        _add(parts, tenure, "EXPERIENCE")
        _add(parts, "\n\nPROFILE\nFocused on maintainable products and measurable outcomes.\n\n")
    elif pattern == 4:
        _add(parts, "CAREER OBJECTIVE\nSeeking a position where my experience as ")
        _add(parts, role, "JOB_ROLE")
        _add(parts, " and ")
        _add(parts, tenure, "EXPERIENCE")
        _add(parts, " can support a collaborative engineering team.\n\n")
    else:
        _add(parts, "BIOGRAPHICAL SUMMARY\nA technology practitioner for ")
        _add(parts, tenure, "EXPERIENCE")
        _add(parts, ", currently working as a ")
        _add(parts, role, "JOB_ROLE")
        _add(parts, ".\n\n")

    sections = ["experience", "skills", "education", "projects", "certifications"]
    if pattern in {1, 5, 9}:
        sections = ["skills", "projects", "experience", "certifications", "education"]
    elif pattern in {2, 6, 10}:
        sections = ["education", "experience", "skills", "certifications", "projects"]
    elif pattern in {3, 7, 11}:
        sections = ["projects", "skills", "education", "experience", "certifications"]

    for section in sections:
        if section == "experience":
            _add(parts, rng.choice(["EMPLOYMENT HISTORY", "CAREER RECORD", "WORK HISTORY", "PROFESSIONAL EXPERIENCE"]) + "\n")
            for employer_index, employer in enumerate(employers):
                tenure_part = f"{max(1, years - employer_index)} years"
                style = (pattern + employer_index) % 4
                if style == 0:
                    _add(parts, "Position — ")
                    _add(parts, role, "JOB_ROLE")
                    _add(parts, " | Employer — ")
                    _add(parts, employer, "COMPANY")
                    _add(parts, " | Time in role — ")
                    _add(parts, tenure_part, "EXPERIENCE")
                    _add(parts, "\n")
                elif style == 1:
                    _add(parts, "At ")
                    _add(parts, employer, "COMPANY")
                    _add(parts, ", served as ")
                    _add(parts, role, "JOB_ROLE")
                    _add(parts, " for ")
                    _add(parts, tenure_part, "EXPERIENCE")
                    _add(parts, ".\n")
                elif style == 2:
                    _add(parts, "• ")
                    _add(parts, role, "JOB_ROLE")
                    _add(parts, " — ")
                    _add(parts, employer, "COMPANY")
                    _add(parts, " (")
                    _add(parts, tenure_part, "EXPERIENCE")
                    _add(parts, ")\n")
                else:
                    _add(parts, "Organization: ")
                    _add(parts, employer, "COMPANY")
                    _add(parts, "\nJob title: ")
                    _add(parts, role, "JOB_ROLE")
                    _add(parts, "\nRelevant tenure: ")
                    _add(parts, tenure_part, "EXPERIENCE")
                    _add(parts, "\n")
                contribution = rng.choice([
                    "Delivered an internal analytics workflow using ",
                    "Automated a recurring service operation with ",
                    "Maintained a customer-facing platform built with ",
                    "Improved data validation processes through ",
                    "Partnered with product teams to launch work using ",
                ])
                _add(parts, contribution)
                _add(parts, rng.choice(skills), "SKILL")
                _add(parts, f" and {rng.choice(skills)}; the change {rng.choice(OUTCOMES).format(n=rng.choice([14, 19, 26, 33, 41]))}.\n")
            _add(parts, "\n")
        elif section == "skills":
            _add(parts, rng.choice(["TECHNICAL TOOLKIT", "TECHNOLOGY STACK", "TOOLS / METHODS", "AREAS OF PRACTICE"]) + "\n")
            order = list(skills)
            rng.shuffle(order)
            for skill_index, skill in enumerate(order):
                prefix = rng.choice(["", "- ", "   • "]) if skill_index else ""
                _add(parts, prefix)
                _add(parts, skill, "SKILL")
                _add(parts, rng.choice(["\n", ", ", "  /  "]))
            _add(parts, "\n")
        elif section == "education":
            _add(parts, rng.choice(["ACADEMIC BACKGROUND", "EDUCATION & TRAINING", "QUALIFICATIONS", "EDUCATION"]) + "\n")
            _add(parts, rng.choice(["Degree earned: ", "Program: ", "Academic qualification — ", ""]))
            _add(parts, degree, "EDUCATION")
            _add(parts, f"; completed {rng.choice([2013, 2015, 2017, 2019, 2021, 2023, 2025])}.\n\n")
        elif section == "projects":
            _add(parts, rng.choice(["PROJECT PORTFOLIO", "SELECTED WORK", "DELIVERY HIGHLIGHTS", "PROJECTS"]) + "\n")
            for project in projects:
                _add(parts, rng.choice(["• ", "- ", "Project: "]))
                _add(parts, project, "PROJECT")
                _add(parts, rng.choice([" — used ", ": implemented with ", ". Built around "]))
                tools_used = rng.sample(skills, min(len(skills), rng.randint(1, 3)))
                for tool_index, skill in enumerate(tools_used):
                    if tool_index:
                        _add(parts, " plus ")
                    _add(parts, skill, "SKILL")
                _add(parts, rng.choice([" to improve team workflows.\n", " for a production use case.\n", " with monitoring and documentation.\n"]))
            _add(parts, "\n")
        elif section == "certifications" and credentials:
            _add(parts, rng.choice(["CREDENTIALS", "CERTIFICATIONS", "PROFESSIONAL DEVELOPMENT"]) + "\n")
            for credential in credentials:
                _add(parts, rng.choice(["• ", "- ", "Completed: "]))
                _add(parts, credential, "CERTIFICATION")
                _add(parts, "\n")
            _add(parts, "\n")

    _add(parts, rng.choice([
        "ADDITIONAL\nEnjoys cross-team planning, peer learning, and clear technical documentation.\n",
        "OTHER CONTRIBUTIONS\nSupports knowledge sharing and continuous improvement across teams.\n",
        "WORKING STYLE\nValues careful problem framing, accessible communication, and reliable delivery.\n",
    ]))
    return parts


def tokenize_labeled(parts: list[tuple[str, str]], tokenizer) -> tuple[list[str], list[str]]:
    tokens: list[str] = []
    tags: list[str] = []
    for text, entity in parts:
        words = tokenizer.tokenize(text)
        if not words:
            continue
        if entity == "O":
            tokens.extend(words)
            tags.extend(["O"] * len(words))
        else:
            tokens.extend(words)
            tags.extend([f"B-{entity}", *([f"I-{entity}"] * (len(words) - 1))])
    return tokens, tags


def split_chunks(document_id: str, tokens: list[str], tags: list[str], chunk_size: int) -> list[dict]:
    records = []
    start = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        # Avoid cutting through an entity span when a nearby safe boundary exists.
        if end < len(tokens) and tags[end].startswith("I-"):
            while end > start and tags[end].startswith("I-"):
                end -= 1
            if end == start:
                end = min(start + chunk_size, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_tags = tags[start:end]
        records.append({
            "document_id": document_id,
            "chunk_id": len(records),
            "tokens": chunk_tokens,
            "ner_tags": chunk_tags,
            "ner_tag_ids": [LABELS.index(tag) for tag in chunk_tags],
        })
        start = end
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20261018)
    parser.add_argument("--pattern-set", type=int, choices=[1, 2, 3], default=1,
                        help="Pattern 3 uses technical student/early-career resume patterns")
    parser.add_argument("--offset", type=int, default=0,
                        help="Starting ID offset, e.g. 1000 generates synthetic_1001 onward")
    parser.add_argument("--dedupe-against", type=Path, action="append", default=[],
                        help="Reviewable source JSONL to deduplicate against (may be repeated)")
    parser.add_argument("--output-dir", type=Path, default=Path("data/ner_synthetic_1000"))
    parser.add_argument("--tokenizer", default="C:/Users/shrav/.cache/huggingface/hub/models--BAAI--bge-small-en-v1.5/snapshots/5c38ec7c405ec4b44b94cc5a9bb96e735b38267a")
    parser.add_argument("--chunk-size", type=int, default=510)
    args = parser.parse_args()
    if args.count < 1 or not 1 <= args.chunk_size <= 510:
        parser.error("count and chunk-size must be positive; chunk-size cannot exceed 510")
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, use_fast=True, local_files_only=True)
    rng = random.Random(args.seed)
    records: list[dict] = []
    source_records: list[dict] = []
    hashes: set[str] = set()
    for prior_path in args.dedupe_against:
        with prior_path.open(encoding="utf-8") as previous_source:
            for line in previous_source:
                previous = json.loads(line)
                normalized = re.sub(r"\s+", " ", previous["text"]).strip().casefold()
                hashes.add(hashlib.sha256(normalized.encode()).hexdigest())
    generated_hashes: set[str] = set()
    for index in range(args.count):
        for attempt in range(100):
            if args.pattern_set == 3:
                parts = build_resume_pattern_set_three(rng, index)
            elif args.pattern_set == 2:
                parts = build_resume_pattern_set_two(rng, index)
            else:
                parts = build_resume(rng, index)
            text = "".join(part for part, _ in parts)
            digest = hashlib.sha256(re.sub(r"\s+", " ", text).strip().casefold().encode()).hexdigest()
            if digest not in hashes and digest not in generated_hashes:
                generated_hashes.add(digest)
                break
        else:
            raise RuntimeError(f"Could not generate a unique resume for item {index}")
        tokens, tags = tokenize_labeled(parts, tokenizer)
        document_id = f"synthetic_{args.offset + index + 1:04d}"
        records.extend(split_chunks(document_id, tokens, tags, args.chunk_size))
        resume_text = "".join(text for text, _ in parts)
        char_offset = 0
        entities = []
        for text_part, entity_type in parts:
            if entity_type != "O":
                entities.append({"label": entity_type, "start": char_offset,
                                 "end": char_offset + len(text_part), "text": text_part})
            char_offset += len(text_part)
        source_records.append({"document_id": document_id, "text": resume_text, "entities": entities})

    args.output_dir.mkdir(parents=True, exist_ok=True)
    data_path = args.output_dir / "train.jsonl"
    with data_path.open("w", encoding="utf-8", newline="\n") as output:
        for row in records:
            output.write(json.dumps(row, ensure_ascii=False) + "\n")
    source_path = args.output_dir / "source_resumes.jsonl"
    with source_path.open("w", encoding="utf-8", newline="\n") as output:
        for row in source_records:
            output.write(json.dumps(row, ensure_ascii=False) + "\n")
    manifest = {
        "dataset_type": "synthetic_training_only",
        "pattern_set": args.pattern_set,
        "pattern_families": 18 if args.pattern_set == 3 else (12 if args.pattern_set == 2 else 8),
        "id_offset": args.offset,
        "synthetic_documents": args.count,
        "chunks": len(records),
        "seed": args.seed,
        "tokenizer": args.tokenizer,
        "chunk_size": args.chunk_size,
        "unique_documents": len(generated_hashes),
        "labels": LABELS,
        "warning": "Fictional, programmatically generated examples. Use only for training/augmentation; do not treat synthetic evaluation as evidence of real-world performance.",
    }
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({**manifest, "output": str(data_path),
                      "reviewable_source_output": str(source_path)}, indent=2))


if __name__ == "__main__":
    main()
