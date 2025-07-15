from django.urls import path
from cutout import views
from cutout.log import get_logger
logger = get_logger(__name__)


urlpatterns = [
    path('', views.HomePageView, name='home'),
]
