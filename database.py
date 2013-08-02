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
	def __init__(self, app = None):
		self.app = app
		self.db = self.get_db()

	def get_db(self, debug = True):
		"""
		Opens a new database connection if there is none yet for the current application context.
		"""
		if debug:
			return self.get_db_debug()
		top = _app_ctx_stack.top
		if not hasattr(top, 'sqlite_db'):
			sqlite_db = sqlite3.connect(os.path.join(self.app.instance_path, self.app.config['DATABASE']))
			sqlite_db.row_factory = sqlite3.Row
			top.sqlite_db = sqlite_db

		return top.sqlite_db

	def get_db_debug(self):
		"""
		just a database connection instantiator for ipython
		"""
		sqlite_db = sqlite3.connect('instance/myapp.db')
		sqlite_db.row_factory = sqlite3.Row
		return sqlite_db


	def write(self, command, data):
		db = self.get_db()
		print 'WRITING', command
		db.execute(command, data)
		db.commit()

	def readRow(self, command, data):
		db = self.get_db()
		row = db.execute(command, data).fetchone()
		if row is None:
			return None
		return row[0]

	def get_books_from_db(self, username):
		db = self.get_db()
		books = db.execute('''SELECT b.pathname 
			FROM users u 
			INNER JOIN books b ON u.id = b.id
			WHERE u.kindle_name = ?
			''', [username]).fetchall()
		return [book[0] for book in books]

	def save_books(self, username, books):
		""" this only enters new books in. no hashes are saved.
		Returns book_id of each book saved """
		
		db = self.get_db()
		user_id = db.execute('SELECT id FROM users WHERE kindle_name = ?', [username]).fetchone()
		if user_id is None:
			return None
		user_id = user_id[0]
		book_ids = []
		# TODO: replace this later with executemany
		for book in books:
			result = db.execute('INSERT INTO books (id, pathname) VALUES (?, ?)', [user_id, book])
			book_ids.append(result.lastrowid)
		db.commit()
		return book_ids

	def save_book_hashes(self, book_ids, hashes):
		db = self.get_db()
		# TODO: replace this later with executemany
		# TODO: check if book row not there
		for i in range(len(book_ids)):
			db.execute('UPDATE books SET book_contents = ? WHERE book_id = ?', [hashes[i], book_ids[i]])
		db.commit()

	def delete_books(self, username, books):
		db = self.get_db()
		user_id = db.execute('SELECT id FROM users WHERE kindle_name = ?', [username]).fetchone()
		if user_id is None:
			return None
		user_id = user_id[0]
		# TODO: replace this later with executemany
		for book in books:
			db.execute('DELETE FROM books WHERE id = ? AND pathname = ?', [user_id, book])
			print "deleted " + book
		db.commit()

	def check_file_rename(self):
		# TODO: check if file was renamed
		return None

	def get_emailer(self, username):
		return self.readRow('SELECT emailer FROM users kindle_name = ?', [username])