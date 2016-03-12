from django.conf.urls import url, include
from django.views.generic.base import RedirectView

from . import views, aws
# from .modelviews.password_authentication_method.new import NewPasswordAuthenticationMethodView

urlpatterns = [
    url(r'^$', RedirectView.as_view(url='/compute_groups/', permanent=False)),
    url(r'^operating_system/$', views.operating_systems),
    url(r'^compute/$', views.compute),
    url(r'^compute/(?P<group_id>\d+)/$', views.compute),
    url(r'^compute/state_history/$', views.state_history),
    url(r'^authentication_methods/$', views.authentication_methods),
    url(r'^authentication_methods/(?P<method_id>\d+)/$', views.authentication_methods),
    url(r'^providers/loaded/$', views.providers_loaded),
    url(r'^providers/(?P<provider_name>\w+)/$', views.configure_provider),
    url(r'^providers/(?P<provider_id>\d+)/disk_images/$', views.provider_disk_images),
    url(r'^providers/(?P<provider_id>\d+)/(?P<action>restore|fail)/$', views.provider_action),

    url(r'^compute_groups/$', views.compute_groups),
    url(r'^compute_groups/add/$', views.add_compute_group),
    url(r'^check_configure/$', views.check_configure),
    url(r'^authentication/$', views.authentication),
    url(r'^providers/$', views.providers),
    url(r'^images/$', views.images),

    url(r'^aws/.*$', aws.initial),
    url(r'^accounts/', include('allauth.urls')),
]
