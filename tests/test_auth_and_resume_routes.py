import asyncio
import json

import numpy as np
import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from app import api, storage


def make_json_request(payload):
    body = json.dumps(payload).encode("utf-8")
    delivered = False

    async def receive():
        nonlocal delivered
        if delivered:
            return {"type": "http.request", "body": b"", "more_body": False}
        delivered = True
        return {"type": "http.request", "body": body, "more_body": False}

    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "POST", "scheme": "http", "path": "/api/auth/register",
        "raw_path": b"/api/auth/register", "query_string": b"",
        "headers": [(b"host", b"testserver"), (b"content-type", b"application/json")],
        "client": ("testclient", 12345), "server": ("testserver", 80),
    }
    return Request(scope, receive)


def test_register_allows_multiple_accounts_and_login(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "DATABASE_PATH", tmp_path / "auth.sqlite3")
    storage.initialize_database()

    first_response = Response()
    first = asyncio.run(api.register(make_json_request({
        "email": "first@example.test", "name": "First Recruiter", "password": "long-password-1",
    }), first_response))
    second_response = Response()
    second = asyncio.run(api.register(make_json_request({
        "email": "second@example.test", "name": "Second Recruiter", "password": "long-password-2",
    }), second_response))

    assert first["user"]["id"] != second["user"]["id"]
    assert first_response.headers.get("set-cookie")
    assert second_response.headers.get("set-cookie")
    with pytest.raises(HTTPException) as duplicate:
        asyncio.run(api.register(make_json_request({
            "email": "FIRST@example.test", "name": "Duplicate", "password": "long-password-3",
        }), Response()))
    assert duplicate.value.status_code == 409

    login_response = Response()
    logged_in = asyncio.run(api.login(make_json_request({
        "email": "first@example.test", "password": "long-password-1",
    }), login_response))
    assert logged_in["user"]["id"] == first["user"]["id"]
    assert login_response.headers.get("set-cookie")


def test_original_resume_route_is_owner_scoped_and_returns_file(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "DATABASE_PATH", tmp_path / "resume.sqlite3")
    storage.initialize_database()
    owner_id = storage.create_user("owner@example.test", "Owner", "hash")
    other_id = storage.create_user("other@example.test", "Other", "hash")
    storage.save_resume(
        owner_id, "candidate.pdf", "application/pdf", b"%PDF-original",
        {"candidate_id": "candidate-abc"}, np.asarray([1.0], dtype="float32"),
    )

    response = api.get_original_resume("candidate-abc", {"id": owner_id})
    assert response.body == b"%PDF-original"
    assert response.media_type == "application/pdf"
    assert "inline" in response.headers["content-disposition"]
    with pytest.raises(HTTPException) as forbidden:
        api.get_original_resume("candidate-abc", {"id": other_id})
    assert forbidden.value.status_code == 404


def test_original_s3_resume_route_streams_object_bytes(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "DATABASE_PATH", tmp_path / "s3-resume.sqlite3")
    storage.initialize_database()
    owner_id = storage.create_user("s3@example.test", "S3 Recruiter", "hash")
    storage.save_resume(
        owner_id, "candidate.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        b"", {"candidate_id": "candidate-s3"}, np.asarray([1.0], dtype="float32"),
        storage_backend="s3", object_key="resumes/user-1/candidate-s3/candidate.docx", file_size=17,
    )

    class FakeStorage:
        def download(self, key):
            assert key == "resumes/user-1/candidate-s3/candidate.docx"
            return b"original-docx-bytes"

    monkeypatch.setattr(api, "get_resume_file_storage", lambda: FakeStorage())
    response = api.get_original_resume("candidate-s3", {"id": owner_id})
    assert response.body == b"original-docx-bytes"
    assert response.media_type.endswith("wordprocessingml.document")
