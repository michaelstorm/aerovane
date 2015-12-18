#!/bin/bash -x
sudo su postgres -c 'psql -c "drop database aerovane;"'
sudo su postgres -c 'psql -c "create database aerovane;"'
sudo su postgres -c 'psql -c "grant all privileges on database aerovane to postgres;"'

python manage.py migrate auth
python manage.py migrate

echo "User.objects.create_user('oopsdude', email='oopsdude@gmail.com', password='password')" | python manage.py shell_plus
echo "Ec2ProviderConfiguration.objects.create(provider_name='aws',
			user_configuration=User.objects.first().configuration,
			access_key_id='$AWS_ACCESS_KEY_ID',
			secret_access_key='$AWS_SECRET_ACCESS_KEY')" | python manage.py shell_plus
echo "LinodeProviderConfiguration.objects.create(provider_name='linode',
			user_configuration=User.objects.first().configuration,
			api_key='$LINODE_API_KEY')" | python manage.py shell_plus

echo "[pc.load_available_images() for pc in ProviderConfiguration.objects.all()]" | python manage.py shell_plus
echo "[pc.load_available_sizes() for pc in ProviderConfiguration.objects.all()]" | python manage.py shell_plus
