from django.urls import path
from django.urls import include
from cutout import views
from rest_framework import routers

from .log import get_logger
logger = get_logger(__name__)

job_api_router = routers.DefaultRouter()
job_api_router.register('', views.JobViewSet, basename='job')

api_urlpatterns = [
    path('job/', include(job_api_router.urls)),
]

jobfile_detail = views.JobFileDownloadViewSet.as_view({
    'get': 'download',
    'post': 'download',
})

urlpatterns = [
    path('', views.HomePageView, name='home'),
    path('api/', include(api_urlpatterns)),
    path('jobs/', views.JobListView.as_view(), name='job-page'),
    path('jobs/<uuid:pk>', views.JobDetailView.as_view(), name='job-detail-page'),
    path('download/<uuid:job_id>/<path:file_path>', jobfile_detail, name='download-job-file'),
]
