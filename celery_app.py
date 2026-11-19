import os
from celery import Celery
import boto3

AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
AWS_ENDPOINT_URL = os.getenv("AWS_ENDPOINT_URL", "https://127.0.0.1:9297")
AWS_SSL_VERIFY = os.getenv("AWS_SSL_VERIFY", "true").lower() not in {
    "0",
    "false",
    "no",
}
AWS_QUEUE_URL = os.getenv(
    "AWS_SQS_QUEUE_URL",
    f"{AWS_ENDPOINT_URL}/000000000000/analyze-queue",
)
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "sqs://")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "dynamodb://")

dynamodb_client = boto3.resource(
    "dynamodb",
    region_name=AWS_REGION,
    endpoint_url=AWS_ENDPOINT_URL,
    verify=AWS_SSL_VERIFY,
)


celery_app = Celery(
    "cseserver",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

broker_transport_options = {}
if CELERY_BROKER_URL.startswith("sqs://"):
    broker_transport_options = {
        "region": AWS_REGION,
        "endpoint_url": AWS_ENDPOINT_URL,
        "predefined_queues": {
            "analyze-queue": {
                "url": AWS_QUEUE_URL,
            },
            "celery": {
                "url": AWS_QUEUE_URL,
            },
        },
        "visibility_timeout": 6000,
    }

result_backend_settings = {}
if CELERY_RESULT_BACKEND.startswith("dynamodb://"):
    result_backend_settings = {
        "table_name": "CeleryResults",
        "region_name": AWS_REGION,
        "endpoint_url": AWS_ENDPOINT_URL,
        "verify": AWS_SSL_VERIFY,
    }

celery_app.conf.update(
    result_backend=CELERY_RESULT_BACKEND,
    result_backend_settings=result_backend_settings,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_transport_options=broker_transport_options,
)

celery_app.autodiscover_tasks(["tasks"])

results_table = dynamodb_client.Table("CeleryResults")
