ps aux | grep python | grep celery | awk -p '{ print $2; }' | xargs kill
sleep 1
ps aux | grep python | grep celery | awk -p '{ print $2; }' | xargs kill -9
rm awkprof.out
