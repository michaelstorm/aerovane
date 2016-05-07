#1/bin/bash -e
python manage.py collectstatic
./bin/post_compile
