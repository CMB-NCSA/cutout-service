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
