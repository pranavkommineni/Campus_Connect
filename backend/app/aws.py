"""Pluggable adapters. Local defaults work with no AWS account; set env vars to use S3 / SQS."""
import json
import uuid
from pathlib import Path

from .core import log, settings


class LocalStorage:
    def save(self, data: bytes, ext: str) -> str:
        Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
        name = f"{uuid.uuid4().hex}{ext}"
        (Path(settings.upload_dir) / name).write_bytes(data)
        return f"/uploads/{name}"


class S3Storage:
    def __init__(self):
        import boto3
        self.client = boto3.client("s3", region_name=settings.aws_region)

    def save(self, data: bytes, ext: str) -> str:
        key = f"posters/{uuid.uuid4().hex}{ext}"
        ctype = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}[ext]
        self.client.put_object(Bucket=settings.s3_bucket, Key=key, Body=data, ContentType=ctype,
                               ServerSideEncryption="aws:kms")
        base = settings.s3_public_base_url.rstrip("/")
        return f"{base}/{key}"


def get_storage():
    return S3Storage() if settings.storage_backend == "s3" else LocalStorage()


class LocalQueue:
    """Development adapter: processes messages inline (notifications are already stored in the DB)."""
    def publish(self, kind: str, payload: dict):
        log.info("queue[local] %s %s", kind, json.dumps(payload))


class SqsQueue:
    def __init__(self):
        import boto3
        self.client = boto3.client("sqs", region_name=settings.aws_region)

    def publish(self, kind: str, payload: dict):
        try:
            self.client.send_message(QueueUrl=settings.sqs_queue_url,
                                     MessageBody=json.dumps({"kind": kind, **payload}))
        except Exception:  # never fail a user request because the queue is down
            log.exception("SQS publish failed for %s", kind)


def get_queue():
    return SqsQueue() if settings.queue_backend == "sqs" and settings.sqs_queue_url else LocalQueue()
