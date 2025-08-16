import yaml
import os
from django.http import StreamingHttpResponse
from django.shortcuts import render
from django.conf import settings
from django.views.generic import ListView, DetailView
from rest_framework.permissions import BasePermission
from rest_framework import viewsets, status
from .models import Job, JobFile
from .models import update_job_state
from .workflows import run_workflow
from .serializers import JobSerializer
from rest_framework.response import Response
from .object_store import ObjectStore
from .tasks import process_config
from .log import get_logger
logger = get_logger(__name__)

s3 = ObjectStore()


def HomePageView(request):
    context = {
        'title': 'Cutout Service',
        'url': settings.HOSTNAMES[0],
    }
    return render(request, "cutout/home.html", context)


class IsStaff(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_staff


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_superuser


class JobViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows jobs to be viewed or edited.
    """
    model = Job
    serializer_class = JobSerializer
    # permission_classes = [IsStaff | IsAdmin]

    def get_queryset(self):
        queryset = Job.objects.all()
        return queryset

    def create(self, request, *args, **kwargs):
        logger.debug(f'Creating job from request: {request.data}')
        # Create the Job table record
        response = super().create(request, args, kwargs)
        new_job_data = response.data
        job_id = str(new_job_data['uuid'])
        job_name = new_job_data['name']
        try:
            # Process the config and update the job record
            config = process_config(job_id, new_job_data['config'])
            new_job = Job.objects.get(uuid__exact=job_id)
            new_job.config = config
            new_job.save()
        except Exception as err:
            logger.error(f'''Error: {err}''')
            response = Response(
                status_code=status.HTTP_400_BAD_REQUEST,
                data=f'''{err}''',
            )
            update_job_state(job_id, Job.JobStatus.FAILURE, error_info=f"Error requesting the config file: {err}")
            return response
        # Launch workflow as async Celery tasks
        logger.debug(f'''Launching Celery task for workflow "{job_name}"...''')
        try:
            # Launch workflow
            run_workflow(job_id, config)
        except Exception as err:
            err_msg = f'Failed to launch workflow: {err}'
            logger.error(err_msg)
            response = Response(
                status=status.HTTP_400_BAD_REQUEST,
                data=f'''{err_msg}''',
            )
            update_job_state(job_id, Job.JobStatus.FAILURE, error_info=err_msg)
        return response


class JobListView(ListView):

    model = Job
    template_name = 'cutout/job_list.html'
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset()


class JobDetailView(DetailView):

    model = Job
    template_name = 'cutout/job_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        job_id = self.kwargs['pk']
        # context["files"] = JobFile.objects.filter(job__owner__exact=self.request.user,
        #                                           job__uuid__exact=self.kwargs['pk'])
        context["files"] = JobFile.objects.filter(job__uuid__exact=job_id)
        # The apparent double-newline in the CSV text rendering is not actually a bug;
        # this is how a single newline renders when using single-quotes.
        context["coords"] = self.object.config.pop('coords')
        for filtered_key in ['outdir', 'dbname', 'prefix']:
            self.object.config.pop(filtered_key)
        self.object.config['logfile'] = self.object.config['logfile'].replace(f'/scratch/{job_id}', '')
        context["config"] = yaml.dump(self.object.config, indent=2, sort_keys=False)
        return context


class JobFileDownloadViewSet(viewsets.ViewSet):

    # permission_classes = [IsStaff | IsAdmin]
    throttle_scope = 'download'

    def download(self, request, job_id=None, file_path=None, *args, **kwargs):
        job_id = str(job_id)
        file_path = file_path.strip('/')
        obj_key = os.path.join(settings.S3_BASE_DIR, 'jobs', job_id, file_path)
        file_path = os.path.join('/', file_path)
        response = Response()
        # job_file = JobFile.objects.filter(job__owner__exact=self.request.user,
        #                                   job__uuid__exact=job_id,
        #                                   path__exact=file_path)
        job_file = JobFile.objects.filter(job__uuid__exact=job_id,
                                          path__exact=file_path)
        if not job_file:
            response.data = f'File "{file_path}" not found for job {job_id}.'
            response.status_code = status.HTTP_404_NOT_FOUND
            return response
        job_file = job_file[0]
        obj_stream = s3.stream_object(obj_key)
        response = StreamingHttpResponse(streaming_content=obj_stream)
        response['Content-Disposition'] = 'attachment; filename="%s"' % os.path.basename(file_path)
        return response
