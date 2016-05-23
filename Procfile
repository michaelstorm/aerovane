web: newrelic-admin run-program librato-launch --config-path librato-conf.json gunicorn --statsd-host=127.0.0.1:8142 multicloud.wsgi --log-file -
default_tasks: newrelic-admin run-program librato-launch --config-path librato-conf.json celery -A multicloud.celery worker --concurrency 4 -B -l info -Q default
load_public_provider_data_tasks: newrelic-admin run-program librato-launch --config-path librato-conf.json celery -A multicloud.celery worker --concurrency 1 -l info -Q load_public_provider_data,default
