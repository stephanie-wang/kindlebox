# -*- coding: utf-8 -*-
# TODO: Make a link to get a new emailer.
# TODO: Allow reset of email address
# TODO: switch to postgres :(

import binascii
from dropbox.client import DropboxOAuth2Flow
from flask import Flask, request, session, redirect, url_for, abort, \
    render_template, flash
from flask.ext.sqlalchemy import SQLAlchemy
import os

import constants
import emailer


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
    emailer = db.Column(db.String(120), unique=True)
    active = db.Column(db.Boolean)
    access_token = db.Column(db.LargeBinary)
    delta_cursor = db.Column(db.Text)
    books = db.relationship('Book', backref='user', lazy='dynamic')

    def __init__(self, kindle_name, email):
        self.kindle_name = kindle_name
        self.email = email


class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book_hash = db.Column(db.Integer)
    pathname = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))


@app.route('/')
def home():
    if 'user' not in session:
        return redirect(url_for('login'))
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
                db.session.add(new_user)
                db.session.commit()
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
    db.session.commit()


@app.route('/new-emailer', methods=['POST'])
def new_emailer():
    if request.method == 'POST':
        kindle_name = request.form['kindle_name']
        refresh_emailer(kindle_name)


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
    user.emailer = refresh_emailer(kindle_name, user)

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
    for attribute in ['emailer', 'active', 'access_token', 'delta_cursor']:
        setattr(user, attribute, None)
    db.session.commit()

    return redirect(url_for('home'))


def refresh_emailer(kindle_name, user=None):
    if user is None:
        user = User.query.filter_by(kindle_name=kindle_name).first()
    random_base = get_random_string()
    emailer_address = 'kindleboxed+%s@gmail.com' % random_base
    emailer.send_mail(emailer_address, user.email, 'subscribe',
            SUBSCRIPTION_MESSAGE.format(emailer_address=emailer_address))

    user.emailer = emailer_address
    db.session.commit()


def get_auth_flow():
    redirect_uri = url_for('dropbox_auth_finish', _external=True)
    return DropboxOAuth2Flow(DROPBOX_APP_KEY, DROPBOX_APP_SECRET, redirect_uri,
            session, 'dropbox-auth-csrf-token')


def get_random_string(size=32):
    return binascii.b2a_hex(os.urandom(size))


def main():
    db.create_all()
    app.run()

if __name__ == '__main__':
    main()
