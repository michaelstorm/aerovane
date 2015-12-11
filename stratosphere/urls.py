from django.conf.urls import url, include

from . import views, aws_iam

urlpatterns = [
    url(r'^$', views.index),
    url(r'^compute/$', views.compute),
    url(r'^compute/(?P<group_id>\w+)/$', views.compute),
    url(r'^check_configure/$', views.check_configure),
    url(r'^authentication/$', views.authentication),
    url(r'^authentication_methods/$', views.authentication_methods),
    url(r'^authentication_methods/(?P<method_id>\w+)/$', views.authentication_methods),
    url(r'^providers/$', views.providers),
    url(r'^providers/(?P<provider_name>\w+)/$', views.configure_provider),
    url(r'^providers/(?P<provider_name>\w+)/(?P<action>\w+)/$', views.provider_action),
    url(r'^aws_iam$', aws_iam.initial),
    url(r'^accounts/', include('allauth.urls')),
]
