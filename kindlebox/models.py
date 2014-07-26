from sqlalchemy import *
from sqlalchemy.orm import relationship


from kindlebox.database import Base
from kindlebox.utils import get_random_string


class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    dropbox_id = Column(Integer)
    kindle_name = Column(String(80), unique=True)
    # TODO: delete email.
    email = Column(String(120), unique=True)
    emailer = Column(String(120), unique=True)
    active = Column(Boolean)
    access_token = Column(Text)
    cursor = Column(Text)
    books = relationship('Book', backref='user', lazy='dynamic')

    def __init__(self, dropbox_id):
        self.dropbox_id = dropbox_id

    def activate(self):
        self.active = True

    def set_new_emailer(self):
        random_base = get_random_string()
        emailer_address = 'kindleboxed+%s@gmail.com' % random_base
        self.emailer = emailer_address


class Book(Base):
    __tablename__ = 'book'
    id = Column(Integer, primary_key=True)
    book_hash = Column(Integer)
    pathname = Column(Text)
    user_id = Column(Integer, ForeignKey('user.id'))

    def __init__(self, user_id, pathname, book_hash):
        self.user_id = user_id
        self.pathname = pathname
        self.book_hash = book_hash
