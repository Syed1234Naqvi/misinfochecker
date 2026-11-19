import os
import time
import json
from celery import Celery, Task
from celery.exceptions import Retry
from celery_app import celery_app
import logging
import boto3
from botocore.exceptions import ClientError
import time

# Initialize DynamoDB and reference the two tables
dynamodb = boto3.resource(
    "dynamodb",
    region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
    endpoint_url=os.getenv("AWS_ENDPOINT_URL", "https://127.0.0.1:9297"),
    verify=os.getenv("AWS_SSL_VERIFY", "true").lower() not in {"0", "false", "no"},
)
rate_limit_table = dynamodb.Table("RateLimits")
results_table = dynamodb.Table("CeleryResults")

logger = logging.getLogger(__name__)

@celery_app.task(name='tasks.analyze_text_async', bind=True, default_retry_delay=60, max_retries=None)
def analyze_text_async(self, text, topics):
    """Analyze large text using ChatGPT with rate limiting."""
    tokens_used = len(text.split())

    try:
        check_limit(tokens_used, self.request.id)
    except Exception as e:
        raise self.retry(exc=e)  # Retry this task, using the configured delay

    from cseserver import analyze_large_text_batched  # Avoid circular import
    result = analyze_large_text_batched(text, topics)

    # Store the result in DynamoDB with TTL to expire results automatically
    results_table.put_item(
        Item={
            'task_id': self.request.id,
            'result': result,
            'processed_at': int(time.time()),
            'ttl': int(time.time()) + 3600  # TTL set to 1 hour (3600 seconds)
        }
    )

    logger.info(f"Analysis completed: {result[:100] if isinstance(result, str) else result}")
    return result

def check_limit(tokens, task_id):
    """Check ChatGPT API rate limits using DynamoDB with deduplication."""
    max_rpm = 500  # ChatGPT requests per minute
    max_tpm = 200000  # ChatGPT tokens per minute
    current_minute = int(time.time() // 60)

    # Keys for rate limiting
    current_rpm_key = f"chatgpt_requests_minute:{current_minute}"
    current_tpm_key = f"chatgpt_tokens_minute:{current_minute}"

    # Deduplication: Check if this task_id has already been processed in CeleryResults
    try:
        response = results_table.get_item(Key={'task_id': task_id})
        if 'Item' in response:
            logger.info(f"Duplicate task detected: {task_id}. Skipping.")
            return
    except ClientError as e:
        logger.info(e.response['Error']['Message'])

    # Proceed to increment counters in DynamoDB for rate limits
    # Increment RPM
    response = rate_limit_table.update_item(
        Key={'limit_key': current_rpm_key},
        UpdateExpression="SET #counter = if_not_exists(#counter, :start) + :inc",
        ExpressionAttributeNames={'#counter': 'counter'},
        ExpressionAttributeValues={':inc': 1, ':start': 0},
        ReturnValues="UPDATED_NEW"
    )
    # Check RPM
    if response['Attributes']['counter'] > max_rpm:
        raise Exception("ChatGPT request limit reached.")

    # Increment TPM
    response = rate_limit_table.update_item(
        Key={'limit_key': current_tpm_key},
        UpdateExpression="SET #counter = if_not_exists(#counter, :start) + :tokens",
        ExpressionAttributeNames={'#counter': 'counter'},
        ExpressionAttributeValues={':tokens': tokens, ':start': 0},
        ReturnValues="UPDATED_NEW"
    )
    # Check TPM
    if response['Attributes']['counter'] > max_tpm:
        raise Exception("ChatGPT token limit reached.")
