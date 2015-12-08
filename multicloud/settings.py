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
DEBUG = True

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = (
    'annoying',
    'polymorphic',
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
    'storages',
    'stratosphere',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.github',
    'kombu.transport.django',
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
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'formatters': {
        'simple': {
            'format': '%(levelname)s %(name)s - %(message)s',
        },
    },
    'loggers': {
        '': {
            'handlers': ['console'],
            'level': os.getenv('LOG_LEVEL', 'DEBUG'),
        },
        'django': {
            'handlers': ['console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
        },
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

ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_SIGNUP_PASSWORD_VERIFICATION = False
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_USERNAME_REQUIRED = False

LOGIN_REDIRECT_URL = '/check_configure/'
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

default_db_config = dj_database_url.config(default='postgres://postgres:password@localhost:5432/aerovane')
db_options = default_db_config['OPTIONS'] if 'OPTIONS' in default_db_config else {}
db_options['isolation_level'] = psycopg2.extensions.ISOLATION_LEVEL_REPEATABLE_READ
default_db_config['OPTIONS'] = db_options

DATABASES = {
    'default': default_db_config
}

# Celery
BROKER_URL = 'django://'
CELERYD_HIJACK_ROOT_LOGGER = True
# CELERYBEAT_SCHEDULER = 'djcelery.schedulers.DatabaseScheduler'
# CELERYBEAT_SCHEDULE = {
#     'schedule-name': {
#         'task': 'stratosphere.tasks.update_instances_statuses',
#         'schedule': timedelta(seconds=30),
#     },
# }


# Internationalization
# https://docs.djangoproject.com/en/1.8/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.8/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(os.getcwd(), 'staticfiles')

STATICFILES_DIRS = (
   os.path.join(BASE_DIR, 'static'),
)

PROJECT_DIR = os.path.dirname(__file__)

DEFAULT_FILE_STORAGE = 'storages.backends.s3boto.S3BotoStorage'
STATICFILES_STORAGE = 'storages.backends.s3boto.S3BotoStorage'
AWS_STORAGE_BUCKET_NAME = 'stratospherecdn2'


# for whatever reason, saves us from a bunch of deprecation errors related to model loading
from stratosphere.models import ComputeInstance


SITE_ID = 2
