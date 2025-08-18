from django.db import models
import uuid
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User

from .log import get_logger
logger = get_logger(__name__)


class Job(models.Model):
    class Meta:
        # -created means newest first
        # to avoid DRF pagination UnorderedObjectListWarning
        ordering = ['-created']
        # db_table = 'ce_jobs'
        verbose_name = _('job')
        verbose_name_plural = _('jobs')
        permissions = [
            ("run_job", "Can run cutout jobs"),
        ]

    class JobStatus(models.TextChoices):
        # Use the built-in Celery states
        PENDING = 'PENDING', _('Pending')
        STARTED = 'STARTED', _('Started')
        SUCCESS = 'SUCCESS', _('Success')
        FAILURE = 'FAILURE', _('Failure')
        RETRY = 'RETRY', _('Retry')
        REVOKED = 'REVOKED', _('Revoked')

    name = models.TextField(blank=True, null=False, default='')
    description = models.TextField(blank=True, null=False, default='')
    owner = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE)
    error_info = models.TextField(blank=True, null=False, default='')
    config = models.JSONField(blank=True, null=False, default=dict)
    created = models.DateTimeField(auto_now_add=True, verbose_name='Time Created', null=False)
    modified = models.DateTimeField(auto_now=True, verbose_name='Last Modified', null=False)
    task_ids = models.JSONField(null=False, blank=True, default=list)
    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        db_index=True,
        primary_key=True
    )
    status = models.CharField(
        max_length=10,
        choices=JobStatus.choices,
        default=JobStatus.PENDING,
        null=False,
        blank=True,
    )

    def __str__(self):
        ret = f'job: {self.uuid}, owner: {self.owner}, status: {self.status}'
        ret += f', created: {self.created}, config: {self.config}'
        return ret


class JobFile(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE)
    path = models.CharField(max_length=None, default='')
    # Size of the stored file in bytes
    size = models.BigIntegerField(null=False, blank=False, default=0)


def update_job_state(job_id, state, error_info=''):
    logger.debug(f'''Updating job "{job_id}" state to: "{state}"...''')
    job = Job.objects.get(uuid__exact=job_id)
    job.status = state
    job.error_info = error_info
    # Forcibly clear current processes list
    if state in [Job.JobStatus.SUCCESS, Job.JobStatus.FAILURE]:
        job.current_processes = []
    job.save()


class JobMetric(models.Model):
    time_collected = models.DateTimeField(auto_now_add=True, verbose_name='Time Collected')
    status = models.CharField(max_length=10, choices=Job.JobStatus.choices)
    owner = models.ForeignKey(User, null=False, blank=False, on_delete=models.CASCADE)
    config = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f'job metric: {self.time_collected}, {self.status}, {self.owner}'


class FileMetric(models.Model):
    class FileType(models.TextChoices):
        JOB = 'job'

    time_collected = models.DateTimeField(auto_now_add=True, verbose_name='Time Collected')
    size = models.BigIntegerField(null=False, blank=False, default=0)  # Size of the stored file in bytes
    owner = models.ForeignKey(User, null=False, blank=False, on_delete=models.CASCADE)
    file_type = models.CharField(max_length=6, choices=FileType.choices, blank=False, null=False, default=FileType.JOB)

    def __str__(self):
        return f'file metric: {self.time_collected}, {self.file_type}, {self.size}, {self.owner}'


class Metric(models.Model):
    time_collected = models.DateTimeField(auto_now_add=True, verbose_name='Time Collected')
    jobs_run = models.IntegerField(null=False, blank=False, default=0)
    jobs_success = models.IntegerField(null=False, blank=False, default=0)
    jobs_failure = models.IntegerField(null=False, blank=False, default=0)
    users_count = models.IntegerField(null=False, blank=False, default=0)
    users_active = models.IntegerField(null=False, blank=False, default=0)
    job_files_total = models.IntegerField(null=False, blank=False, default=0)
    job_files_size = models.BigIntegerField(null=False, blank=False, default=0)
    job_files_added = models.IntegerField(null=False, blank=False, default=0)
    job_files_added_size = models.BigIntegerField(null=False, blank=False, default=0)

    def __str__(self):
        return (
            f'time_collected: {self.time_collected}, '
            f'jobs_run: {self.jobs_run}, '
            f'jobs_success: {self.jobs_success}, '
            f'jobs_failure: {self.jobs_failure}, '
            f'users_count: {self.users_count}, '
            f'users_active: {self.users_active}, '
            f'job_files_total: {self.job_files_total}, '
            f'job_files_size: {self.job_files_size}, '
            f'job_files_added: {self.job_files_added}, '
            f'job_files_added_size: {self.job_files_added_size}, '
        )
