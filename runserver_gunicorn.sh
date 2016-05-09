# run with gunicorn in order to use WhiteNoise (in wsgi.py) to serve static assets
gunicorn multicloud.wsgi --log-file -
