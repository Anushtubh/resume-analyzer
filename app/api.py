"""Authenticated local resume analyzer API backed by SQLite."""
import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import sys
import time
import uuid
from pathlib import Path
from threading import Lock
from urllib.parse import quote

import numpy as np
from fastapi import Cookie, Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

PROJECT_ROOT = Path(__file__).resolve().parents[1]
try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env", override=False)
except ImportError:
    pass
os.environ.setdefault("HF_HOME", str(PROJECT_ROOT / "model_cache"))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import DATA_DIR, VECTOR_STORE_DIR
from app.services.document_parser import extract_text
from app.services.embedding_service import EmbeddingService
from app.services.file_storage import get_resume_file_storage
from app.services.faiss_service import FaissResumeIndex
from app.services.information_extractor import CandidateProfile, extract_candidate_info
from app.services.preprocessing import preprocess_text
from app.services.ranking_service import rank_candidates
from app import storage

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)
MAX_BATCH_FILES = 25
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_BATCH_BYTES = 100 * 1024 * 1024
SESSION_SECONDS = 60 * 60 * 12
SESSION_COOKIE = "talentlens_session"
SESSION_SECRET_PATH = DATA_DIR / ".session_secret"
if not SESSION_SECRET_PATH.exists():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        SESSION_SECRET_PATH.write_text(secrets.token_urlsafe(48), encoding="utf-8")
    except FileExistsError:
        pass
SESSION_SECRET = SESSION_SECRET_PATH.read_text(encoding="utf-8").strip().encode("utf-8")
app = FastAPI(title="Resume Analyzer API", version="2.0.0")
app.mount("/static", StaticFiles(directory=PROJECT_ROOT / "app" / "static"), name="static")
pipeline_lock = Lock()
_FAISS_INDICES: dict[int, FaissResumeIndex] = {}


@app.on_event("startup")
def startup():
    storage.initialize_database()
    for user_id in storage.list_user_ids():
        candidates, vectors = _resume_candidates(user_id)
        if candidates:
            try:
                with pipeline_lock:
                    _get_user_index(user_id, candidates, vectors)
            except Exception:
                LOGGER.exception("Could not load or recover FAISS index for user %s", user_id)


@app.get("/")
def home():
    return FileResponse(PROJECT_ROOT / "app" / "static" / "index.html")


def _password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600_000)
    return f"pbkdf2_sha256$600000${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def _password_matches(password: str, encoded: str) -> bool:
    try:
        scheme, iterations, salt, expected = encoded.split("$")
        actual = _password_hash(password, base64.urlsafe_b64decode(salt.encode())).split("$")[-1]
        return scheme == "pbkdf2_sha256" and int(iterations) == 600_000 and hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _make_session(user_id: int) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"uid": user_id, "exp": int(time.time()) + SESSION_SECONDS}, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(SESSION_SECRET, payload.encode(), hashlib.sha256).digest()
    return payload + "." + base64.urlsafe_b64encode(signature).decode().rstrip("=")


def _session_user(token: str | None):
    if not token:
        return None
    try:
        payload, signature = token.split(".", 1)
        expected = hmac.new(SESSION_SECRET, payload.encode(), hashlib.sha256).digest()
        supplied = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
        if not hmac.compare_digest(expected, supplied):
            return None
        body = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if body["exp"] < time.time():
            return None
        return storage.get_user_by_id(int(body["uid"]))
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def require_user(token: str | None = Cookie(default=None, alias=SESSION_COOKIE)):
    user = _session_user(token)
    if not user:
        raise HTTPException(401, "Please sign in to continue.")
    return user


@app.get("/api/auth/setup-status")
def setup_status():
    return {"setup_required": storage.user_count() == 0}


@app.post("/api/auth/register")
async def register(request: Request, response: Response):
    payload = await request.json()
    email = str(payload.get("email", "")).strip().lower()
    name = str(payload.get("name", "")).strip()
    password = str(payload.get("password", ""))
    if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or not name or len(name) > 100:
        raise HTTPException(422, "Enter a valid email address and a display name.")
    if len(password) < 12 or len(password) > 256:
        raise HTTPException(422, "Use a password between 12 and 256 characters.")
    try:
        user_id = storage.create_user(email, name, _password_hash(password))
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:
        LOGGER.exception("Account creation failed")
        raise HTTPException(409, "Could not create the account. Please try again.") from exc
    response.set_cookie(SESSION_COOKIE, _make_session(user_id), httponly=True, samesite="strict", secure=request.url.scheme == "https", max_age=SESSION_SECONDS, path="/")
    return {"user": storage.get_user_by_id(user_id)}


@app.post("/api/auth/login")
async def login(request: Request, response: Response):
    payload = await request.json()
    user = storage.get_user(str(payload.get("email", "")))
    if not user or not _password_matches(str(payload.get("password", "")), user["password_hash"]):
        raise HTTPException(401, "Email or password is incorrect.")
    response.set_cookie(SESSION_COOKIE, _make_session(user["id"]), httponly=True, samesite="strict", secure=request.url.scheme == "https", max_age=SESSION_SECONDS, path="/")
    return {"user": storage.get_user_by_id(user["id"])}


@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="strict")
    return {"ok": True}


@app.get("/api/auth/me")
def me(user=Depends(require_user)):
    return {"user": user}


def _resume_candidates(user_id: int):
    candidates, vectors = [], []
    for row in storage.list_resumes(user_id):
        candidates.append(CandidateProfile(**json.loads(row["profile_json"])))
        vectors.append(np.frombuffer(row["embedding"], dtype="float32").copy())
    return candidates, vectors


def _user_index_paths(user_id: int):
    folder = VECTOR_STORE_DIR / "users" / str(user_id)
    return folder / "resume.index", folder / "mapping.json"


def _persist_user_index(user_id: int, candidates, vectors):
    index = FaissResumeIndex()
    if candidates:
        index.build_index(np.asarray(vectors, dtype="float32"), [candidate.candidate_id for candidate in candidates])
        index_path, mapping_path = _user_index_paths(user_id)
        index.save_index(index_path, mapping_path)
    _FAISS_INDICES[user_id] = index
    return index


def _append_user_index(user_id: int, all_candidates, all_vectors, additions, addition_vectors):
    expected_ids = [candidate.candidate_id for candidate in all_candidates]
    existing_ids = expected_ids[:len(expected_ids) - len(additions)]
    index_path, mapping_path = _user_index_paths(user_id)
    index = _FAISS_INDICES.get(user_id)
    if index is None or list(index.mapping.values()) != existing_ids:
        index = FaissResumeIndex()
        try:
            index.load_index(index_path, mapping_path)
        except (OSError, ValueError, RuntimeError):
            index = None
        if index is not None and list(index.mapping.values()) != existing_ids:
            index = None
    if index is None:
        return _persist_user_index(user_id, all_candidates, all_vectors)
    try:
        for candidate, vector in zip(additions, addition_vectors):
            index.add_embedding(vector, candidate.candidate_id)
        index.save_index(index_path, mapping_path)
    except Exception:
        LOGGER.exception("Incremental FAISS update failed; rebuilding from durable SQLite embeddings")
        return _persist_user_index(user_id, all_candidates, all_vectors)
    _FAISS_INDICES[user_id] = index
    return index


def _get_user_index(user_id: int, candidates, vectors):
    expected_ids = [candidate.candidate_id for candidate in candidates]
    index_path, mapping_path = _user_index_paths(user_id)
    cached = _FAISS_INDICES.get(user_id)
    if cached is not None and list(cached.mapping.values()) == expected_ids:
        return cached
    if index_path.is_file() and mapping_path.is_file():
        try:
            index = FaissResumeIndex()
            index.load_index(index_path, mapping_path)
            if list(index.mapping.values()) == expected_ids:
                _FAISS_INDICES[user_id] = index
                return index
        except (OSError, ValueError, RuntimeError):
            LOGGER.warning("Stored FAISS index for user %s is missing or inconsistent; rebuilding from SQLite", user_id)
    return _persist_user_index(user_id, candidates, vectors)


def _status_for(user_id: int, failures=None):
    candidates, _ = _resume_candidates(user_id)
    files = [{"id": c.candidate_id, "name": c.filename, "preview": c.clean_text[:700]} for c in candidates]
    return {"processed": len(candidates), "failed": len(failures or []), "files": files,
            "failures": failures or [], "ready": bool(candidates)}


@app.get("/api/status")
def status(user=Depends(require_user)):
    return _status_for(user["id"])


def _check_suffix(filename: str):
    if Path(filename).suffix.lower() not in {".pdf", ".docx"}:
        raise ValueError("Only PDF and DOCX files are supported")


def _process_uploads(user_id: int, incoming):
    if not incoming:
        raise HTTPException(400, "Choose at least one PDF or DOCX resume.")
    if len(incoming) > MAX_BATCH_FILES:
        raise HTTPException(413, f"Process up to {MAX_BATCH_FILES} resumes per batch, then upload the next batch. Your existing pool will be kept.")
    good, failures, total_bytes = [], [], 0
    for filename, content, content_type in incoming:
        try:
            _check_suffix(filename)
            if len(content) > MAX_FILE_BYTES:
                raise ValueError("File exceeds the 10 MB per-resume limit")
            total_bytes += len(content)
            if total_bytes > MAX_BATCH_BYTES:
                raise ValueError("Batch exceeds the 100 MB total upload limit")
            extractor_file = type("ResumeFile", (), {"name": filename, "read": lambda self: content})()
            raw_text = extract_text(extractor_file)
            if not raw_text.strip():
                raise ValueError("No readable text found; scanned PDFs need OCR before upload")
            candidate = extract_candidate_info(raw_text, uuid.uuid4().hex, Path(filename).name)
            if candidate.extraction_method.startswith("rules"):
                LOGGER.info("Rule-based extraction is active (%s) for %s", candidate.extraction_method, filename)
            good.append((candidate, content, content_type))
        except Exception as exc:
            failures.append({"name": filename, "error": str(exc) or exc.__class__.__name__})
    if good:
        try:
            with pipeline_lock:
                embedder = EmbeddingService()
                embeddings = embedder.generate_embeddings([candidate.embedding_text() for candidate, _, _ in good])
                file_storage = get_resume_file_storage()
                for (candidate, content, content_type), vector in zip(good, embeddings):
                    object_key = None
                    stored_bytes = content
                    backend = "sqlite"
                    if file_storage is not None:
                        object_key = file_storage.upload(user_id, candidate.candidate_id,
                                                         candidate.filename, content, content_type)
                        stored_bytes = b""  # Avoid duplicating original files in SQLite.
                        backend = "s3"
                    try:
                        storage.save_resume(user_id, candidate.filename, content_type, stored_bytes,
                                            candidate.to_dict(), vector, storage_backend=backend,
                                            object_key=object_key, file_size=len(content))
                    except Exception:
                        if file_storage is not None and object_key:
                            try:
                                file_storage.delete(object_key)
                            except Exception:
                                LOGGER.exception("Could not remove unreferenced S3 resume %s", object_key)
                        raise
                all_candidates, all_vectors = _resume_candidates(user_id)
                _append_user_index(user_id, all_candidates, all_vectors,
                                   [candidate for candidate, _, _ in good], list(embeddings))
        except Exception as exc:
            LOGGER.exception("Resume embedding/index creation failed")
            raise HTTPException(500, f"Resumes could not be stored or embedded: {exc}") from exc
    return _status_for(user_id, failures)


@app.post("/api/process")
async def process_resumes(files: list[UploadFile] = File(...), user=Depends(require_user)):
    if len(files) > MAX_BATCH_FILES:
        raise HTTPException(413, f"Process up to {MAX_BATCH_FILES} resumes per batch, then upload the next batch. Your existing pool will be kept.")
    incoming = []
    total_bytes = 0
    for upload in files:
        content = await upload.read(MAX_FILE_BYTES + 1)
        total_bytes += len(content)
        if total_bytes > MAX_BATCH_BYTES:
            raise HTTPException(413, "Batch exceeds the 100 MB total upload limit. Process a smaller batch.")
        incoming.append((upload.filename or "resume", content, upload.content_type or "application/octet-stream"))
    return _process_uploads(user["id"], incoming)


@app.post("/api/demo")
def load_demo(user=Depends(require_user)):
    paths = sorted((PROJECT_ROOT / "sample_data" / "resumes").glob("*.pdf")) + sorted((PROJECT_ROOT / "sample_data" / "resumes").glob("*.docx"))
    if not paths:
        raise HTTPException(404, "No sample resumes are included.")
    existing = {row["filename"] for row in storage.list_resume_files(user["id"])}
    incoming = [(path.name, path.read_bytes(), "application/pdf" if path.suffix.lower() == ".pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document") for path in paths if path.name not in existing]
    return _process_uploads(user["id"], incoming) if incoming else _status_for(user["id"])


@app.get("/api/resumes")
def resume_inventory(user=Depends(require_user)):
    return [{"id": row["id"], "filename": row["filename"], "content_type": row["content_type"],
             "created_at": row["created_at"], "size_bytes": row["file_size"],
             "storage_backend": row["storage_backend"]}
            for row in storage.list_resume_files(user["id"])]


@app.get("/api/resumes/by-candidate/{candidate_id}/file")
def get_original_resume(candidate_id: str, user=Depends(require_user)):
    record = storage.get_resume_file_for_candidate(user["id"], candidate_id)
    if record is None:
        raise HTTPException(404, "The original resume was not found in your account.")
    if record["storage_backend"] == "s3":
        file_storage = get_resume_file_storage()
        if file_storage is None or not record["object_key"]:
            raise HTTPException(503, "The configured resume object store is unavailable.")
        try:
            content = file_storage.download(record["object_key"])
        except Exception as exc:
            LOGGER.exception("Could not retrieve original resume from S3")
            raise HTTPException(502, "Could not retrieve the original resume from S3.") from exc
    else:
        content = record["file_bytes"]
    if not content:
        raise HTTPException(404, "The original resume file is empty or unavailable.")
    filename = Path(record["filename"]).name
    return Response(
        content=content,
        media_type=record["content_type"] or "application/octet-stream",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(filename)}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@app.post("/api/analyze")
def analyze(title: str = Form("Untitled role"), job_description: str = Form(...), top_k: int = Form(5, gt=0), user=Depends(require_user)):
    candidates, vectors = _resume_candidates(user["id"])
    if not candidates:
        raise HTTPException(400, "Upload resumes before analyzing candidates.")
    if not job_description.strip():
        raise HTTPException(400, "Enter a job description.")
    try:
        with pipeline_lock:
            embedder = EmbeddingService()
            query = embedder.generate_embedding(preprocess_text(job_description))
            index = _get_user_index(user["id"], candidates, vectors)
            retrievals = index.search(query, min(max(1, top_k), len(candidates)))
        ranked = rank_candidates(candidates, retrievals, job_description)
        return {"title": title, "results": [item.to_dict() for item in ranked]}
    except Exception as exc:
        LOGGER.exception("Candidate analysis failed")
        raise HTTPException(500, f"Candidate analysis failed: {exc}") from exc
