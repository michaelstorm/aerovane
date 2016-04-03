#!/bin/bash -x
sudo su postgres -c 'psql -c "drop database aerovane;"'
sudo su postgres -c 'psql -c "create database aerovane;"'
sudo su postgres -c 'psql -c "grant all privileges on database aerovane to postgres;"'

python manage.py migrate auth
python manage.py migrate

echo "User.objects.create_superuser('oopsdude', email='oopsdude@gmail.com', password='password')" | python manage.py shell_plus

echo "Ec2ProviderConfiguration.create_regions(
			user=User.objects.first(),
			access_key_id='$AWS_ACCESS_KEY_ID',
			secret_access_key='$AWS_SECRET_ACCESS_KEY')" | python manage.py shell_plus

#echo "Provider.objects.create(
#			name='linode',
#			pretty_name='Linode',
#			icon_path='/static/stratosphere/aws_icon.png')" | python manage.py shell_plus

#echo "LinodeProviderConfiguration.objects.create(
#			provider=Provider.objects.get(name='linode'),
#			provider_name='linode',
#			user_configuration=User.objects.first().configuration,
#			api_key='$LINODE_API_KEY')" | python manage.py shell_plus

#echo "LinodeProviderConfiguration.objects.first().load_available_images()" | python manage.py shell_plus

echo "[pc.load_data(False) for pc in ProviderConfiguration.objects.all()]" | python manage.py shell_plus

echo "KeyAuthenticationMethod.objects.create(
	name='Production deployment key',
	user_configuration=UserConfiguration.objects.first(),
	key='ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQDB0Yuu7wkwA/Dv9/D33oncSsicZcJoVcn7rbqrC6pLg1v6fso9hmM5735miW57ZeOS6VtUFJT3as+qvoR0SYMTAP69ohTuIlLBrHa8NoMxh8AYrYZi3HGt6vIZb4flA51pLjzeojb8ifT+KwfESU47LzBMauJekhqiTqFROobbMVi+CKSkoKUWXmxwYDWC0g4CYfUKdkgyt+VrRmt150EjAn7vig0vsNFSrI+QEnyaCnuFL4Y8lLU3UdR30P/We8wcELSs9ebPgc165K3MlKX1xHxQCHAoibqyk6rNlyL8D9UuyJZuAIfaRi/Iww+b1i2noxa6Vf9EI8BLdh3V3vnti5OK2OHDGEfG+4mIZ6tnKJ1FUZ9IZ05iC75cGnd6i5Wjynf8K/Gx+DA0ywsALL3AfDgWeIv3Y+bpXpiXuqvdDRx8MiN5OdnH+exFTh6KSPii67CdjHwdjF4wou9Wcl4v8YLU3q6lWmiDUKKC4kTNsbHh0He2L8zYM0LgXXreULp0Hj+M7qf98uGTpFcOHL5b6TebZl5hClO5H3zfLpEcQJ44lnoqoGhiKrtSf9WGfIKSp8K70/t+QfXZ7vclg14Z0+ZS/BKfonSortS8907FUO5ZIpTfGo9x/ZYHcEOCZXwzSEhyg6NsGV0k6sl3e+aFvPmnYatZ/NrdaoK50rJj1Q== michael@michael-Lenovo-B575')" | python manage.py shell_plus
