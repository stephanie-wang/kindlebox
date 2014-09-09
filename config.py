import os


### Environments ###
# Configs for env DEV or PROD should be put in '<env>_config.py'
DEBUG = os.getenv('DEBUG') is not None
DEV = os.getenv('DEV', DEBUG)
PROD = os.getenv('PROD', False)


### Default settings ###
APP_URL = 'http://localhost:5000'

# TODO: add csrf protection to user info form
CSRF_ENABLED = True

SECRET_KEY = ''

#SQLALCHEMY_DATABASE_URI = 'sqlite:////tmp/kindlebox.db'
SQLALCHEMY_DATABASE_URI = 'postgres://sxwang@localhost/kindlebox'

REDIS_URI = 'redis://localhost:6379'
REDIS_QUEUE_KEY = 'dropbox_delta_ids'

CELERY_BROKER_URL = 'amqp://guest:guest@localhost//'

DROPBOX_APP_KEY = ''
DROPBOX_APP_SECRET = ''

EMAILER_ADDRESS = ''
EMAILER_PASSWORD = ''


### Environment settings overrides ###
if DEV:
    try:
        from dev_config import *
    except ImportError:
        pass
elif PROD:
    try:
        from prod_config import *
    except ImportError:
        pass
