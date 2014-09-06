from datetime import timedelta
from flask import current_app, jsonify, make_response, redirect, request, \
    session, url_for
from functools import update_wrapper
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


# Snippet: http://flask.pocoo.org/snippets/56/
def crossdomain(origin=None, methods=None, headers=None,
                max_age=21600, attach_to_all=True,
                automatic_options=True):
    if methods is not None:
        methods = ', '.join(sorted(x.upper() for x in methods))
    if headers is not None and not isinstance(headers, basestring):
        headers = ', '.join(x.upper() for x in headers)
    if not isinstance(origin, basestring):
        origin = ', '.join(origin)
    if isinstance(max_age, timedelta):
        max_age = max_age.total_seconds()

    def get_methods():
        if methods is not None:
            return methods

        options_resp = current_app.make_default_options_response()
        return options_resp.headers['allow']

    def decorator(f):
        def wrapped_function(*args, **kwargs):
            if automatic_options and request.method == 'OPTIONS':
                resp = current_app.make_default_options_response()
            else:
                resp = {
                    'success': False,
                    }
                try:
                    resp = make_response(f(*args, **kwargs))
                except:
                    return jsonify(resp)
            if not attach_to_all and request.method != 'OPTIONS':
                return resp

            h = resp.headers

            h['Access-Control-Allow-Origin'] = origin
            h['Access-Control-Allow-Methods'] = get_methods()
            h['Access-Control-Max-Age'] = str(max_age)
            if headers is not None:
                h['Access-Control-Allow-Headers'] = headers
            return resp

        f.provide_automatic_options = False
        return update_wrapper(wrapped_function, f)
    return decorator
