"""
Django settings for multicloud project.

Generated by 'django-admin startproject' using Django 1.8.6.

For more information on this file, see
https://docs.djangoproject.com/en/1.8/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.8/ref/settings/
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os
import dj_database_url
import psycopg2.extensions

from datetime import timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.8/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'r$&@my(i!cyx5v_1m21ii28yb771u+t)!%r++6&tdlx2=s5+_%'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'FALSE').upper() in ('YES', 'ON', 'TRUE', '1')

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')


# Application definition

INSTALLED_APPS = (
    'annoying',
    'bootstrap3',
    'django_admin_bootstrapped',
    'django_extensions',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.sites',
    'django.contrib.staticfiles',
    'polymorphic',
    'storages',
    'stratosphere',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.github',
    'kombu.transport.django',
    'simple_history',
    'compressor',
)

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware',
    'stratosphere.middleware.ssl_middleware.SSLMiddleware',
)

ROOT_URLCONF = 'multicloud.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False, # True
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        # 'file': {
        #     'level': 'DEBUG',
        #     'class': 'logging.FileHandler',
        #     'filename': 'log/debug.log',
        # },
    },
    'formatters': {
        'simple': {
            'format': '%(levelname)s %(name)s - %(message)s',
        },
    },
    'loggers': {
        '': {
            'handlers': ['console'], #, 'file'],
            'level': os.getenv('LOG_LEVEL', 'DEBUG'),
        },
        'django': {
            'handlers': ['console'], #, 'file'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
        },
        # 'django.db.backends': {
        #     'level': 'DEBUG',
        #     'handlers': ['console'],
        # },
    },
}

WSGI_APPLICATION = 'multicloud.wsgi.application'

APPEND_SLASH = False


AUTHENTICATION_BACKENDS = (
    # Needed to login by username in Django admin, regardless of `allauth`
    "django.contrib.auth.backends.ModelBackend",
    # `allauth` specific authentication methods, such as login by e-mail
    "allauth.account.auth_backends.AuthenticationBackend"
)

ACCOUNT_ADAPTER = 'stratosphere.lib.account_adapter.AccountAdapter'
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"
ACCOUNT_SIGNUP_FORM_CLASS = "stratosphere.forms.SignupForm"
ACCOUNT_SIGNUP_PASSWORD_VERIFICATION = False
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_USERNAME_REQUIRED = False

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
SOCIALACCOUNT_QUERY_EMAIL = True
SOCIALACCOUNT_PROVIDERS = {
    'github': {
        'SCOPE': ['email'],
        #'METHOD': 'js_sdk'  # instead of 'oauth2'
    }
}

EMAIL_BACKEND = 'django_mailgun.MailgunBackend'
MAILGUN_ACCESS_KEY = os.environ['MAILGUN_ACCESS_KEY']
MAILGUN_SERVER_NAME = os.environ['MAILGUN_SERVER_NAME']

DAB_FIELD_RENDERER = 'django_admin_bootstrapped.renderers.BootstrapFieldRenderer'

# Database
# https://docs.djangoproject.com/en/1.8/ref/settings/#databases

# from stratosphere.logging_connection import LoggingCursor

def create_db_config(isolation_level):
    db_config = dj_database_url.config(default='postgres://postgres:password@localhost:5432/aerovane')

    db_options = db_config['OPTIONS'] if 'OPTIONS' in db_config else {}
    db_options['isolation_level'] = isolation_level

    db_config['ENGINE'] = 'transaction_hooks.backends.postgresql_psycopg2'
    db_config['OPTIONS'] = db_options

    return db_config

serializable_db_config = create_db_config(psycopg2.extensions.ISOLATION_LEVEL_SERIALIZABLE)
read_committed_db_config = create_db_config(psycopg2.extensions.ISOLATION_LEVEL_READ_COMMITTED)

DATABASES = {
    'default': read_committed_db_config,
    'serializable': serializable_db_config
}

DATABASE_ROUTERS = ['stratosphere.settings_router.SettingsRouter']

# Celery
BROKER_URL = os.environ['CLOUDAMQP_URL']
CELERYD_HIJACK_ROOT_LOGGER = True
CELERY_IGNORE_RESULT = True
CELERY_DEFAULT_QUEUE = 'default'


# Internationalization
# https://docs.djangoproject.com/en/1.8/topics/i18n/

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.8/howto/static-files/

# Documenting here because I'll never remember how this works. django-staticfiles seems to provide
# the harness/pipeline for messing around with static files. `$ python manage.py collectstatic` picks up
# static files from stratosphere/static/ and plops them in multicloud/staticfiles/, which would make a difference
# if there were other apps whose assets would also be plopped there. For us, it copies them there because
# it just wants to help.
#
# django-compressor reads every asset referenced inside {% compress %}/{% endcompress %} blocks (probably from
# multicloud/staticfiles/, since we use `static` tags inside `compress` blocks and it doesn't choke on them),
# "compresses" them, and sticks the results in multicloud/staticfiles/. "Compressing" can be several operations,
# configurably, and seemingly dependent on which optional packages are installed. The one I most care about is
# concatenation, for now, and it's included by default. It then rewrites the HTML inside the `compress` blocks
# to reference the newly-created assets, so my guess is that it's definitely not safe to stick anything else in
# there.
#
# Finally, we serve the assets via WhiteNoise. WhiteNoise allows apps to serve static assets via WSGI, which is
# incredibly convenient, since we don't have to copy our assets anywhere or fiddle with nginx or Apache configs.
# It also allows a transparent CDN like Cloudflare to just pick up our assets, since it theoretically appends a
# cache-busting suffix to asset URLs. This seems to get swallowed when django-compressor is in use, though.
#
# Asset pipeline is:
# $ python manage.py collectstatic
# $ python manage.py compress
# $ python -m whitenoise.compress multicloud/staticfiles/
#
# Works both locally and on Heroku, with DEBUG on or off. Edge cases may differ, though -- django-compressor
# complains about missing assets in debug mode, but just elides them in production, IIRC. Interestingly, we
# seem to be able to omit `$ python manage.py collectstatic` if all assets are in `compress` blocks, but I like
# to include it for safety's sake. Also, Heroku does it by default.
#
# Speaking of Heroku, we trigger the latter two commands by sticking it them `bin/post_compile`, which is a
# special file that Heroku looks for.
#
# Running `whitenoise.compress` shouldn't be necessary, according to the docs, but (a) gzipped assets aren't
# served otherwise, and (b) it's not clear how gzipped assets were going to be compressed "live" anyhow. Took a
# bit of experimentation to figure that one out.

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'compressor.finders.CompressorFinder',
)

COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True


SITE_ID = int(os.environ.get('DJANGO_SITE_ID', '2'))
