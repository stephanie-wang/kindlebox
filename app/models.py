from app import db
from app.utils import get_random_string


class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    dropbox_id = db.Column(db.Integer)
    kindle_name = db.Column(db.String(80), unique=True)
    # TODO: delete email.
    email = db.Column(db.String(120), unique=True)
    emailer = db.Column(db.String(120), unique=True)
    active = db.Column(db.Boolean)
    access_token = db.Column(db.Text)
    cursor = db.Column(db.Text)
    books = db.relationship('Book', backref='user', lazy='dynamic')

    def __init__(self, dropbox_id):
        self.dropbox_id = dropbox_id

    def activate(self):
        self.active = True

    def set_new_emailer(self):
        random_base = get_random_string()
        emailer_address = 'kindleboxed+%s@gmail.com' % random_base
        self.emailer = emailer_address


class Book(db.Model):
    __tablename__ = 'book'
    id = db.Column(db.Integer, primary_key=True)
    book_hash = db.Column(db.Integer)
    pathname = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    def __init__(self, user_id, pathname, book_hash):
        self.user_id = user_id
        self.pathname = pathname
        self.book_hash = book_hash
