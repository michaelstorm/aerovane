#!/bin/bash -x
./celery_purge.sh

sudo su - postgres -c 'psql -c "drop database aerovane;"'
sudo su - postgres -c 'psql -c "create database aerovane;"'
sudo su - postgres -c 'psql -c "grant all privileges on database aerovane to postgres;"'

python manage.py migrate auth
python manage.py migrate

export CELERY_ALWAYS_EAGER=True

echo "s = Site.objects.first(); s.name = 'localhost'; s.domain = 'localhost:8000'; s.save()" | python manage.py shell_plus

echo "AWSProviderConfiguration.create_providers()" | python manage.py shell_plus

echo "AWSProviderConfiguration.create_regions(
			user=None,
			access_key_id='$AWS_ACCESS_KEY_ID',
			secret_access_key='$AWS_SECRET_ACCESS_KEY')" | python manage.py shell_plus
