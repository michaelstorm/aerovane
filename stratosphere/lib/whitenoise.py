import os

from django.conf import settings

from whitenoise.django import DjangoWhiteNoise


class StratosphereWhiteNoise(DjangoWhiteNoise):
    def is_immutable_file(self, path, url):
        # keep all the path-checking goodness of the default implementation
        if super(StratosphereWhiteNoise, self).is_immutable_file(path, url):
            return True
        else:
            # It's kind of weird to determine whether a file is immutable based on its URL,
            # but it works. (I.e., we're comparing with STATIC_URL instead of STATIC_ROOT,
            # since STATIC_ROOT is an absolute path on the file system.)
            prefix = os.path.join(settings.STATIC_URL, settings.COMPRESS_OUTPUT_DIR)
            startswith = url.startswith(prefix)
            return startswith
