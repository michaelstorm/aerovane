from django.conf import settings
from django.http import HttpResponseRedirect

import newrelic.agent


class NewRelicIgnoreAdminSiteMiddleware(object):
    def process_request(self, request):
        if request.path == '/admin' or request.path.startswith('/admin/'):
            newrelic.agent.ignore_transaction()


# from http://stackoverflow.com/a/9207726
class SSLMiddleware(object):
    def process_request(self, request):
        if not any([settings.DEBUG, request.is_secure(), request.META.get("HTTP_X_FORWARDED_PROTO", "") == 'https']):
            url = request.build_absolute_uri(request.get_full_path())
            secure_url = url.replace("http://", "https://")
            return HttpResponseRedirect(secure_url)