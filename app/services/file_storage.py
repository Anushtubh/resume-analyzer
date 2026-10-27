"""Optional S3 storage for original resume files.

SQLite remains the default for local use. In S3 mode, credentials are resolved
by boto3's standard provider chain (prefer an EC2 instance role in AWS).
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


class S3ResumeStorage:
    def __init__(self, bucket: str, region: str | None = None, prefix: str = "resumes", client=None):
        if not bucket.strip():
            raise ValueError("S3_BUCKET is required when RESUME_STORAGE_BACKEND=s3")
        self.bucket = bucket.strip()
        self.prefix = prefix.strip("/") or "resumes"
        if client is None:
            import boto3

            client = boto3.client("s3", region_name=region or None)
        self.client = client

    def upload(self, user_id: int, candidate_id: str, filename: str, content: bytes,
               content_type: str) -> str:
        safe_filename = Path(filename).name.replace("\\", "_").replace("/", "_")
        key = f"{self.prefix}/user-{int(user_id)}/{candidate_id}/{safe_filename}"
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=content,
            ContentType=content_type or "application/octet-stream",
            ServerSideEncryption="AES256",
        )
        return key

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def download(self, key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read()


@lru_cache(maxsize=1)
def get_resume_file_storage():
    backend = os.getenv("RESUME_STORAGE_BACKEND", "sqlite").strip().lower()
    if backend in {"sqlite", "local", ""}:
        return None
    if backend != "s3":
        raise ValueError("RESUME_STORAGE_BACKEND must be 'sqlite' or 's3'")
    return S3ResumeStorage(
        bucket=os.getenv("S3_BUCKET", ""),
        region=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION"),
        prefix=os.getenv("S3_RESUME_PREFIX", "resumes"),
    )
