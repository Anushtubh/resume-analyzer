import re
import logging
from dataclasses import asdict, dataclass, field
from typing import Any

from app.services.preprocessing import detect_sections, preprocess_text
from app.utils.text_utils import canonicalize_skill
from app.services.ner_service import ResumeNerService

LOGGER = logging.getLogger(__name__)


# Configurable technology vocabulary. The groups are kept separate for easier
# maintenance, then flattened into the existing `skills` contract so matching
# and the current frontend/API continue to work unchanged.
TECHNOLOGY_DICTIONARY = {
    "languages": [
        "Python", "Java", "C", "C++", "C#", "Go", "Rust", "JavaScript", "TypeScript",
        "PHP", "Ruby", "Kotlin", "Swift", "Scala", "R", "MATLAB", "Bash", "PowerShell",
        "SQL", "HTML", "CSS",
    ],
    "ai_ml": [
        "Artificial Intelligence", "Machine Learning", "Deep Learning", "Generative AI",
        "Large Language Models", "NLP",
        "Computer Vision", "Reinforcement Learning", "Statistical Learning", "MLOps",
        "Prompt Engineering", "Retrieval-Augmented Generation", "Transformers",
        "Hugging Face", "LangChain", "LlamaIndex", "TensorFlow", "PyTorch", "PyTorch Lightning", "Keras",
        "JAX", "Scikit-learn", "XGBoost", "LightGBM", "CatBoost", "spaCy", "NLTK",
        "OpenCV", "ONNX", "Sentence Transformers", "FAISS", "ChromaDB", "Pinecone",
        "Weaviate", "MLflow", "Kubeflow", "Weights & Biases", "DVC",
    ],
    "web_and_backend": [
        "React", "Angular", "Vue.js", "Svelte", "Next.js", "Nuxt.js", "Node.js",
        "Express.js", "NestJS", "Redux", "Tailwind CSS", "Bootstrap", "jQuery",
        "Spring", "Spring Boot", "ASP.NET", ".NET", "Django", "Flask", "FastAPI",
        "Ruby on Rails", "Laravel", "Symfony", "Gin", "Actix", "REST API", "GraphQL",
        "gRPC", "WebSocket", "Microservices", "OAuth", "OpenAPI", "Swagger",
    ],
    "data_and_analytics": [
        "Pandas", "NumPy", "SciPy", "Polars", "Spark", "PySpark", "Hadoop",
        "Hive", "Kafka", "Apache Airflow", "dbt", "Databricks", "Snowflake",
        "BigQuery", "Amazon Redshift", "Amazon Athena", "Athena", "ETL",
        "ELT", "Data Warehousing", "Data Engineering", "Power BI", "Tableau", "Looker",
        "Qlik Sense", "Excel", "Jupyter Notebook",
    ],
    "databases_and_search": [
        "PostgreSQL", "MySQL", "Microsoft SQL Server", "SQLite", "Oracle",
        "MongoDB", "Redis", "Cassandra", "DynamoDB", "Elasticsearch", "OpenSearch",
        "Neo4j", "MariaDB", "Firebase", "Supabase", "Cosmos DB", "Amazon RDS",
    ],
    "cloud_and_devops": [
        "AWS", "Azure", "Google Cloud Platform", "Docker", "Kubernetes", "Terraform",
        "Ansible", "Helm", "Jenkins", "GitHub Actions", "GitLab CI", "CircleCI",
        "Argo CD", "Prometheus", "Grafana", "Linux", "Nginx", "Apache HTTP Server",
        "CI/CD", "DevOps", "Site Reliability Engineering", "Serverless",
    ],
    "version_control_and_tools": [
        "Git", "GitHub", "GitLab", "Bitbucket", "Jira", "Confluence", "Postman",
        "Insomnia", "VS Code", "IntelliJ IDEA", "PyCharm",
        "Eclipse", "Vim", "Figma", "Selenium", "Playwright", "Cypress", "Jest",
        "Pytest", "JUnit", "TestNG", "SonarQube",
    ],
}

SKILL_DICTIONARY = list(dict.fromkeys(
    entry.strip() for group in TECHNOLOGY_DICTIONARY.values() for entry in group
))

# Common resume spellings that should resolve to the same canonical skill name.
SKILL_ALIASES = {
    "PostgreSQL": ["Postgres"],
    "Kubernetes": ["K8s"],
    "AWS": ["Amazon Web Services"],
    "Azure": ["Microsoft Azure"],
    "NLP": ["Natural Language Processing"],
    "NLP": ["Natural Language Processing"],
    "Power BI": ["PowerBI"],
    "VS Code": ["Visual Studio Code", "Visual Studio Code (VS Code)"],
    "JavaScript": ["ECMAScript"],
    "TypeScript": ["TS language"],
    "Node.js": ["Node JS", "NodeJS"],
    "Scikit-learn": ["scikit learn", "sklearn"],
    "PySpark": ["pyspark"],
    "Spark": ["Apache Spark"],
    "Google Cloud Platform": ["GCP", "Google Cloud"],
    "Large Language Models": ["LLM", "LLMs"],
    "Retrieval-Augmented Generation": ["RAG"],
    "Generative AI": ["GenAI"],
    "Artificial Intelligence": ["AI"],
    "Site Reliability Engineering": ["SRE"],
    "Weights & Biases": ["Weights and Biases", "W&B"],
    "Apache Airflow": ["Airflow"],
    "Microsoft SQL Server": ["SQL Server"],
}

ROLE_PATTERNS = {
    "Machine Learning Engineer": ["machine learning engineer", "ml engineer"],
    "AI Engineer": ["artificial intelligence engineer", "ai engineer"],
    "Deep Learning Engineer": ["deep learning engineer"],
    "NLP Engineer": ["nlp engineer", "natural language processing engineer"],
    "Computer Vision Engineer": ["computer vision engineer", "vision engineer"],
    "MLOps Engineer": ["mlops engineer", "machine learning operations engineer"],
    "Data Scientist": ["data scientist", "applied scientist"],
    "Data Engineer": ["data engineer", "big data engineer"],
    "Analytics Engineer": ["analytics engineer"],
    "Data Analyst": ["data analyst", "business data analyst"],
    "Business Intelligence Analyst": ["business intelligence analyst", "bi analyst"],
    "Business Intelligence Developer": ["business intelligence developer", "bi developer"],
    "Software Engineer": ["software engineer", "software developer"],
    "Frontend Engineer": ["frontend engineer", "front-end engineer", "frontend developer", "front-end developer"],
    "Backend Engineer": ["backend engineer", "back-end engineer", "backend developer", "back-end developer"],
    "Full Stack Engineer": ["full stack engineer", "full-stack engineer", "full stack developer", "full-stack developer"],
    "Web Developer": ["web developer", "web engineer"],
    "Mobile Developer": ["mobile developer", "mobile engineer", "android developer", "ios developer"],
    "Cloud Engineer": ["cloud engineer", "cloud developer"],
    "Cloud Architect": ["cloud architect", "solutions architect"],
    "DevOps Engineer": ["devops engineer", "devops specialist"],
    "Site Reliability Engineer": ["site reliability engineer", "sre"],
    "Platform Engineer": ["platform engineer"],
    "Security Engineer": ["security engineer", "cybersecurity engineer", "information security engineer"],
    "QA Engineer": ["qa engineer", "quality assurance engineer", "test automation engineer"],
    "Database Administrator": ["database administrator", "dba"],
    "Database Engineer": ["database engineer"],
    "Systems Engineer": ["systems engineer", "system administrator", "systems administrator"],
    "Network Engineer": ["network engineer", "network administrator"],
    "Product Manager": ["technical product manager", "product manager"],
    "Research Scientist": ["research scientist", "research engineer"],
    "Engineering Manager": ["engineering manager", "software development manager"],
    "Technical Support Engineer": ["technical support engineer", "support engineer"],
    "Solutions Engineer": ["solutions engineer", "sales engineer"],
}

EXPERIENCE_PATTERN = re.compile(
    r"(?<![\w.])(?:\d+(?:\.\d+)?\s*\+?\s*(?:years?|yrs?)"
    r"(?:\s*(?:and\s*)?\d+\s*(?:months?|mos?))?|"
    r"\d+\s*(?:months?|mos?))(?!\w)", re.IGNORECASE
)


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
    extraction_method: str = "rules"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def embedding_text(self) -> str:
        fields = [self.clean_text, "Skills: " + ", ".join(self.skills),
                  "Experience: " + ", ".join(self.experience),
                  "Projects: " + ", ".join(self.projects),
                  "Education: " + ", ".join(self.education)]
        return "\n".join(part for part in fields if part.strip())


def extract_skills(text: str, skill_dictionary: list[str] | None = None) -> list[str]:
    dictionary = SKILL_DICTIONARY if skill_dictionary is None else skill_dictionary
    found: dict[str, str] = {}
    alias_lookup = {canonicalize_skill(name): aliases for name, aliases in SKILL_ALIASES.items()}
    for skill in sorted(dictionary, key=len, reverse=True):
        variants = [skill, *alias_lookup.get(canonicalize_skill(skill), [])]
        for variant in variants:
            # Treat periods, #, and + as meaningful characters (C++, C#, Node.js)
            # while preventing partial-word matches such as Java inside JavaScript.
            pattern = rf"(?<![\w+#.]){re.escape(variant)}(?![\w+#.])"
            flags = 0 if canonicalize_skill(skill) in {"c", "r"} else re.IGNORECASE
            if re.search(pattern, text or "", flags=flags):
                found.setdefault(canonicalize_skill(skill), skill)
                break
    return sorted(found.values(), key=canonicalize_skill)


def extract_experience(text: str) -> list[str]:
    """Extract numeric years/months-tenure phrases without guessing dates."""
    return list(dict.fromkeys(match.group(0).strip() for match in EXPERIENCE_PATTERN.finditer(text or "")))


def _extract_job_roles(lines: list[str]) -> list[str]:
    found = []
    for line in lines:
        for role, aliases in ROLE_PATTERNS.items():
            for alias in aliases:
                if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", line, re.IGNORECASE):
                    found.append(role)
                    break
    return list(dict.fromkeys(found))


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
    summary = _section_values(sections, "summary", "profile")
    roles = _extract_job_roles((summary + experience)[:20])
    years = extract_experience(clean)
    companies = []
    for line in experience:
        match = re.search(r"(?:at|@|with)\s+([A-Z][\w& .-]{2,})", line)
        if match:
            companies.append(match.group(1).strip(" .,-"))
    try:
        ner = ResumeNerService().extract_entities(clean)
        extraction_error = False
    except Exception:
        LOGGER.exception("Fine-tuned NER inference failed; falling back to rule extraction")
        ner = None
        extraction_error = True
    if ner is None:
        ner = {"skills": [], "education": [], "companies": [], "job_roles": [], "experience": [], "projects": [], "certifications": []}
        extraction_method = "rules_fallback_model_error" if extraction_error else "rules"
    else:
        extraction_method = "fine_tuned_bert_ner+rules"
    skills = extract_skills(clean)
    known_skills = {canonicalize_skill(skill): skill for skill in SKILL_DICTIONARY}
    seen_skills = {canonicalize_skill(skill) for skill in skills}
    for skill in ner["skills"]:
        canonical = canonicalize_skill(skill)
        if canonical not in seen_skills:
            skills.append(known_skills.get(canonical, skill))
            seen_skills.add(canonical)
    return CandidateProfile(
        candidate_id=candidate_id,
        filename=filename,
        raw_text=text,
        clean_text=clean,
        skills=sorted(skills, key=canonicalize_skill),
        education=list(dict.fromkeys(education + ner["education"])),
        companies=sorted(set(companies + ner["companies"])),
        job_roles=list(dict.fromkeys(roles + ner["job_roles"])),
        experience=sorted(set(years + ner["experience"])),
        projects=list(dict.fromkeys(projects + ner["projects"])),
        certifications=list(dict.fromkeys(certifications + ner["certifications"])),
        extraction_method=extraction_method,
    )
