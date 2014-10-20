web: gunicorn app:app --log-file=-
worker: celery worker --app=app.celery -l info
