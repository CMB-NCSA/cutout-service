from django.conf import settings
from django.contrib.auth.models import User
from celery import shared_task
from .models import Job, JobFile, JobMetric, FileMetric, Metric
from .log import get_logger
logger = get_logger(__name__)


class CollectMetrics():

    @property
    def task_name(self):
        return "Collect metrics"

    @property
    def task_handle(self):
        return self.task_func

    @property
    def task_frequency_seconds(self):
        return settings.COLLECT_METRICS_INTERVAL

    @property
    def task_initially_enabled(self):
        return True

    def __init__(self, task_func='') -> None:
        self.task_func = task_func

    def run_task(self):
        logger.info(f'Running periodic task "{self.task_name}"...')
        # Count total number of users
        all_users = User.objects.filter()
        # Count total number of job files
        all_job_files = JobFile.objects.filter()
        # Download all cached metrics
        recent_jobs = JobMetric.objects.all()
        recent_jobs_success = recent_jobs.filter(status__exact=Job.JobStatus.SUCCESS)
        recent_jobs_failure = recent_jobs.filter(status__exact=Job.JobStatus.FAILURE)
        recent_job_files = FileMetric.objects.filter(file_type__exact=FileMetric.FileType.JOB)
        # Count number of unique users who ran jobs
        job_owners = []
        for job in recent_jobs:
            if job.owner not in job_owners:
                job_owners.append(job.owner)
        # Record the collected metrics
        metric = Metric(
            jobs_run=len(recent_jobs),
            jobs_success=len(recent_jobs_success),
            jobs_failure=len(recent_jobs_failure),
            users_count=len(all_users),
            users_active=len(job_owners),
            job_files_added=len(recent_job_files),
            job_files_added_size=sum([job_file.size for job_file in recent_job_files]),
            job_files_total=len(all_job_files),
            job_files_size=sum([job_file.size for job_file in all_job_files]),
        )
        metric.save()
        logger.debug(f'Collected metrics object: {metric}')
        # Delete all cached metrics
        JobMetric.objects.all().delete()
        FileMetric.objects.all().delete()


@shared_task
def collect_metrics():
    CollectMetrics().run_task()


periodic_tasks = [
    CollectMetrics(task_func='collect_metrics'),
]
