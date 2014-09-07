# -*- coding: utf-8 -*-
import simplejson as json
import hashlib
import hmac

from dropbox.client import DropboxOAuth2Flow
from flask import request, session, redirect, url_for, abort, \
    render_template, flash, jsonify
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from app import app
from app import csrf
from app import db
from app.decorators import login_required_ajax
from app.decorators import crossdomain
from app.kindleboxer import kindlebox
from app.models import User


DEBUG = app.config.get('DEBUG', False)

DROPBOX_APP_KEY = app.config.get('DROPBOX_APP_KEY', '')
DROPBOX_APP_SECRET = app.config.get('DROPBOX_APP_SECRET', '')


@app.route('/start')
def splash():
    return render_template('splash.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/')
def home():
    dropbox_id = session.get('dropbox_id')
    if dropbox_id is None and not request.args.get('redirect'):
        return redirect(url_for('splash'))

    kindle_name = ''
    active = False
    emailer = ''

    user = User.query.filter_by(dropbox_id=dropbox_id).first()
    logged_in = dropbox_id is not None and user is not None
    if logged_in:
        kindle_name = user.kindle_name
        active = user.active
        emailer = user.emailer

    response = {
        'logged_in': logged_in,
        'kindle_name': kindle_name,
        'active': active,
        'emailer': emailer,
        'dropbox_id': dropbox_id,
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
    return redirect(url_for('home', redirect=True))


@app.route('/activate', methods=['POST'])
@crossdomain(origin=['https://www.amazon.com', app.config['APP_URL']])
@csrf.exempt
def activate_user():
    response = {
        'success': False,
        }
    try:
        data = request.data
        if data == '':
            data = request.form.get('data')
        data = json.loads(data)
        active = data.get('active')
        dropbox_id = data.get('dropbox_id')
        assert type(active) == bool
        assert type(dropbox_id) in {str, unicode}
    except (json.JSONDecodeError, AssertionError):
        return jsonify(response)

    user = User.query.filter_by(dropbox_id=dropbox_id).first()
    if user is None:
        return jsonify(response)

    user.activate(active)
    db.session.commit()
    response['success'] = True
    if active:
        try:
            kindlebox.delay(dropbox_id)
        except:
            return jsonify(response)
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

    if dropbox_id is None:
        # TODO: log?
        return redirect(url_for('home'))

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


@app.route('/dropbox-webhook', methods=['GET', 'POST'])
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


def get_auth_flow():
    if DEBUG:
        redirect_uri = url_for('dropbox_auth_finish', _external=True)
    else:
        redirect_uri = url_for('dropbox_auth_finish', _external=True,
                               _scheme="https")
    return DropboxOAuth2Flow(DROPBOX_APP_KEY, DROPBOX_APP_SECRET, redirect_uri,
                             session, 'dropbox-auth-csrf-token')
