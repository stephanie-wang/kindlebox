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
	    user_id = db.execute('SELECT id FROM users WHERE kindle_name = ?', [username]).fetchone()
	    if user_id is None:
	        return []
	    books = db.execute('''SELECT pathname FROM books WHERE book_id in 
	    	(SELECT book_id FROM booksbyuser WHERE id = ?)''', user_id).fetchmany()
	    return books

	def save_books(self, username, book_mappings):
		""" this only enters new books in. no hashes are saved.
		Returns book_id of each book saved """

	    db = self.get_db()
	    user_id = db.execute('SELECT id FROM users WHERE kindle_name = ?', [username]).fetchone()
	    if user_id is None:
	        return None
	    user_id = user_id[0]
	    book_ids = []
	    # TODO: replace this later with executemany
	    for book_mapping in book_mappings:
	    	result = db.execute('INSERT INTO books (id, pathname, book_contents) VALUES (?, ?, ?)', 
	    		[user_id, book_mappings[0]])
	    	book_ids.append(result.lastrowid)
	  		db.execute('INSERT INTO booksbyuser (id, book_id) VALUES (?, ?)', [user_id, result.lastrowid])
	    db.commit()

	def save_book_hashes(self, book_ids, hashes):
		db = self.get_db()
		# TODO: replace this later with executemany
		for i in range(len(book_ids)):
			db.execute('UPDATE books SET book_contents = ? VALUES WHERE book_id = ?', [hashes[i], book_ids[i]])
		db.commit()


	def check_file_rename(self):
		# TODO: check if file was renamed
		return None
