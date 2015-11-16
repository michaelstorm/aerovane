from django.conf.urls import url, include

from . import views

urlpatterns = [
    url(r'^$', views.index),
    url(r'^compute/$', views.compute),
    url(r'^sync/$', views.sync),
    url(r'^check_configure/$', views.check_configure),
    url(r'^settings/$', views.settings),
    url(r'^configure/(?P<provider_name>\w+)/$', views.configure_provider),
    url(r'^accounts/', include('allauth.urls')),
]
