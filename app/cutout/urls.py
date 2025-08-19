from django.urls import path
from django.urls import re_path
from django.urls import include
from django.contrib.auth.decorators import login_required
from django.contrib import admin
from cutout import views
from rest_framework import routers

from .log import get_logger
logger = get_logger(__name__)

handler403 = "cutout.views.error_view"

job_api_router = routers.DefaultRouter()
job_api_router.register('', views.JobViewSet, basename='job')
user_api_router = routers.DefaultRouter()
user_api_router.register('', views.UserViewSet, basename='user')

api_urlpatterns = [
    path('job/', include(job_api_router.urls)),
    path('token/', views.get_token, name='token-api'),
]

jobfile_detail = views.JobFileDownloadViewSet.as_view({
    'get': 'download',
    'post': 'download',
})

urlpatterns = [
    path('', views.HomePageView, name='home'),
    path('admin/', admin.site.urls),
    path('user/', include(user_api_router.urls)),
    path('api/', include(api_urlpatterns)),
    path('jobs/', login_required(views.job_list), name='jobs-page'),
    path('jobs/<uuid:pk>', login_required(views.JobDetailView.as_view()), name='job-detail-page'),
    path('download/<uuid:job_id>/<path:file_path>', login_required(jobfile_detail), name='download-job-file'),
    re_path(r"^accounts/", include("django.contrib.auth.urls")),
    path('oidc/', include("mozilla_django_oidc.urls")),
    path('token/', views.CustomAuthToken.as_view(), name='token'),
    path('cutout/', views.cutout_form, name='cutout-form'),
]
