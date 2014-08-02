# -*- coding: utf-8 -*-
from app import app
from app import db

import simplejson as json
import hashlib
import hmac

from dropbox.client import DropboxOAuth2Flow
from flask import request, session, redirect, url_for, abort, \
    render_template, flash, jsonify
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from app.decorators import login_required_ajax
from app.kindleboxer import process_user
from app.models import User


DEBUG = app.config.get('DEBUG', False)

DROPBOX_APP_KEY = app.config.get('DROPBOX_APP_KEY', '')
DROPBOX_APP_SECRET = app.config.get('DROPBOX_APP_SECRET', '')


@app.route('/')
def home():
    dropbox_id = session.get('dropbox_id')
    user = User.query.filter_by(dropbox_id=dropbox_id).first()

    logged_in = dropbox_id is not None and user is not None
    kindle_name = ''
    email = ''
    active = False
    emailer = ''
    if logged_in:
        kindle_name = user.kindle_name
        email = user.email
        active = user.active
        emailer = user.emailer

    response = {
        'logged_in': logged_in,
        'kindle_name': kindle_name,
        'email': email,
        'active': active,
        'emailer': emailer,
        }
    return render_template('index.html', **response)


@app.route('/set-user-info', methods=['POST'])
@login_required_ajax
def set_user_info(dropbox_id):
    response = {
        'success': False,
        }

    user = User.query.filter_by(dropbox_id=dropbox_id).first()
    kindle_name = request.form.get('kindle_name')

    if kindle_name is not None:
        if user.kindle_name is None:
            user.set_new_emailer()
        user.kindle_name = kindle_name
        db.session.commit()
        response['success'] = True
        response['emailer'] = user.emailer

    return jsonify(response)


@app.route('/login')
def login():
    # _logout()
    return redirect(get_auth_flow().start())


def _logout():
    # TODO: clear any other session args
    session.pop('dropbox_id', None)


@app.route('/logout')
def logout():
    _logout()
    return redirect(url_for('home'))


@app.route('/activate', methods=['POST'])
@login_required_ajax
def activate_user(dropbox_id):
    response = {
        'success': False,
        }

    try:
        user = User.query.filter_by(dropbox_id=dropbox_id).one()
    except (NoResultFound, MultipleResultsFound):
        # TODO: log
        return jsonify(response)

    try:
        _process_user(user.dropbox_id)
    except:
        # TODO: log
        return jsonify(response)

    user.activate()
    db.session.commit()
    response['success'] = True
    return jsonify(response)


@app.route('/dropbox-auth-finish')
def dropbox_auth_finish():
    """
    Finish Dropbox auth. If successful, user is now logged in. If the dropbox
    ID is new, register a new user.
    """
    try:
        access_token, dropbox_id, url_state = (get_auth_flow().
                                               finish(request.args))
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

    user = User.query.filter_by(dropbox_id=dropbox_id).first()
    if user is None:
        user = User(dropbox_id)
        db.session.add(user)

    user.access_token = access_token
    db.session.commit()

    session['dropbox_id'] = user.dropbox_id

    return redirect(url_for('home'))


@app.route('/dropbox-unlink')
def dropbox_unlink():
    dropbox_id = session.get('dropbox_id')
    if dropbox_id is None:
        abort(403)

    user = User.query.filter_by(dropbox_id=dropbox_id).first()
    for attribute in ['active', 'access_token', 'cursor']:
        setattr(user, attribute, None)
    db.session.commit()

    _logout()

    return redirect(url_for('home'))


@app.route('/dropbox-webhook', methods=['GET'])
def verify():
    if request.method != 'POST':
        return request.args.get('challenge')
    signature = request.headers.get('X-Dropbox-Signature')
    if signature != hmac.new(DROPBOX_APP_SECRET, request.data,
                             hashlib.sha256).hexdigest():
        abort(403)

    for dropbox_id in json.loads(request.data)['delta']['users']:
        _process_user.delay(dropbox_id)

    return ''


def _process_user(dropbox_id):
    process_user.delay(dropbox_id)


def get_auth_flow():
    if DEBUG:
        redirect_uri = url_for('dropbox_auth_finish', _external=True)
    else:
        redirect_uri = url_for('dropbox_auth_finish', _external=True,
                               _scheme="https")
    return DropboxOAuth2Flow(DROPBOX_APP_KEY, DROPBOX_APP_SECRET, redirect_uri,
                             session, 'dropbox-auth-csrf-token')
