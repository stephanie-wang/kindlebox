# -*- coding: utf-8 -*-

import binascii
from dropbox.client import DropboxOAuth2Flow
from flask import Flask, request, session, redirect, url_for, abort, \
    render_template, flash
from flask.ext.sqlalchemy import SQLAlchemy
import hashlib
import hmac
import os

import constants
from kindlebox import emailer
from kindlebox.database import db
from kindlebox.models import User
from kindlebox.queue import SetQueue


DEBUG = True
SECRET_KEY = 'hello'
SUBSCRIPTION_MESSAGE = '''
Yay kindlebox.
Here's your email: {emailer_address}
'''

DROPBOX_APP_KEY = constants.DROPBOX_APP_KEY
DROPBOX_APP_SECRET = constants.DROPBOX_APP_SECRET

app = Flask(__name__)
app.config.from_object(__name__)
app.config.from_envvar('FLASKR_SETTINGS', silent=True)

# Ensure instance directory exists.
try:
    os.makedirs(app.instance_path)
except OSError:
    pass

users = SetQueue()


@app.route('/')
def home():
    if 'user' not in session:
        return redirect(url_for('login'))
    # TODO: Display option to link or unlink based on if user has an
    # access token set
    # TODO: Display option to activate if user has a token and an
    # emailer set
    # TODO: Link to get a new emailer
    # TODO: Form to reset email address
    return render_template('index.html', real_name=session['user'])


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        kindle_name = request.form['kindle_name']
        email = request.form['email']

        if kindle_name is not None and email is not None:
            session['user'] = kindle_name
            session['email'] = email
            user = User.query.filter_by(kindle_name=kindle_name).first()
            if user is not None:
                return redirect(url_for('home'))
            else:
                new_user = User(kindle_name, email)
                db.add(new_user)
                db.commit()
                return redirect(url_for('dropbox_auth_start'))
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('email', None)
    return redirect(url_for('home'))


@app.route('/activate')
def activate():
    if 'user' not in session:
        return redirect(url_for('login'))
    kindle_name = session.get('user')
    user = User.query.filter_by(kindle_name=kindle_name).first()
    user.active = True
    db.commit()


@app.route('/new-emailer', methods=['POST'])
def new_emailer():
    if request.method == 'POST':
        kindle_name = request.form['kindle_name']
        set_new_emailer(kindle_name)
        db.commit()

        emailer.send_mail(user.emailer, user.email, 'subscribe',
                SUBSCRIPTION_MESSAGE.format(emailer_address=emailer_address))


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
        flash('Not approved?    Why not, bro?')
        return redirect(url_for('home'))
    except DropboxOAuth2Flow.ProviderException, e:
        app.logger.exception("Auth error" + e)
        abort(403)

    user = User.query.filter_by(kindle_name=kindle_name).first()
    user.access_token = access_token
    user.user_id = user_id
    set_new_emailer(kindle_name, user)
    db.commit()

    emailer.send_mail(user.emailer, user.email, 'subscribe',
            SUBSCRIPTION_MESSAGE.format(emailer_address=emailer_address))

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
    user = User.query.filter_by(kindle_name=kindle_name).first()
    for attribute in ['active', 'access_token', 'delta_cursor']:
        setattr(user, attribute, None)
    db.commit()

    return redirect(url_for('home'))

@app.route('/dropbox-webhook', methods=['GET'])
def verify():
    if request.method != 'POST':
        return request.args.get('challenge') 
    # TODO: check this
    signature = request.headers.get('X-Dropbox-Signature')
    if signature != hmac.new(DROPBOX_APP_SECRET, request.data,
            hashlib.sha256).hexdigest():
        abort(403)

    for user_id in json.loads(request.data)['delta']['users']:
        users.add(user_id)

    return ''


def set_new_emailer(kindle_name, user=None):
    if user is None:
        user = User.query.filter_by(kindle_name=kindle_name).first()
    random_base = get_random_string()
    emailer_address = 'kindleboxed+%s@gmail.com' % random_base
    user.emailer = emailer_address


def get_auth_flow():
    redirect_uri = url_for('dropbox_auth_finish', _external=True)
    return DropboxOAuth2Flow(DROPBOX_APP_KEY, DROPBOX_APP_SECRET, redirect_uri,
            session, 'dropbox-auth-csrf-token')


def get_random_string(size=32):
    return binascii.b2a_hex(os.urandom(size))


def main():
    # TODO: start a thread to read from users queue
    from kindlebox.database import init_db
    init_db()
    app.run()

if __name__ == '__main__':
    main()
