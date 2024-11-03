# celery_app.py
import os
from celery import Celery
from celery import shared_task
import boto3

os.environ["AWS_DEFAULT_REGION"] = "us-east-2"

dynamodb_client = boto3.resource('dynamodb', region_name='us-east-2')


# Create a Celery instance
celery_app = Celery(
    'cseserver',
    broker='sqs://',
    backend='dynamodb://'
)

# Celery configuration
# Celery configuration
celery_app.conf.update(
    result_backend='dynamodb',
    result_backend_settings={
        'table_name': 'CeleryResults',  # Make sure this matches the actual DynamoDB table name
        'region_name': 'us-east-2',
        'aws_access_key_id': 'AKIA6JQ442QOEP3H74TM',
        'aws_secret_access_key': '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',
    },
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    broker_transport_options={
        'region': 'us-east-2',
        'predefined_queues': {
            'analyze-queue': {
                'url': 'https://sqs.us-east-2.amazonaws.com/982534378524/analyze-queue',
            },
            # Add this queue to avoid the UndefinedQueueException
            'celery': {
                'url': 'https://sqs.us-east-2.amazonaws.com/982534378524/analyze-queue',
            }
        },
        'visibility_timeout': 6000,  # Timeout in seconds (adjust as needed)
        'aws_access_key_id': 'AKIA6JQ442QOEP3H74TM',         # Embed your AWS access key here
        'aws_secret_access_key': 'Gn1n9iPTrSODIcX0zSmmaUZUCzOYpGLfy0Od9izm'  # Embed your AWS secret key here

    }
)

celery_app.autodiscover_tasks(['tasks'])

results_table = dynamodb_client.Table('CeleryResults')  # Reference to CeleryResults table for manual result handling
