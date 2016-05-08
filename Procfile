web: newrelic-admin run-program librato-launch --config-path librato-conf.json gunicorn --statsd-host=127.0.0.1:8142 multicloud.wsgi --log-file -
jobs: newrelic-admin run-program librato-launch --config-path librato-conf.json celery -A multicloud.celery worker --concurrency 4 -B -l info
