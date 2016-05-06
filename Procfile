web: gunicorn multicloud.wsgi --log-file -
jobs: celery -A multicloud.celery worker -l info
scheduler: celery -A multicloud.celery beat -l info
flower: celery -A multicloud.celery flower
