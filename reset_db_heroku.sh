#!/bin/bash -xe
heroku pg:reset -a $1 DATABASE_URL --confirm $1
heroku run -a $1 python manage.py migrate auth
heroku run -a $1 python manage.py migrate

echo "s = Site.objects.first(); s.name = 'Production'; s.domain = 'dashboard.aerovane.io'; s.save(); exit()" | heroku run -a $1 python manage.py shell_plus

echo "Ec2ProviderConfiguration.create_providers(); exit()" | heroku run -a $1 python manage.py shell_plus

echo "Ec2ProviderConfiguration.create_regions(
			user_configuration=None,
			access_key_id='$AWS_ACCESS_KEY_ID',
			secret_access_key='$AWS_SECRET_ACCESS_KEY'); exit()" | heroku run -a $1 python manage.py shell_plus

#echo "[pc.load_data(True) for pc in ProviderConfiguration.objects.all()]; exit()" | heroku run -a $1 python manage.py shell_plus
