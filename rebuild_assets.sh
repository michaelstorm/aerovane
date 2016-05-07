#1/bin/bash -e
python manage.py collectstatic --noinput --clear
./bin/post_compile
