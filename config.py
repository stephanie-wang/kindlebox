DEBUG = True

### Default settings ###
# TODO: add csrf protection to user info form
CSRF_ENABLED = True

SECRET_KEY = ''

#SQLALCHEMY_DATABASE_URI = 'sqlite:////tmp/kindlebox.db'
SQLALCHEMY_DATABASE_URI = 'postgres://sxwang@localhost/kindlebox'

DROPBOX_APP_KEY = ''
DROPBOX_APP_SECRET = ''

EMAILER_ADDRESS = ''
EMAILER_PASSWORD = ''
