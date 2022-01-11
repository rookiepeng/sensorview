START /b redis-server
SLEEP 2
START /b celery -A tasks worker --loglevel=info -P gevent
SLEEP 2
START /b waitress-serve --listen=*:8000 app:server