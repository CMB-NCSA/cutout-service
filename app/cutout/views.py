import yaml
import os
from django.http import StreamingHttpResponse
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import UserPassesTestMixin
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User
from rest_framework.decorators import api_view
from rest_framework import permissions
from django.shortcuts import render
from django.conf import settings
from django.views.generic import DetailView, ListView
from rest_framework.permissions import BasePermission
from django.http import HttpResponseForbidden
from rest_framework import viewsets, status
from .models import Job, JobFile
from .workflows import launch_workflow
from .serializers import JobSerializer, UserSerializer
from rest_framework.response import Response
from .object_store import ObjectStore
from .tasks import process_config
from .tasks_api import revoke_job, delete_job, delete_job_files
from celery import chain, group
from .forms import CutoutForm
from django.http import HttpResponseRedirect, HttpResponseBadRequest
from .log import get_logger
logger = get_logger(__name__)

s3 = ObjectStore()


# Handler for 403 errors
def error_view(request, exception, template_name="cutout/access_denied.html"):
    return render(request, template_name)


class CustomAuthToken(UserPassesTestMixin, ObtainAuthToken):
    permission_classes = [permissions.IsAuthenticated]

    def test_func(self):
        return self.request.user.has_perms(('cutout.run_job',))

    def get(self, request, format=None):
        token, created = Token.objects.get_or_create(user=request.user)
        return Response({'token': token.key})


@api_view(['POST'])
def get_token(request, format=None):
    response = Response()
    username = request.data['username']
    password = request.data['password']
    logger.debug(f'Fetching token for username "{username}"')
    user_search = User.objects.filter(username__exact=username)
    if not user_search:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response
    user = user_search[0]
    if not user.check_password(password):
        response.status_code = status.HTTP_403_FORBIDDEN
        return response
    token, created = Token.objects.get_or_create(user=user)
    logger.debug(f'token for username "{username}": "{token.key}')
    return Response(data={'token': token.key})


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


class RunJob(BasePermission):
    def has_permission(self, request, view):
        logger.debug(f'''user.has_perms: {request.user.has_perms(('cutout.run_job',))}''')
        return request.user.has_perms(('cutout.run_job',))


class UserListView(UserPassesTestMixin, ListView):

    def test_func(self):
        return self.request.user.is_superuser

    def handle_no_permission(self):
        return HttpResponseForbidden(content='You must be authenticated.')

    model = User
    template_name = 'cutout/user_list.html'


class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]


class JobViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows jobs to be viewed or edited.
    """
    model = Job
    serializer_class = JobSerializer
    permission_classes = [IsAdmin | IsStaff | RunJob]

    def get_queryset(self):
        queryset = Job.objects.filter(owner__exact=self.request.user)
        return queryset

    def perform_create(self, serializer):
        serializer.is_valid(raise_exception=True)
        return serializer.save(owner=self.request.user)

    def create(self, request, *args, **kwargs):
        logger.debug(f'Creating job from request: {request.data}')
        # Create the Job table record
        response = super().create(request, args, kwargs)
        new_job_data = response.data
        job_id = str(new_job_data['uuid'])
        job_name = new_job_data['name']
        new_job = Job.objects.get(uuid__exact=job_id)
        # Process the config and update the job record
        config, err_msg = process_config(new_job_data['config'])
        try:
            assert not err_msg
        except AssertionError:
            logger.error(f'''Invalid config: {err_msg}''')
            response = Response(
                status=status.HTTP_400_BAD_REQUEST,
                data=f'''Invalid config: {err_msg}''',
            )
            new_job.delete()
            return response
        new_job.config = config
        new_job.save()
        # Launch workflow as async Celery tasks
        logger.debug(f'''Job info: {response.data}''')
        logger.debug(f'''Launching Celery task for workflow "{job_name}"...''')
        updated_response = launch_workflow(job_id, config)
        if updated_response:
            response = updated_response
        return response

    def destroy(self, request, pk=None, *args, **kwargs):
        job_id = pk
        logger.debug(f'''Deleting job "{job_id}"...''')
        response = Response(status=status.HTTP_204_NO_CONTENT)
        # If the authenticated user does not own the job, do not delete anything
        job = Job.objects.filter(uuid__exact=job_id)
        if not job:
            response.data = f'Job {job_id} not found.'
            response.status_code = status.HTTP_404_NOT_FOUND
            return response
        # Allow admin to delete any job
        if not self.request.user.username == settings.DJANGO_SUPERUSER_USERNAME:
            job = job.filter(owner__exact=self.request.user)
            if not job:
                response.data = f'You must be the job owner to delete it: {job_id}.'
                response.status_code = status.HTTP_403_FORBIDDEN
                return response
        logger.info(f'''Deleting job "{job_id}"...''')
        # Delete job record from database and delete job files
        # after revoking workflow tasks using async Celery tasks
        delete_chain = chain(
            revoke_job.si(job_id),
            group([
                delete_job.si(job_id),
                delete_job_files.si(job_id),
            ]),
        )
        delete_chain.delay()
        return response


@permission_required("cutout.run_job", raise_exception=True)
def job_list(request):
    jobs = Job.objects.filter(owner__exact=request.user)
    logger.debug(jobs)
    token, created = Token.objects.get_or_create(user=request.user)
    context = {
        'job_list': jobs,
        'api_token': token.key,
    }
    return render(request, "cutout/job_list.html", context)


@permission_required("cutout.run_job", raise_exception=True)
def cutout_form(request):
    # if this is a POST request we need to process the form data
    if request.method == "POST":
        # create a form instance and populate it with data from the request:
        form = CutoutForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            # process the data in form.cleaned_data as required

            logger.debug(f'''Form data: {form.cleaned_data}''')
            name = form.cleaned_data['job_name']
            description = form.cleaned_data['job_description']
            new_job = Job(
                name=name,
                description=description,
                owner=request.user,
            )
            job_id = str(new_job.uuid)
            input_csv = form.cleaned_data['input_csv'].replace('\r\n', '\n')
            xsize = form.cleaned_data['xsize']
            ysize = form.cleaned_data['ysize']
            bands = form.cleaned_data['bands']
            # colorset = form.cleaned_data['colorset']
            config, err_msg = process_config(config={
                'input_csv': input_csv,
                'xsize': xsize,
                'ysize': ysize,
                'bands': bands,
                # 'colorset': colorset,
            })
            try:
                assert not err_msg
            except AssertionError:
                logger.error(f'''Invalid config: {err_msg}''')
                new_job.delete()
                return HttpResponseBadRequest(content=f'''Invalid config: {err_msg}''')
            new_job.config = config
            new_job.save()
            # Launch workflow as async Celery tasks
            logger.debug(f'''Launching Celery task for workflow "{name}"...''')
            response = launch_workflow(job_id, config)
            if response:
                return HttpResponseBadRequest(content=response.data)
            return HttpResponseRedirect(f'''/jobs/{job_id}''')

    # if a GET (or any other method) we'll create a blank form
    else:
        form = CutoutForm()

    context = {
        # "form": form,
        "textarea_initial": '''RA,DEC,XSIZE,YSIZE\n49.9208333333, -19.4166666667, 6.6, 3.3'''
    }
    return render(request, "cutout/cutout_form.html", context)


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
        for filtered_key in ['prefix']:
            self.object.config.pop(filtered_key)
        self.object.config['logfile'] = '/cutout.log'
        context["config"] = yaml.dump(self.object.config, indent=2, sort_keys=False)
        return context


class JobFileDownloadViewSet(viewsets.ViewSet):

    permission_classes = [IsAdmin | IsStaff | RunJob]
    throttle_scope = 'download'

    def download(self, request, job_id=None, file_path=None, *args, **kwargs):
        job_id = str(job_id)
        file_path = file_path.strip('/')
        obj_key = os.path.join(settings.S3_BASE_DIR, 'jobs', job_id, file_path)
        file_path = os.path.join('/', file_path)
        response = Response()
        job_file = JobFile.objects.filter(job__owner__exact=self.request.user,
                                          job__uuid__exact=job_id,
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
