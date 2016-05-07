web: newrelic-admin run-program librato-launch --config-path production-librato-conf.json gunicorn multicloud.wsgi --log-file -
jobs: newrelic-admin run-program librato-launch --config-path production-librato-conf.json celery -A multicloud.celery worker -l info
scheduler: celery -A multicloud.celery beat -l info
