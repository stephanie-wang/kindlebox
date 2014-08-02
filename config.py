import os


DEBUG = os.getenv('DEBUG') is not None

### Default settings ###
# TODO: add csrf protection to user info form
CSRF_ENABLED = True

SECRET_KEY = ''

#SQLALCHEMY_DATABASE_URI = 'sqlite:////tmp/kindlebox.db'
if DEBUG:
    SQLALCHEMY_DATABASE_URI = 'postgres://sxwang@localhost/kindlebox'
else:
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', '')


REDIS_QUEUE_KEY = 'dropbox_delta_ids'

DROPBOX_APP_KEY = ''
DROPBOX_APP_SECRET = ''

EMAILER_ADDRESS = ''
EMAILER_PASSWORD = ''
