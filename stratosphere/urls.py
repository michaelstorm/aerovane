from django.conf.urls import url, include
from django.views.generic.base import RedirectView

from . import views, aws_iam

urlpatterns = [
    url(r'^$', RedirectView.as_view(url='/compute_groups/', permanent=False)),
    url(r'^operating_system/$', views.operating_systems),
    url(r'^compute/$', views.compute),
    url(r'^compute/(?P<group_id>\w+)/$', views.compute),
    url(r'^authentication_methods/$', views.authentication_methods),
    url(r'^authentication_methods/(?P<method_id>\w+)/$', views.authentication_methods),
    url(r'^providers/(?P<provider_name>\w+)/$', views.configure_provider),
    url(r'^providers/(?P<provider_id>\w+)/disk_images/$', views.provider_disk_images),
    url(r'^providers/(?P<provider_name>\w+)/(?P<action>restore|fail)/$', views.provider_action),

    url(r'^compute_groups/$', views.compute_groups),
    url(r'^compute_groups/add/$', views.add_compute_group),
    url(r'^check_configure/$', views.check_configure),
    url(r'^authentication/$', views.authentication),
    url(r'^providers/$', views.providers),
    url(r'^images/$', views.images),

    url(r'^aws_iam$', aws_iam.initial),
    url(r'^accounts/', include('allauth.urls')),
]
