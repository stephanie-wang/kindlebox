# -*- coding: utf-8 -*-

import os
import posixpath
import constants
import startapp

from sqlite3 import dbapi2 as sqlite3
from flask import Flask, request, session, g, redirect, url_for, abort, \
     render_template, flash, _app_ctx_stack

from dropbox.client import DropboxClient, DropboxOAuth2Flow

class Database:
	def __init__(self, app):
		self.app = app

	def get_db(self):
	    """
	    Opens a new database connection if there is none yet for the current application context.
	    """
	    top = _app_ctx_stack.top
	    if not hasattr(top, 'sqlite_db'):
	        sqlite_db = sqlite3.connect(os.path.join(self.app.instance_path, self.app.config['DATABASE']))
	        sqlite_db.row_factory = sqlite3.Row
	        top.sqlite_db = sqlite_db

	    return top.sqlite_db

	def write(self, command, data):
		db = self.get_db()
		db.execute(command, data)
		db.commit()

	def readRow(self, command, data):
		db = self.get_db()
		row = db.execute(command, data).fetchone()
		if row is None:
			return None
		return row[0]

	def get_folder(self):
	    username = session.get('user')
	    if username is None:
	        return None
	    db = self.get_db()
	    row = db.execute('SELECT folder FROM users WHERE username = ?', [username]).fetchone()
	    if row is None:
	        return None
	    return row[0]

	def get_books_from_db(self):
	    username = session.get('user')
	    if username is None:
	        return None
	    db = self.get_db()
	    user_id = db.execute('SELECT id FROM users WHERE username = ?', [username]).fetchone()
	    if user_id is None:
	        return None
	    user_id = user_id[0]
	    books = db.execute('SELECT pathname FROM users WHERE id = ?', [user_id])
	    return books

	def get_books_from_dropbox(self, client):
	    metadata = client.metadata(self.get_folder())
	    return [f['path'] for f in metadata['contents']]

	def set_books(self, pathnameMappings):
	    username = session.get('user')
	    if username is None:
	        return None
	    db = self.get_db()
	    user_id = db.execute('SELECT id FROM users WHERE username = ?', [username]).fetchone()
	    if user_id is None:
	        return None
	    user_id = user_id[0]
	    for mapping in pathnameMappings:
	        if db.execute('SELECT * FROM books WHERE book_id = ?', [mapping['book_id']]) == None:
	            db.execute('UPDATE books SET pathname = ? WHERE book_id = ?', [mapping['pathname'], mapping['book_id']])
	        else:
	            db.execute('INSERT INTO books (id, pathname) VALUES(?, ?)', [user_id, mapping['pathname']])
	    db.commit()
