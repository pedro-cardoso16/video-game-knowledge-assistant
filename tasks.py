"""
tasks.py - Asynchronous background ingestion workers using Celery and Redis.
Implements atomic idempotency locks, exponential backoff with jitter, and Dead-Letter Queue (DLQ).
"""
import os
import time
from celery import Celery
import redis

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

celery_app = Celery("ingestion_tasks", broker=REDIS_URL, backend=REDIS_URL)

# Configure Dead-Letter Queue (DLQ) routing
celery_app.conf.task_routes = {
    "tasks.quarantine_dead_letter": {"queue": "dlq_poisoned_tasks"},
}

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)

@celery_app.task(
    bind=True,
    max_retries=3,
    retry_backoff=True,          # Exponential backoff
    retry_jitter=True,           # Random jitter to prevent thundering herd
    autoretry_for=(ConnectionError, TimeoutError),
)
def async_ingest_game_task(self, game_id: str, source: str = "igdb"):
    """Idempotent ingestion worker protected by atomic Redis locks."""
    lock_key = f"lock:ingest:{game_id}"

    # 1. Atomic Idempotency Guard via Redis SETNX
    is_acquired = redis_client.set(lock_key, "PROCESSING", nx=True, ex=300)
    if not is_acquired:
        return {"status": "SKIPPED_DUPLICATE", "game_id": game_id}

    try:
        # Simulates asynchronous ingestion pipeline execution
        time.sleep(0.2)
        return {"status": "SUCCESS", "game_id": game_id, "source": source}

    except Exception as exc:
        if self.request.retries >= self.max_retries:
            # Route to DLQ on final failure
            celery_app.send_task(
                "tasks.quarantine_dead_letter",
                args=[game_id, str(exc)],
                queue="dlq_poisoned_tasks"
            )
        raise self.retry(exc=exc)

    finally:
        redis_client.delete(lock_key)

@celery_app.task
def quarantine_dead_letter(game_id: str, error_message: str):
    """Dead-Letter Queue handler for poisoned/failing ingestion tasks."""
    return {"quarantined": True, "game_id": game_id, "error": error_message}