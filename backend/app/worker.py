"""SQS consumer for async notification/event jobs.  python -m app.worker
Failed messages are NOT deleted; SQS redelivers them after the visibility timeout and moves them to the
dead-letter queue after maxReceiveCount attempts (configured on the queue, see infra/aws-resources.yaml)."""
import json
import time

from .core import log, settings


def handle(msg: dict):
    # Extension point: send e-mail/push via SES/SNS. Notifications are already persisted in the DB by the API.
    if msg.get("kind") == "notification":
        log.info("deliver notification to user %s: %s", msg.get("user_id"), msg.get("message"))
    else:
        raise ValueError(f"unknown message kind {msg.get('kind')!r}")


def main():
    if not settings.sqs_queue_url:
        raise SystemExit("Set SQS_QUEUE_URL (and QUEUE_BACKEND=sqs) to run the worker.")
    import boto3
    sqs = boto3.client("sqs", region_name=settings.aws_region)
    log.info("worker polling %s", settings.sqs_queue_url)
    while True:
        resp = sqs.receive_message(QueueUrl=settings.sqs_queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=20)
        for m in resp.get("Messages", []):
            try:
                handle(json.loads(m["Body"]))
                sqs.delete_message(QueueUrl=settings.sqs_queue_url, ReceiptHandle=m["ReceiptHandle"])
            except Exception:
                log.exception("message failed; will be retried / dead-lettered")
        if not resp.get("Messages"):
            time.sleep(1)


if __name__ == "__main__":
    main()
