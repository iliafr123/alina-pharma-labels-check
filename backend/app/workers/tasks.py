# Celery tasks — populated in Phase 3
from app.workers.celery_app import celery_app


@celery_app.task(bind=True, name="run_check_pipeline")
def run_check_pipeline(self, task_id: str):
    """Main pipeline task — implemented in Phase 3."""
    pass
