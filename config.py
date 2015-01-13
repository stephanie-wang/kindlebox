import os


### Environments ###
# Configs for env DEV or PROD should be put in '<env>_config.py'
# Default to debug and dev true, prod false. Otherwise, debug and dev false,
# prod true.
DEBUG = os.getenv('DEBUG', True)
DEV = os.getenv('DEV', DEBUG)
PROD = os.getenv('PROD', not DEV)
if PROD:
    DEBUG = False
    DEV = False


### Default settings ###
APP_URL = 'http://localhost:5000'

# TODO: add csrf protection to user info form
CSRF_ENABLED = True

SECRET_KEY = ''

SQLALCHEMY_DATABASE_URI = 'postgres://sxwang@localhost/kindlebox'

REDIS_URI = 'redis://localhost:6379'
REDIS_QUEUE_KEY = 'dropbox_delta_ids'

CELERY_BROKER_URL = 'amqp://guest:guest@localhost//'

DROPBOX_APP_KEY = ''
DROPBOX_APP_SECRET = ''

# Kindlebox emailer settings. Emailer cookie is used to register each new
# emailer with Gmail's "Send mail as" endpoint.
EMAILER_ADDRESS = ''
EMAILER_PASSWORD = ''
EMAILER_COOKIE = ''


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
