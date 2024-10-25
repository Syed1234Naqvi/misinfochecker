# tasks.py
from celery_app import celery_app
import logging
from openai import OpenAI
import os
from celery import shared_task


client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
logger = logging.getLogger(__name__)

@celery_app.task(name='tasks.analyze_text_async')  # Register the task with an explicit name
def analyze_text_async(text, topics):
    """Analyze large text in the background using Celery."""
    # Perform text analysis logic here (can reuse your analyze_large_text_batched logic)
    from cseserver import analyze_large_text_batched  # Avoid circular imports
    result = analyze_large_text_batched(text, topics)
    logger.info(f"Analysis completed: {result[:100]}")
    return result
