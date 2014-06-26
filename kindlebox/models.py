from sqlalchemy import *
from sqlalchemy.orm import relationship
from kindlebox.database import Base

class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    kindle_name = Column(String(80), unique=True)
    email = Column(String(120), unique=True)
    emailer = Column(String(120), unique=True)
    active = Column(Boolean)
    access_token = Column(LargeBinary)
    delta_cursor = Column(Text)
    books = relationship('Book', backref='user', lazy='dynamic')

    def __init__(self, kindle_name, email):
        self.kindle_name = kindle_name
        self.email = email


class Book(Base):
    __tablename__ = 'book'
    id = Column(Integer, primary_key=True)
    book_hash = Column(Integer)
    pathname = Column(Text)
    user_id = Column(Integer, ForeignKey('user.id'))

    def __init__(self, pathname, user_id):
        self.pathname = pathname
        self.user_id = user_id
