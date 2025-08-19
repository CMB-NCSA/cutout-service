from celery import chain
import json
import os
import yaml
from .models import Job, JobMetric
from .models import update_job_state
from celery import shared_task
from .tasks import generate_cutouts
from django.conf import settings
from .object_store import ObjectStore
from datetime import datetime, timezone
from rest_framework.response import Response
from rest_framework import status
from .log import get_logger
logger = get_logger(__name__)

s3 = ObjectStore()


def launch_workflow(job_id, config):
    response = None
    try:
        # Launch workflow with validated config
        run_workflow(job_id, config)
    except Exception as err:
        err_msg = f'Failed to launch workflow: {err}'
        logger.error(err_msg)
        response = Response(
            status=status.HTTP_400_BAD_REQUEST,
            data=f'''{err_msg}''',
        )
        update_job_state(job_id, Job.JobStatus.FAILURE, error_info=err_msg)
        logger.debug(f'''[{response.status_code}] {response.data}''')
    return response


def run_workflow(job_id, config) -> None:
    def find_task_ids(tasks_obj, task_ids=None):
        if task_ids is None:
            task_ids = []
        if isinstance(tasks_obj, list):
            for tasks_obj_item in tasks_obj:
                task_ids = find_task_ids(tasks_obj_item, task_ids.copy())
        elif isinstance(tasks_obj, dict):
            for tasks_obj_key, tasks_obj_val in tasks_obj.items():
                if tasks_obj_key == 'task_id' and isinstance(tasks_obj_val, str) and tasks_obj_val not in task_ids:
                    task_ids.append(tasks_obj_val)
                else:
                    task_ids = find_task_ids(tasks_obj_val, task_ids.copy())
        return task_ids

    # Define workflow
    logger.debug(f'job_id: {job_id}')
    workflow = chain(
        workflow_init.si(job_id=job_id, config=config),
        generate_cutouts.si(job_id=job_id, config=config).set(task_id=job_id),
        workflow_complete.si(job_id=job_id),
    )
    # Mark job status as STARTED
    update_job_state(job_id, Job.JobStatus.STARTED)
    # Use the freeze() function to provision static task IDs so they can
    # be revoked if the job is deleted before the workflow completes.
    workflow.freeze()
    workflow.on_error(wf_error_handler.s(job_id=job_id)).apply_async()
    # Collect all workflow task IDs and store with job so
    # they can be revoked when a job is deleted.
    workflow_task_ids = find_task_ids(workflow.tasks)
    logger.debug('Workflow task_ids:')
    logger.debug(json.dumps(workflow_task_ids, indent=2))
    job = Job.objects.get(uuid__exact=job_id)
    job.task_ids = workflow_task_ids
    job.save()


@shared_task(name='Workflow Init')
def workflow_init(job_id: str = '', config: dict = {}):
    # wait_for_free_space()
    # If enough scratch space is available, mark job status as STARTED
    update_job_state(job_id, Job.JobStatus.STARTED)
    # Write workflow config to output folder
    s3_basepath = os.path.join(
        settings.S3_BASE_DIR,
        f'''jobs/{job_id}''')
    s3.put_object(data=yaml.dump(config),
                  path=os.path.join(s3_basepath, 'config.yaml'),
                  json_output=False)
    # Write metadata file to capture provenance info
    metadata = {
        'cutout_service': {
            'version': settings.APP_VERSION,
        },
        'job': {
            'time': datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            'uuid': job_id,
        }
    }
    s3.put_object(data=yaml.dump(metadata),
                  path=os.path.join(s3_basepath, 'meta.yaml'),
                  json_output=False)


@shared_task(name='Workflow Complete')
def workflow_complete(job_id=''):
    logger.info(f'''Workflow for job "{job_id}" completed successfully.''')
    # Set workflow status to success
    update_job_state(job_id, Job.JobStatus.SUCCESS)
    # Record the job metadata for metrics collection
    job = Job.objects.get(uuid__exact=job_id)
    JobMetric.objects.create(
        status=Job.JobStatus.SUCCESS,
        owner=job.owner,
        config=job.config,
    )


@shared_task(name='Workflow Job Error Handler')
def wf_error_handler(request, exc, traceback, job_id):
    logger.error(f'''Workflow error! Celery task ID: {request.id}, job ID: {job_id}''')
    logger.error(f'''exc: {exc}''')
    logger.error(f'''traceback: {traceback}''')
