# AI-Based Resume Analyzer & Intelligent Candidate Ranking System

This repository contains a locally runnable college mini-project prototype: resume upload, PDF/DOCX extraction, preprocessing, rule-based information extraction, SBERT embeddings, FAISS cosine retrieval, explainable matching, weighted ranking, and a responsive web dashboard served by FastAPI.

## Problem statement

Recruiters often spend significant time manually comparing resumes against a job description. This prototype demonstrates how semantic search plus transparent matching signals can help surface relevant candidates for review.

## Objectives

- Accept multiple PDF and DOCX resumes.
- Extract and clean resume text without losing technical terms.
- Build structured candidate profiles using configurable rules and a skill dictionary.
- Embed candidate profiles and job descriptions with `all-MiniLM-L6-v2`.
- Retrieve semantically relevant candidates with FAISS.
- Explain a basic match score with matched and missing skills.

## Architecture

```text
Browser (HTML/CSS/vanilla JS)
        │ fetch + multipart forms / JSON
        ▼
FastAPI transport layer (app/api.py)
  /api/process    /api/demo    /api/analyze    /api/status
        │
        ├── PDF/DOCX parser ──► text normalization ──► candidate profile extraction
        │                                                   │
        │                                                   ▼
        │                              SentenceTransformer (MiniLM-L6-v2)
        │                                                   │ normalized vectors
        │                                                   ▼
        │                                      FAISS IndexFlatIP
        │                                                   │ top-K cosine retrieval
        └──────────────────────────────► skill / experience / education matching
                                                            │
                                                            ▼
                                                   weighted ranking
                                                            │
                                                            ▼
                                             ranked candidates + explanations
```

### Request and data flow

1. The browser accepts multiple PDF/DOCX files and posts them to `/api/process`. The demo button instead asks `/api/demo` to read the synthetic files shipped in `sample_data/resumes`.
2. `document_parser.py` extracts selectable PDF text using PyMuPDF or paragraphs and tables from DOCX using python-docx. Empty or unsupported files are reported individually.
3. `preprocessing.py` normalizes whitespace and punctuation and splits common resume sections. `information_extractor.py` uses a configurable skill dictionary plus lightweight heuristics to create `CandidateProfile` records. Profiles are persisted as JSON under `data/processed/`.
4. `embedding_service.py` lazily loads `sentence-transformers/all-MiniLM-L6-v2` once per process and embeds candidate text. Vectors are stored with each profile in SQLite. Analysis rebuilds a user-scoped FAISS inner-product index from those saved vectors; with normalized vectors, inner product is cosine similarity.
5. The browser submits a job title, description, and K to `/api/analyze`. The description is preprocessed and embedded; FAISS retrieves the K most semantically similar candidates.
6. `matching_service.py` derives skill overlap, experience, and education signals. `ranking_service.py` combines those with semantic similarity using 50% semantic, 30% skills, 10% experience, and 10% education weights. Results return candidate profile details, score components, matched skills, missing skills, and cleaned resume text.
7. `app/static/` contains the single-page browser interface: HTML structure, responsive CSS, and JavaScript for uploads, API calls, status, and candidate details. It has no frontend build step or separate Node runtime.

### Components

| Path | Responsibility |
| --- | --- |
| `app/api.py` | FastAPI routes, request validation, in-memory session state, pipeline orchestration |
| `app/static/index.html` | Dashboard layout and workflow |
| `app/static/styles.css` | Responsive visual system and component styling |
| `app/static/app.js` | File selection, API integration, ranking and detail rendering |
| `app/config.py` | Paths for data, FAISS artifacts, and model name |
| `app/services/document_parser.py` | PDF and DOCX extraction |
| `app/services/preprocessing.py` | Text cleanup and common section detection |
| `app/services/information_extractor.py` | Candidate profile model and heuristic extraction |
| `app/services/embedding_service.py` | Cached MiniLM model access and vector creation |
| `app/services/faiss_service.py` | FAISS build, persistence, and top-K search |
| `app/services/matching_service.py` | Skill, experience, and education match explanations |
| `app/services/ranking_service.py` | Weighted score and descending candidate order |
| `app/utils/` | Whitespace/skill normalization and JSON persistence helpers |
| `sample_data/` | Synthetic PDF/DOCX resumes and example job descriptions |
| `tests/` | Unit tests for parsing, extraction, embeddings, retrieval, and matching |
| `tools/generate_demo_data.py` | Demo fixture generation |

### Accounts, database, and upload capacity

- The first visit shows a one-time account setup form. The first account becomes the owner; later sign-ins use that account. Passwords are stored as salted PBKDF2-SHA256 hashes and the browser receives an HttpOnly, SameSite=Strict, signed session cookie.
- SQLite stores each account, original uploaded PDF/DOCX bytes, extracted profile, and embedding in `data/talentlens.sqlite3`. Resume records are scoped to their owner and persist across server restarts. Model files stay under the ignored `model_cache/` directory.
- The UI queues any selected number of resumes and submits them in batches of at most 25. The server accepts up to 25 files per request, 10 MB per file, and 100 MB combined per batch. A 100-resume set is four batches; processed resumes stay in the pool as further batches are added.
- For a classroom demo or one recruiter on one computer, SQLite is a good fit for hundreds or thousands of small records. Processing capacity depends mainly on CPU/RAM, file size, extraction quality, and embedding speed—not a fixed global resume count. Start with 25 per batch; if 100 is slow, use batches of 10–25 and wait for each to complete. For sustained larger workloads, move to PostgreSQL for account/profile metadata, private object storage for resume files, and a background job queue with progress updates.
- This prototype is for local use. SQLite and this app do not encrypt resume files at rest or provide production-grade account administration, password reset, TLS, or automated retention/deletion. Before exposing it to a network or using real candidate data, add those controls and use private managed storage. Do not commit the database or session secret.

## Folder structure

```text
app/
  api.py
  static/  # browser dashboard (HTML, CSS, JavaScript)
  config.py
  services/  # parser, preprocessing, extraction, embeddings, FAISS, matching, ranking
  utils/
data/processed/  # generated candidate JSON profiles
sample_data/     # 10 synthetic resumes and 3 job descriptions
tests/
tools/generate_demo_data.py
vector_store/    # generated FAISS index and candidate mapping
requirements.txt
```

## Installation

Python 3.10+ is recommended.

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# macOS/Linux
source .venv/bin/activate
pip install -r requirements.txt
```

The first SBERT analysis downloads `sentence-transformers/all-MiniLM-L6-v2` from Hugging Face and caches it locally. An internet connection is only needed for that first model download; the application itself is local.

## Run the dashboard

From the project root:

```bash
python -m uvicorn app.api:app --reload
```

On Windows PowerShell, from the `resume_analyzer` directory, start the server with `\.venv\Scripts\python.exe -m uvicorn app.api:app --host 127.0.0.1 --port 8000`. Keep that terminal open and visit http://127.0.0.1:8000. Create the first workspace account, then upload PDF/DOCX files or choose **Load demo candidates**. Upload batches of up to 25 are added to your saved pool. Add a job description and choose **Find top candidates**. The dashboard shows ranked matches and an explainable score breakdown. The first use downloads the embedding model and can take several minutes.

## Demo workflow

The included synthetic dataset covers machine learning, data science, web, Python backend, analytics, cloud, AI, backend, software, and NLP profiles. For a compelling demonstration:

1. Load the included sample resumes.
2. Use `sample_data/job_descriptions/machine_learning_engineer.txt` as the job description.
3. Analyze candidates with K=5.
4. Expand a candidate to see semantic similarity, matched/missing skills, experience, education, projects, and cleaned resume text.

## Scoring

```text
Job Match Score =
  0.5 * semantic similarity
  + 0.3 * skill match
  + 0.1 * experience match
  + 0.1 * education match
```

Every component is bounded between 0 and 1. The result is a transparent prototype ranking signal, not a scientifically validated hiring probability.

## Tests

```bash
pytest -q
```

The tests cover PDF/DOCX extraction, preprocessing, skill extraction, candidate profiles, embedding dimensions and normalization, FAISS persistence/search, skill matching, scoring, and ranking. The embedding test downloads/loads the real SBERT model and can take longer on the first run.

## Current 50% implementation

The full local core pipeline is implemented and wired to the UI. It is deliberately modular so cloud storage, APIs, databases, and improved models can replace individual services later.

## Phase 2 / future work

1. Fine-tuned BERT-NER and a larger annotated resume dataset.
2. PostgreSQL, FastAPI, authentication, and richer job requirement extraction.
3. Calibrated scoring and evaluation with Precision/Recall/F1, Precision@K, Recall@K, and human-ranking comparison.
4. AWS S3, EC2, RDS, Docker, and production monitoring.
5. OCR for scanned resumes, recruiter filters, improved UI, and candidate-facing feedback.

## Known limitations

The information extractor is intentionally a configurable rule/NLP hybrid; it does not claim generic NER understands every resume format. Experience and education matching are simple heuristics, PDF extraction depends on selectable text, and the score has not been validated against hiring outcomes. These are appropriate boundaries for the 50% demonstrator.
