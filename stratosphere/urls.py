from django.conf.urls import url, include

from . import views

urlpatterns = [
    url(r'^$', views.index),
    url(r'^compute/$', views.compute),
    url(r'^compute/(?P<group_id>\w+)/$', views.compute),
    url(r'^check_configure/$', views.check_configure),
    url(r'^settings/$', views.settings),
    url(r'^deployment_scripts/$', views.deployment_scripts),
    url(r'^deployment_scripts/(?P<script_id>\w+)/$', views.deployment_scripts),
    url(r'^authentication_methods/$', views.authentication_methods),
    url(r'^authentication_methods/(?P<method_id>\w+)/$', views.authentication_methods),
    url(r'^settings/(?P<provider_name>\w+)/$', views.configure_provider),
    url(r'^provider/(?P<provider_name>\w+)/(?P<action>\w+)/$', views.provider_action),
    url(r'^accounts/', include('allauth.urls')),
]
