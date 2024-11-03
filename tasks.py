import os
import time
import json
import redis
from celery import Celery, Task
from celery.exceptions import Retry
from celery_app import celery_app  # Uses the existing Redis configuration
import logging

logger = logging.getLogger(__name__)


# Redis connection
r = redis.Redis(host='localhost', port=6379)

@celery_app.task(name='tasks.analyze_text_async', bind=True, default_retry_delay=60, max_retries=None)
def analyze_text_async(self, text, topics):
    """Analyze large text using ChatGPT with rate limiting."""
    tokens_used = len(text.split())

    # Use Redis to check ChatGPT rate limits
    try:
        check_limit(r, tokens_used)
    except Exception as e:
        raise self.retry(exc=e)  # Retry this task, using the configured delay
    
    from cseserver import analyze_large_text_batched  # Avoid circular import
    result = analyze_large_text_batched(text, topics)

    logger.info(f"Analysis completed: {result[:100] if isinstance(result, str) else result}")
    return result

def check_limit(redis_client, tokens):
    """Check ChatGPT API rate limits using Redis."""
    max_rpm = 500  # ChatGPT requests per minute
    max_tpm = 200000  # ChatGPT tokens per minute
    current_minute = int(time.time() // 60)
    
    # Retrieve current RPM and TPM counts
    current_rpm = int(redis_client.get(f"chatgpt_requests_minute:{current_minute}") or 0)
    current_tpm = int(redis_client.get(f"chatgpt_tokens_minute:{current_minute}") or 0)

    # Request per minute tracking
    if redis_client.incr(f"chatgpt_requests_minute:{current_minute}") > max_rpm:
        raise Exception("ChatGPT request limit reached.")
    redis_client.expire(f"chatgpt_requests_minute:{current_minute}", 60)
    logger.info(f"Current RPM: {current_rpm}/{max_rpm}")

    # Token per minute tracking
    if redis_client.incrby(f"chatgpt_tokens_minute:{current_minute}", tokens) > max_tpm:
        raise Exception("ChatGPT token limit reached.")
    redis_client.expire(f"chatgpt_tokens_minute:{current_minute}", 60)

    logger.info(f"Current TPM: {current_tpm}/{max_tpm}")

