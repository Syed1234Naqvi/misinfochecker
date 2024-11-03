# celery_app.py
import os
from celery import Celery
from celery import shared_task

# Create a Celery instance using Redis as the broker and result backend
celery_app = Celery(
    'cseserver',
    broker=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0')
)

# Celery configuration
celery_app .conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True
)


celery_app.autodiscover_tasks(['tasks'])

