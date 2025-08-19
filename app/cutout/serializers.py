from .models import Job, JobFile
from django.contrib.auth.models import User
from rest_framework import serializers
from .log import get_logger
logger = get_logger(__name__)


class UserSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="user-detail")

    class Meta:
        model = User
        fields = ['url', 'username', 'email', 'groups']


class JobSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Job
        read_only_fields = ['owner', 'created', 'uuid', 'error_info', 'status', 'modified', 'files', 'task_ids']
        fields = read_only_fields + ['name', 'description', 'files', 'config']
    files = serializers.SerializerMethodField()
    config = serializers.JSONField(initial={
        'input_csv': 'RA,DEC,XSIZE,YSIZE\n#0.29782658,0.029086056,3,3\n49.9208333333,-19.4166666667,6.6,6.6\n'
    })

    def get_files(self, job):
        jobfiles = JobFile.objects.filter(job__exact=job)
        return [{'path': jobfile.path, 'size': jobfile.size} for jobfile in jobfiles]
