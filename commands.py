import logging
import time
import os

from dropbox.client import DropboxClient
from flask.ext.script import Command
from flask.ext.script import Option

from app import app
from app import db
from app import emailer
from app import filesystem
from app.kindleboxer import kindlebox
from app.kindleboxer import send_books
from app.kindleboxer import acquire_kindlebox_lock
from app.kindleboxer import acquire_send_books_lock
from app.models import User
from app.models import Book
from app.models import KindleName


log = logging.getLogger()


class CeleryTasksCommand(Command):
    """
    Sets off the `kindlebox` celery task for all active users, which resends
    any unsent books.
    """
    def run(self):
        # Kindleboxing active users.
        active_users = User.query.filter_by(active=True).all()
        log.info("Kindleboxing {0} active users...".format(len(active_users)))
        for user in active_users:
            kindlebox.delay(user.dropbox_id)


class ResetUserCommand(Command):
    """
    Resets a user's Dropbox delta cursor to nothing and deletes all the books
    that they already own. Should be used if user has just signed up but
    doesn't receive any books that they added.
    """
    option_list = (
            Option('--user-id', '-u', dest='user_id'),
            )

    def run(self, user_id):
        user = User.query.filter_by(id=user_id).first()
        if user is None:
            print "User doesn't exist"
            return
        user.cursor = None
        user.books.delete()
        db.session.commit()


class StatsCommand(Command):
    """
    Get some stats on number of users, books, etc.
    """
    def run(self):
        active_user_count = User.query.filter_by(active=True).count()
        total_user_count = User.query.count()
        print ("{num_active} active users out of {num_total} "
               "total".format(num_active=active_user_count, num_total=total_user_count))

        unsent_book_count = Book.query.filter_by(unsent=True).count()
        total_book_count = Book.query.count()
        print ("{num_unsent} unsent books out of {num_total} "
               "total".format(num_unsent=unsent_book_count, num_total=total_book_count))


class SeedEmailsCommand(Command):
    """
    Fill in all Dropbox emails.
    """
    def run(self):
        users = User.query.all()
        for user in users:
            if user.email is not None:
                continue
            client = DropboxClient(user.access_token)
            try:
                info = client.account_info()
            except:
                continue
            user.email = info.get('email')
            print user.id, user.email
        db.session.commit()


class SendRenameEmailsCommand(Command):
    def run(self):
        emails = [row[0] for row in db.session.query(User.email).filter_by(active=True).all()]
        with open('app/static/html/bookdrop_rename_email.html') as f:
            html = f.read()
            for email in emails:
                emailer.send_mail('mail@mail.kindlebox.me', ['mail@mail.kindlebox.me'], subject='Kindlebox is now BookDrop', html=html, bcc=[email])


class ClearTemporaryDirectoryCommand(Command):
    def run(self):
        tmp_directory = app.config.get('BASE_DIR', '')
        for user_id in os.listdir(tmp_directory):
            subdirectory = os.path.join(tmp_directory, user_id)
            if not os.path.isdir(subdirectory):
                log.error("Non-directory in base directory. Please delete before trying again.")
                return

            user = User.query.filter_by(id=user_id).first()
            if user is None:
                log.info("User {user_id} doesn't exist.".format(user_id=user_id))
                filesystem.clear_directory(subdirectory)
            else:
                kindlebox_lock = acquire_kindlebox_lock(user.dropbox_id, blocking=False)
                if kindlebox_lock is None:
                    continue

                send_books_lock = acquire_send_books_lock(user_id, blocking=False)
                if send_books_lock is None:
                    kindlebox_lock.release()
                    continue

                log.info("Clearing user directory id {user_id}.".format(user_id=user_id))
                filesystem.clear_directory(subdirectory)
                send_books_lock.release()
                kindlebox_lock.release()


class RewriteKindleNamesCommand(Command):
    """
    One-off script to convert all kindle names to kindle email addresses.
    """
    def run(self):
        for row in KindleName.query.all():
            row.kindle_name = row.kindle_name + '@kindle.com'
        db.session.commit()


class SendReactivateEmailsCommand(Command):
    def run(self):
        emails = set(row[0] for row in db.session.query(User.email).filter(User.id < 500).all())
        with open('app/static/html/bookdrop_reactivate.html') as f:
            html = f.read()
            for email in emails:
                print emailer.send_mail('mail@mail.getbookdrop.com', ['mail@mail.getbookdrop.com'], subject='Bookdrop relaunch', html=html, bcc=[email])
                time.sleep(0.1)
