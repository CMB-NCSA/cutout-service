from .models import Job, JobFile
from rest_framework import serializers
from .log import get_logger
logger = get_logger(__name__)


class JobSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Job
        read_only_fields = ['owner', 'created', 'uuid', 'error_info', 'status', 'modified', 'files', 'task_ids']
        fields = read_only_fields + ['name', 'description', 'files', 'config']
    files = serializers.SerializerMethodField()
    config = serializers.JSONField(initial={})

    def get_files(self, job):
        jobfiles = JobFile.objects.filter(job__exact=job)
        return [{'path': jobfile.path, 'size': jobfile.size} for jobfile in jobfiles]
