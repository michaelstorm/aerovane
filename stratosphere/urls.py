from django.conf.urls import url, include
from django.views.generic.base import RedirectView

from . import views, aws
# from .modelviews.password_authentication_method.new import NewPasswordAuthenticationMethodView

urlpatterns = [
    url(r'^$', views.dashboard),
    url(r'^operating_system/$', views.operating_systems),
    url(r'^compute/$', views.compute),
    url(r'^compute/(?P<group_id>[0-9a-f\-]+)/$', views.compute),
    url(r'^compute/state_history/$', views.state_history),
    url(r'^compute/state_history/(?P<group_id>[0-9a-f\-]+)/$', views.state_history),
    url(r'^authentication_methods/$', views.authentication_methods),
    url(r'^authentication_methods/(?P<method_id>[0-9a-f\-]+)/$', views.authentication_methods),
    url(r'^providers/loaded/$', views.providers_loaded),
    url(r'^providers/refresh/$', views.providers_refresh),
    url(r'^providers/$', views.get_providers),
    url(r'^providers/(?P<provider_id>[0-9a-f\-]+)/$', views.get_providers),
    url(r'^providers/(?P<provider_id>[0-9a-f\-]+)/enabled/$', views.set_provider_enabled),
    url(r'^providers/(?P<provider_name>\w+)/$', views.configure_provider),
    url(r'^providers/(?P<provider_id>[0-9a-f\-]+)/disk_images/$', views.provider_disk_images),

    url(r'^compute_groups/$', views.compute_groups),
    url(r'^compute_groups/add/$', views.add_compute_group),
    url(r'^compute_groups/(?P<group_id>[0-9a-f\-]+)/$', views.compute_group),
    url(r'^check_configure/$', views.check_configure),
    url(r'^authentication/$', views.authentication),
    url(r'^images/$', views.images),

    url(r'^aws/.*$', aws.initial),
    url(r'^accounts/', include('allauth.urls')),

    url(r'^\.well-known/acme-challenge/Pyb4_9N05Q1hpcTwJuH5gfkyH44kRyvEEnHBujr_Qpc$', views.letsencrypt_challenge),
]
