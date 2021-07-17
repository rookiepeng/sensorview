#!/bin/sh

celery -A tasks worker --loglevel=info -P gevent &
gunicorn --timeout=600 --workers=5 --threads=2 -b 0.0.0.0:8000 app:server &