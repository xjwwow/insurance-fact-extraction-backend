from celery import Celery

from app.core.config import settings


if settings.celery_task_always_eager:
    broker_url = "memory://"
    result_backend = "cache+memory://"
else:
    broker_url = settings.celery_broker_url
    result_backend = settings.celery_result_backend


celery_app = Celery(
    "insurance_fact_extraction",
    broker=broker_url,
    backend=result_backend,
    include=["app.tasks.parse_tasks"],
)

celery_app.conf.update(
    task_track_started=settings.celery_task_track_started,
    task_always_eager=settings.celery_task_always_eager,
    task_store_eager_result=settings.celery_task_store_eager_result,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=False,
)
