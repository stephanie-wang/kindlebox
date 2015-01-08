from functools import wraps

from flask import session

from app.models import User


def login_required_ajax(f):
    """
    Returns a JSON object with success false if there's no user logged in or no
    user registered with the session's dropbox ID. Functions decorated with
    login_required_ajax must have a models.User object as first arg.
    """
    @wraps(f)
    def login_required_f(*args, **kwargs):
        dropbox_id = session.get('dropbox_id')
        if dropbox_id is None:
            return jsonify({
                'success': False,
                })
        user = User.query.filter_by(dropbox_id=dropbox_id).first()
        if user is None:
            return jsonify({
                'success': False,
                })
        return f(user, *args, **kwargs)
    return login_required_f
