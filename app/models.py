from app import db
from app.utils import get_random_string


class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    dropbox_id = db.Column(db.Integer)
    name = db.Column(db.String(80))
    kindle_name = db.Column(db.String(80))
    emailer = db.Column(db.String(120), unique=True)
    added_bookmarklet = db.Column(db.Boolean)
    active = db.Column(db.Boolean)
    access_token = db.Column(db.Text)
    cursor = db.Column(db.Text)
    books = db.relationship('Book', backref='user', lazy='dynamic')

    def __init__(self, dropbox_id):
        self.dropbox_id = dropbox_id

    def activate(self, active):
        self.active = active

    def set_new_emailer(self):
        random_base = get_random_string()
        emailer_address = 'kindleboxed+%s@gmail.com' % random_base
        self.emailer = emailer_address
        return random_base

    def set_added_bookmarklet(self):
        self.added_bookmarklet = True


class Book(db.Model):
    __tablename__ = 'book'
    id = db.Column(db.Integer, primary_key=True)
    book_hash = db.Column(db.Text)
    pathname = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    def __init__(self, user_id, pathname, book_hash):
        self.user_id = user_id
        self.pathname = pathname
        self.book_hash = book_hash


class KindleName(db.Model):
    __tablename__ = 'kindle_name'
    id = db.Column(db.Integer, primary_key=True)
    kindle_name = db.Column(db.String(120))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    def __init__(self, user_id, kindle_name):
      self.user_id = user_id
      self.kindle_name = kindle_name
