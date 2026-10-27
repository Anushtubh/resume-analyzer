import numpy as np

from app import storage
from app.services.file_storage import S3ResumeStorage, get_resume_file_storage


class FakeS3Client:
    def __init__(self):
        self.puts = []
        self.deletes = []

    def put_object(self, **kwargs):
        self.puts.append(kwargs)

    def delete_object(self, **kwargs):
        self.deletes.append(kwargs)


def test_s3_upload_uses_scoped_key_and_server_side_encryption():
    client = FakeS3Client()
    s3 = S3ResumeStorage("demo-bucket", region="ap-south-1", client=client)
    key = s3.upload(7, "candidate-123", "../../resume.pdf", b"pdf bytes", "application/pdf")
    assert key == "resumes/user-7/candidate-123/resume.pdf"
    assert client.puts[0]["Bucket"] == "demo-bucket"
    assert client.puts[0]["Body"] == b"pdf bytes"
    assert client.puts[0]["ContentType"] == "application/pdf"
    assert client.puts[0]["ServerSideEncryption"] == "AES256"


def test_s3_storage_requires_bucket():
    try:
        S3ResumeStorage("  ", client=FakeS3Client())
    except ValueError as exc:
        assert "S3_BUCKET" in str(exc)
    else:
        raise AssertionError("Expected a missing bucket to be rejected")


def test_resume_storage_defaults_to_sqlite(monkeypatch):
    monkeypatch.delenv("RESUME_STORAGE_BACKEND", raising=False)
    get_resume_file_storage.cache_clear()
    try:
        assert get_resume_file_storage() is None
    finally:
        get_resume_file_storage.cache_clear()


def test_s3_file_metadata_is_kept_in_sqlite_without_duplicating_resume(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "DATABASE_PATH", tmp_path / "test.sqlite3")
    storage.initialize_database()
    user_id = storage.create_initial_user("recruiter@example.test", "Recruiter", "hash")
    vector = np.asarray([0.25, 0.75], dtype="float32")
    resume_id = storage.save_resume(
        user_id, "resume.pdf", "application/pdf", b"", {"candidate_id": "candidate-123"}, vector,
        storage_backend="s3", object_key="resumes/user-1/candidate-123/resume.pdf", file_size=4096,
    )
    row = storage.list_resume_files(user_id)[0]
    assert row["id"] == resume_id
    assert row["file_bytes"] == b""
    assert row["storage_backend"] == "s3"
    assert row["object_key"] == "resumes/user-1/candidate-123/resume.pdf"
    assert row["file_size"] == 4096
    assert storage.get_resume_file_for_candidate(user_id, "candidate-123")["object_key"] == row["object_key"]
    assert storage.get_resume_file_for_candidate(user_id + 1, "candidate-123") is None


def test_multiple_users_can_register_and_duplicate_email_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "DATABASE_PATH", tmp_path / "accounts.sqlite3")
    storage.initialize_database()
    first = storage.create_user("first@example.test", "First Recruiter", "hash-1")
    second = storage.create_user("second@example.test", "Second Recruiter", "hash-2")
    assert first != second
    assert storage.get_user("FIRST@example.test")["display_name"] == "First Recruiter"
    try:
        storage.create_user("first@example.test", "Duplicate", "hash-3")
    except ValueError as exc:
        assert "already exists" in str(exc)
    else:
        raise AssertionError("Duplicate email addresses must not create separate accounts")
