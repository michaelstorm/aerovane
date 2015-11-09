from django.conf import settings
from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^$', views.IndexView.as_view()),
    url(r'^compute/$', views.CreateComputeGroupView.as_view(providers=settings.CLOUD_PROVIDERS)),
    url(r'^sync/$', views.SyncView.as_view(providers=settings.CLOUD_PROVIDERS)),
]
