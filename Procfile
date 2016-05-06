web: newrelic-admin run-program gunicorn multicloud.wsgi --log-file -
jobs: newrelic-admin run-program celery -A multicloud.celery worker -l info
scheduler: celery -A multicloud.celery beat -l info
