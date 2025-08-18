import os
import time
from django.conf import settings
from celery import shared_task
from celery.result import AsyncResult
from .celery import app
from .models import Job
from .object_store import ObjectStore
from .log import get_logger
logger = get_logger(__name__)

s3 = ObjectStore()


@shared_task(name='Revoke Job')
def revoke_job(job_id):
    try:
        # Terminate all workflow tasks
        logger.info(f'''Revoking job "{job_id}"...''')
        job = Job.objects.get(uuid__exact=job_id)
        logger.info(f'''Revoking tasks: {job.task_ids}''')
        # NOTE: Although the documentation says you can supply a list of
        #       task IDs to the terminate/revoke functions, empirically
        #       it only works when you terminate tasks one-by-one.
        app.control.terminate(job_id, signal='SIGKILL')
        for task_id in job.task_ids:
            app.control.terminate(task_id, signal='SIGKILL')

        time_start = time.time()
        timeout = 120  # seconds
        wait = True
        active_job_states = ['STARTED', 'RETRY', 'RECEIVED']
        while timeout > time.time() - time_start and wait:
            wait = False
            for task_id in job.task_ids:
                result = AsyncResult(task_id)
                if result and result.status in active_job_states:
                    logger.info(f'''Waiting for task to stop: {task_id}''')
                    wait = True
            if wait:
                time.sleep(5)
        for task_id in job.task_ids:
            result = AsyncResult(task_id)
            if result and result.status in active_job_states:
                logger.info(f'''Ignoring task {task_id} still in state "{result.status}".''')
    except Exception as err:
        logger.error(f'''Error attempting to terminate job "{job_id}": {err}''')


@shared_task(name='Delete Job Files')
def delete_job_files(job_id):
    job_dir = os.path.join(settings.S3_BASE_DIR, 'jobs', job_id)
    s3.delete_directory(job_dir)


@shared_task(name='Delete Job')
def delete_job(job_id):
    job = Job.objects.get(uuid__exact=job_id)
    job.delete()
