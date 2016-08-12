#!/bin/bash -x
./celery_purge.sh

sudo su - postgres -c 'psql -c "drop database aerovane;"'
sudo su - postgres -c 'psql -c "create database aerovane;"'
sudo su - postgres -c 'psql -c "grant all privileges on database aerovane to postgres;"'

python manage.py migrate auth
python manage.py migrate

export CELERY_ALWAYS_EAGER=True

cat seed_db.py | python manage.py shell_plus
