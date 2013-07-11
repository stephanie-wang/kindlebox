# -*- coding: utf-8 -*-

import os
import posixpath
import constants
import database
from sqlite3 import dbapi2 as sqlite3
from flask import Flask, request, session, g, redirect, url_for, abort, \
     render_template, flash, _app_ctx_stack

from dropbox.client import DropboxClient, DropboxOAuth2Flow

# configuration
DEBUG = True
DATABASE = 'myapp.db'
SECRET_KEY = 'development key'

# Fill these in!
DROPBOX_APP_KEY = constants.DROPBOX_APP_KEY
DROPBOX_APP_SECRET = constants.DROPBOX_APP_SECRET

# create our little application :)
app = Flask(__name__)
app.config.from_object(__name__)
app.config.from_envvar('FLASKR_SETTINGS', silent=True)

# Ensure instance directory exists.
try:
    os.makedirs(app.instance_path)
except OSError:
    pass

db = None

def init_db():
    """Creates the database tables."""
    with app.app_context():
        global db
        db = database.Database(app)
        storage = db.get_db()
        with app.open_resource("schema.sql", mode="r") as f:
            storage.cursor().executescript(f.read())
        storage.commit()

@app.route('/')
def home():
    if 'user' not in session:
        return redirect(url_for('login'))
    access_token = get_access_token()
    real_name = None
    print(access_token)
    if access_token is not None:
        client = DropboxClient(access_token)
        account_info = client.account_info()
        real_name = account_info["display_name"]
        print db.get_books_from_dropbox(client)
        return render_template('index.html', real_name=db.get_books_from_dropbox(client))
    return render_template('index.html', real_name=real_name)


def get_access_token():
    username = session.get('user')
    if username is None:
        return None
    return db.readRow('SELECT access_token FROM users WHERE username = ?', [username])

@app.route('/dropbox-auth-finish')
def dropbox_auth_finish():
    username = session.get('user')
    if username is None:
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
    data = [access_token, username]
    db.write('UPDATE users SET access_token = ? WHERE username = ?', data)
    return redirect(url_for('home'))

@app.route('/dropbox-auth-start')
def dropbox_auth_start():
    if 'user' not in session:
        abort(403)
    return redirect(get_auth_flow().start())

@app.route('/dropbox-unlink')
def dropbox_unlink():
    username = session.get('user')
    if username is None:
        abort(403)
    db.write('UPDATE users SET access_token = NULL, folder = NULL, \
        email_address = NULL, active = 0 WHERE username = ?', [username])
    return redirect(url_for('home'))

def get_auth_flow():
    redirect_uri = url_for('dropbox_auth_finish', _external=True)
    return DropboxOAuth2Flow(DROPBOX_APP_KEY, DROPBOX_APP_SECRET, redirect_uri,
                                       session, 'dropbox-auth-csrf-token')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        folder = request.form['folder']
        if username:
            storage = db.get_db()
            storage.execute('INSERT OR IGNORE INTO users (username, email_address, active) \
                VALUES (?, ?, ?)', [username, username, 0])
            if folder:
                storage.execute('UPDATE users SET folder = ? WHERE username = ?', [folder, username])
            storage.commit()
            session['user'] = username
            flash('You were logged in')
            return redirect(url_for('home'))
        else:
            flash("You must provide a username")
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('You were logged out')
    return redirect(url_for('home'))


def main():
    init_db()
    app.run()

if __name__ == '__main__':
    main()
