# -*- coding: utf-8 -*-
# TODO: Make a link to get a new emailer.
# TODO: Allow reset of email address
# TODO: switch to postgres :(

import binascii
import os
import posixpath
import constants
import database
import emailer
import hashlib
from flask import Flask, request, session, g, redirect, url_for, abort, \
    render_template, flash, _app_ctx_stack
from flask.ext.sqlalchemy import SQLAlchemy
from dropbox.client import DropboxClient, DropboxOAuth2Flow

# configuration
DEBUG = True
DATABASE = 'myapp.db'
SECRET_KEY = 'development key'
SUBSCRIPTION_MESSAGE = '''
Yay kindlebox.
Here's your email: {emailer_address}
'''

# Fill these in!
DROPBOX_APP_KEY = constants.DROPBOX_APP_KEY
DROPBOX_APP_SECRET = constants.DROPBOX_APP_SECRET

# create our little application :)
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/' + DATABASE
db = SQLAlchemy(app)

app.config.from_object(__name__)
app.config.from_envvar('FLASKR_SETTINGS', silent=True)

# Ensure instance directory exists.
try:
  os.makedirs(app.instance_path)
except OSError:
  pass

class User(db.Model):
  id = db.Column(db.Integer, primary_key=True) 
  kindle_name = db.Column(db.String(80), unique=True)
  email = db.Column(db.String(120), unique=True)
  access_token = db.Column(db.LargeBinary)
  emailer = db.Column(db.String(120), unique=True)
  active = db.Column(db.Boolean)
  delta_cursor = db.Column(db.Text)
  books = db.relationship('Book', backref='user', lazy='dynamic')

  def __init__(self, kindle_name, email):
    self.kindle_name = kindle_name
    self.email = email

class Book(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  book_hash = db.Column(db.Integer)
  pathname = db.Column(db.Text)

@app.route('/')
def home():
  if 'user' not in session:
    print 'not logged in'
    return redirect(url_for('login'))

  real_name = None
  access_token = get_access_token()
  print "access token is ", access_token

  # user not authorized
  if access_token is None:
    return render_template('index.html', real_name=real_name)

  client = DropboxClient(access_token)
  account_info = client.account_info()
  real_name = account_info['display_name']

  contents = get_delta(client)
  return render_template('index.html', real_name="You are logged in as " + real_name,
    folder_contents = contents)

@app.route('/activate')
def activate():
  if 'user' not in session:
    return redirect(url_for('login'))
  kindle_name = session.get('user')
  activate(kindle_name)


@app.route('/dropbox-auth-finish')
def dropbox_auth_finish():
  kindle_name = session.get('user')
  if kindle_name is None:
    abort(403)
  try:
    access_token, user_id, url_state = get_auth_flow().finish(request.args)
  except DropboxOAuth2Flow.BadRequestException, e:
    abort(400)
  except DropboxOAuth2Flow.BadStateException, e:
    abort(400)
  except DropboxOAuth2Flow.CsrfException, e:
    abort(403)
  except DropboxOAuth2Flow.NotApprovedException, e:
    flash('Not approved?  Why not, bro?')
    return redirect(url_for('home'))
  except DropboxOAuth2Flow.ProviderException, e:
    app.logger.exception("Auth error" + e)
    abort(403)

  random_base = get_random_string()
  emailer_address = 'kindleboxed+{base}@gmail.com'.format(base=random_base)
  user = User.query.filter_by(kindle_name=kindle_name).first()
  if user is None:
    # TODO: log error
    return
  emailer.send_mail(emailer_address, user.email, 'subscribe',
      SUBSCRIPTION_MESSAGE.format(emailer_address=emailer_address))

  user.access_token = access_token
  user.emailer = emailer_address
  db.session.commit()

  return redirect(url_for('home'))

@app.route('/dropbox-auth-start')
def dropbox_auth_start():
  if 'user' not in session:
    abort(403)
  return redirect(get_auth_flow().start())

@app.route('/dropbox-unlink')
def dropbox_unlink():
  kindle_name = session.get('user')
  if kindle_name is None:
    abort(403)
  db.write('UPDATE users SET access_token = NULL, \
    email = NULL, active = 0 WHERE kindle_name = ?', [kindle_name])
  return redirect(url_for('home'))

def get_auth_flow():
  redirect_uri = url_for('dropbox_auth_finish', _external=True)
  return DropboxOAuth2Flow(DROPBOX_APP_KEY, DROPBOX_APP_SECRET, redirect_uri,
                     session, 'dropbox-auth-csrf-token')

@app.route('/login', methods=['GET', 'POST'])
def login():
  error = None
  if request.method == 'POST':

    kindle_name = request.form['kindle_name']
    email = request.form['email']

    if kindle_name and email:
      session['user'] = kindle_name
      session['email'] = email
      # TODO: fix
      if db.is_active(kindle_name):
        return redirect(url_for('home'))
      else:
        new_user = User(kindle_name, email)
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('dropbox_auth_start'))
  return render_template('login.html', error=error)

@app.route('/logout')
def logout():
  session.pop('user', None)
  flash('You were logged out')
  return redirect(url_for('home'))

def get_access_token():
  kindle_name = session.get('user')
  if kindle_name is None:
    return None

def get_delta(client):
  kindle_name = session.get('user')
  if kindle_name is None:
    return None
  cursor = db.get_delta_cursor(kindle_name)
  delta = client.delta(cursor)
  
  # Get all entries that were added and are not a directory.
  booksToSave = filter(lambda entry: (not entry[1]['is_dir']) if entry[1] !=
      None else False, delta['entries'])
  books_saved = [ book[0] for book in booksToSave ]
  # Also filter by current books in case last save failed
  cur_books = db.get_books_from_db(kindle_name)
  books_saved = filter(lambda book: book not in cur_books, books_saved)
  # TODO: check books for file renames
  # TODO: check books for correct file extensions
  book_ids = db.save_books(kindle_name, books_saved)
  hashes = download_and_email_books(client, kindle_name, books_saved)
  # TODO: what happens if emailing fails midway through hashes? need some sort
  # of saved flag in database. should probably save books one at a time in case
  # of failure
  db.save_book_hashes(book_ids, hashes)
  
  booksToDelete = filter(lambda entry: entry[1] == None and len(entry[0].split('.')) > 1,
    delta['entries'])
  books_removed = [ book[0] for book in booksToDelete ]
  db.delete_books(kindle_name, books_removed)

  db.write('UPDATE users SET delta_cursor = ? WHERE kindle_name = ?', [delta['cursor'], kindle_name])
  return books_saved

def download_and_email_books(client, kindle_name, books):
  hashes = []
  md5 = hashlib.md5()

  email_from = db.get_emailer(kindle_name)
  email_to = kindle_name + '@kindle.com'

  for book in books:
    tmp_path = constants.LOCAL_FOLDER + book.split('/')[-1]
    with open(tmp_path, 'w') as tmp_book:
      with client.get_file(book) as book:
        data = book.read()
        tmp_book.write(data)
        md5.update(data)

    book_hash = md5.digest().decode("iso-8859-1")
    print "book hash is " + book_hash
    hashes.append(book_hash)

    # TODO: Error catching on the email?
    emailer.send_mail(email_from, email_to, 'convert','sending a book',
        [tmp_book])

    os.remove(tmp_path)
  return hashes

def get_random_string(size=32):
  return binascii.b2a_hex(os.urandom(size))


def main():
  db.create_all()
  app.run()

if __name__ == '__main__':
  main()
