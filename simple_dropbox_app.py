# -*- coding: utf-8 -*-
"""
An example of Dropbox App linking with Flask.
"""

import os
import posixpath

from sqlite3 import dbapi2 as sqlite3
from flask import Flask, request, session, g, redirect, url_for, abort, \
     render_template, flash, _app_ctx_stack

from dropbox.client import DropboxClient, DropboxOAuth2Flow

# configuration
DEBUG = True
DATABASE = 'myapp.db'
SECRET_KEY = 'development key'

# Fill these in!
DROPBOX_APP_KEY = 'pbxn93iu6zgnjph'
DROPBOX_APP_SECRET = 'n12nugx1no97a3f'

# create our little application :)
app = Flask(__name__)
app.config.from_object(__name__)
app.config.from_envvar('FLASKR_SETTINGS', silent=True)

# Ensure instance directory exists.
try:
    os.makedirs(app.instance_path)
except OSError:
    pass

def init_db():
    """Creates the database tables."""
    with app.app_context():
        db = get_db()
        with app.open_resource("schema.sql", mode="r") as f:
            db.cursor().executescript(f.read())
        db.commit()


def get_db():
    """
    Opens a new database connection if there is none yet for the current application context.
    """
    top = _app_ctx_stack.top
    if not hasattr(top, 'sqlite_db'):
        sqlite_db = sqlite3.connect(os.path.join(app.instance_path, app.config['DATABASE']))
        sqlite_db.row_factory = sqlite3.Row
        top.sqlite_db = sqlite_db

    return top.sqlite_db

def get_access_token():
    username = session.get('user')
    if username is None:
        return None
    db = get_db()
    row = db.execute('SELECT access_token FROM users WHERE username = ?', [username]).fetchone()
    if row is None:
        return None
    return row[0]

def get_folder():
    username = session.get('user')
    if username is None:
        return None
    db = get_db()
    row = db.execute('SELECT folder FROM users WHERE username = ?', [username]).fetchone()
    if row is None:
        return None
    return row[0]

def get_books():
    username = session.get('user')
    if username is None:
        return None
    db = get_db()
    user_id = db.execute('SELECT id FROM users WHERE username = ?', [username]).fetchone()
    if user_id is None:
        return None
    user_id = user_id[0]
    books = db.execute('SELECT pathname FROM users WHERE id = ?', [user_id])
    return books

def get_books_from_dropbox(client):
    metadata = client.metadata(get_folder())
    return [f['path'] for f in metadata['contents']]

def set_books(pathnameMappings):
    username = session.get('user')
    if username is None:
        return None
    db = get_db()
    user_id = db.execute('SELECT id FROM users WHERE username = ?', [username]).fetchone()
    if user_id is None:
        return None
    user_id = user_id[0]
    for mapping in pathnameMappings:
        if db.execute('SELECT * FROM books WHERE book_id = ?', [mapping['book_id']]) == None:
            db.execute('UPDATE books SET pathname = ? WHERE book_id = ?', [mapping['pathname'], mapping['book_id']])
        else:
            db.execute('INSERT INTO books (id, pathname) VALUES(?, ?)', [user_id, mapping['pathname']])
    db.commit()


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
        return render_template('index.html', real_name=get_books_from_dropbox(client))
    return render_template('index.html', real_name=real_name)

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
    db = get_db()
    data = [access_token, username]
    db.execute('UPDATE users SET access_token = ? WHERE username = ?', data)
    db.commit()
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
    db = get_db()
    db.execute('UPDATE users SET access_token = NULL, folder = NULL WHERE username = ?', [username])
    db.commit()
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
            db = get_db()
            db.execute('INSERT OR IGNORE INTO users (username) VALUES (?)', [username])
            if folder:
                db.execute('UPDATE users SET folder = ? WHERE username = ?', [folder, username])
            db.commit()
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
