from flask import jsonify, redirect, session, url_for
from functools import wraps


def login_required_ajax(f):
    """
    Redirects to home if not logged in. Functions decorated
    with login_required_ajax must have dropbox_id as first arg.
    """
    @wraps(f)
    def login_required_f(*args, **kwargs):
        dropbox_id = session.get('dropbox_id')
        if dropbox_id is None:
            return jsonify({
                'success': False,
                })
        return f(dropbox_id, *args, **kwargs)
    return login_required_f
