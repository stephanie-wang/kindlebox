# -*- coding: utf-8 -*-
import simplejson as json
import hashlib
import hmac

from dropbox.client import DropboxClient
from dropbox.client import DropboxOAuth2Flow
from flask import request
from flask import session
from flask import redirect
from flask import url_for
from flask import abort
from flask import render_template
from flask import flash
from flask import jsonify
from validate_email import validate_email

from app import analytics
from app import app
from app import csrf
from app import db
from app.decorators import login_required_ajax
from app.kindleboxer import kindlebox
from app.kindleboxer import upload_welcome_pdf
from app.models import User
from app.models import KindleName


DEBUG = app.config.get('DEBUG', False)

DROPBOX_APP_KEY = app.config.get('DROPBOX_APP_KEY', '')
DROPBOX_APP_SECRET = app.config.get('DROPBOX_APP_SECRET', '')


@app.errorhandler(404)
def page_not_found(e):
    return render_kindlebox_template('error.html'), 404


@app.errorhandler(400)
def error(e):
    return render_kindlebox_template('error.html'), 400


@app.route('/start')
def splash():
    return render_kindlebox_template('splash.html')


@app.route('/about')
def about():
    return render_kindlebox_template('about.html')


@app.route('/')
def home():
    dropbox_id = session.get('dropbox_id')
    if dropbox_id is None and not request.args.get('redirect'):
        return redirect(url_for('splash'))

    if request.MOBILE:
        return render_kindlebox_template('mobile/index.html')

    # Use a blank user if no one's logged in.
    user = User.query.filter_by(dropbox_id=dropbox_id).first()
    if user is None:
        user = User(dropbox_id)

    response = {
        'added_bookmarklet': user.added_bookmarklet,
        'active': user.active,
        'emailer': user.emailer,
        'app_url': app.config['APP_URL'],
        'mobile': request.MOBILE,
        }

    return render_kindlebox_template('index.html', **response)


@app.route('/added-bookmarklet', methods=['POST'])
@login_required_ajax
def added_bookmarklet(user):
    user.set_added_bookmarklet()
    db.session.commit()

    return jsonify({
        'success': True,
        })


def _logout():
    # TODO: clear any other session args
    session.pop('dropbox_id', None)


@app.route('/login')
def login():
    # _logout()
    return redirect(get_auth_flow().start())


@app.route('/logout')
def logout():
    _logout()
    return redirect(url_for('home', redirect=True))


def validate_kindle_name(kindle_name):
    # Check for duplicates? Might end up blocking real users...
    kindle_name = kindle_name.lower()

    if kindle_name.endswith('@free.kindle.com'):
        kindle_name = kindle_name[:-len('@free.kindle.com')] + '@kindle.com'

    # We could use pyDNS here to check for an SMTP server, but we're filtering
    # by @kindle.com anyway.
    if kindle_name.endswith('@kindle.com') and validate_email(kindle_name):
        return kindle_name[:-len('@kindle.com')]

    return None


@app.route('/activate', methods=['POST'])
def activate():
    dropbox_id = session.get('dropbox_id')
    if dropbox_id is None:
        abort(400)

    user = User.query.filter_by(dropbox_id=dropbox_id).first()
    if user is None:
        abort(400)

    if not user.active:
        if 'kindle_names' not in request.form:
            abort(400)

        # Add all the Kindle usernames.
        form_kindle_names = request.form.get('kindle_names')
        try:
            kindle_names = json.loads(form_kindle_names)
        except json.JSONDecodeError:
            abort(400)

        if type(kindle_names) != list:
            abort(400)

        for kindle_name in kindle_names:
            kindle_name = validate_kindle_name(kindle_name)
            if kindle_name is None:
                continue
            kindle_name_row = KindleName(user.id, kindle_name)
            db.session.add(kindle_name_row)

        db.session.flush()
        # TODO: Return an error to the client
        if user.kindle_names.first() is None:
            abort(400)

        user.set_active(True)
        db.session.commit()

        try:
            upload_welcome_pdf.delay(user.dropbox_id)
        except:
            # TODO: Log
            pass

        analytics.track(str(user.id), 'Activated account')

    return redirect(url_for('home'))


@app.route('/deactivate', methods=['POST'])
@login_required_ajax
def deactivate(user):
    if user.active:
        user.kindle_names.delete()
    user.set_active(False)
    db.session.commit()

    analytics.track(str(user.id), 'Deactivated account')

    return jsonify({
            'success': True,
            })


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
    new_user = user is None
    if user is None:
        user = User(dropbox_id)
        # TODO: Log error
        error = register_gmail_emailer(user.set_new_emailer())
        db.session.add(user)

    user.access_token = access_token
    user.name = get_dropbox_name(access_token)
    db.session.commit()

    if new_user:
        analytics.track(str(user.id), 'Registered')
    analytics.track(str(user.id), 'Logged in')

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


@csrf.exempt
@app.route('/dropbox-webhook', methods=['GET', 'POST'])
def verify():
    if request.method != 'POST':
        return request.args.get('challenge', '')
    signature = request.headers.get('X-Dropbox-Signature')
    if signature != hmac.new(DROPBOX_APP_SECRET, request.data,
                             hashlib.sha256).hexdigest():
        abort(403)

    for dropbox_id in json.loads(request.data)['delta']['users']:
        kindlebox.delay(dropbox_id)

    return ''


def get_auth_flow():
    if DEBUG:
        redirect_uri = url_for('dropbox_auth_finish', _external=True)
    else:
        redirect_uri = url_for('dropbox_auth_finish', _external=True,
                               _scheme="https")
    return DropboxOAuth2Flow(DROPBOX_APP_KEY, DROPBOX_APP_SECRET, redirect_uri,
                             session, 'dropbox-auth-csrf-token')


def get_dropbox_name(access_token):
    client = DropboxClient(access_token)
    meta = client.account_info()
    return meta.get('display_name', '').split(' ')[0]

def register_gmail_emailer(emailer_base):
    import subprocess

    cookie = app.config.get('EMAILER_COOKIE', None)
    if cookie is None:
        return False
    emailer_arg = 'cfrp=1&cfss=&cfsp=587&cfsl=&cfsr=&cfn=Kindle+Box&cfa=kindleboxed%2B{emailer}%40gmail.com&cfia=on&cfrt='.format(emailer=emailer_base)

    request_args = ['curl',
         'https://mail.google.com/mail/?ui=2&ik=8ac11efc4f&view=cf&at=AF6bupOHMQUuohfutB0FBuEjaSTAw0TEzQ',
         '-H',
         'origin: https://mail.google.com',
         '-H',
         'accept-encoding: gzip,deflate',
         '-H',
         'accept-language: en-US,en;q=0.8',
         '-H',
         'user-agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36',
         '-H',
         'content-type: application/x-www-form-urlencoded',
         '-H',
         'accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
         '-H',
         'cache-control: max-age=0',
         '-H',
         'cookie: ' + cookie,
         '-H',
         'referer: https://mail.google.com/mail/?ui=2&ik=8ac11efc4f&view=cf&at=AF6bupOHMQUuohfutB0FBuEjaSTAw0TEzQ',
         '--data',
         emailer_arg,
         '--compressed']
    return subprocess.check_call(request_args) == 0


def get_logged_in_info():
    logged_in_info = {
            'logged_in': False,
            'name': '',
            }
    dropbox_id = session.get('dropbox_id')
    if dropbox_id is not None:
        user = User.query.filter_by(dropbox_id=dropbox_id).first()
        if user is not None:
            logged_in_info['logged_in'] = True
            logged_in_info['user_id'] = user.id
            logged_in_info['name'] = user.name

    return logged_in_info


def render_kindlebox_template(template, **args):
    args['dev'] = app.config.get('DEV', False)
    args.update(get_logged_in_info())
    return render_template(template, **args)
