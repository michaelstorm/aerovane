web: NEW_RELIC_CONFIG_FILE=newrelic.ini newrelic-admin run-program gunicorn multicloud.wsgi --log-file -
jobs: celery -A multicloud.celery worker -l info
scheduler: celery -A multicloud.celery beat -l info
