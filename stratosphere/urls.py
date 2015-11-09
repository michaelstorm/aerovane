from django.conf.urls import url, include

from . import views

urlpatterns = [
    url(r'^$', views.index),
    url(r'^compute/$', views.compute),
    url(r'^sync/$', views.sync),
    url(r'^accounts/', include('allauth.urls')),
]
