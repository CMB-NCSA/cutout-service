from django.shortcuts import render
from django.conf import settings
from cutout.log import get_logger
logger = get_logger(__name__)


def HomePageView(request):
    context = {
        'title': 'Cutout Service',
        'url': settings.HOSTNAMES[0],
    }
    return render(request, "cutout/home.html", context)
