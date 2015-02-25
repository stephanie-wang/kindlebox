from app import db
from app.kindleboxer import kindlebox
from app.kindleboxer import resend_books
from app.models import User
from app.models import Book

from flask.ext.script import Command
from flask.ext.script import Option


class CeleryTasksCommand(Command):
    """
    Sets off the `kindlebox` celery task for all active users and the
    `resend_books` celery task for all unsent books.
    """
    option_list = (
            Option('--no-kindlebox',
                   dest='no_kindlebox',
                   action='store_true',
                   help="Don't run the kindlebox task"),
            Option('--no-resend-books',
                   dest='no_resend_books',
                   action='store_true',
                   help="Don't run the resend books task"),
            )
    def run(self, no_kindlebox, no_resend_books):
        if not no_kindlebox:
            # Kindleboxing active users.
            active_users = User.query.filter_by(active=True).all()
            print "Kindleboxing {0} active users...".format(len(active_users))
            for user in active_users:
                kindlebox.delay(user.dropbox_id)

        if not no_resend_books:
            # Resending any unsent books.
            unsent_books = Book.query.filter_by(unsent=True).all()
            print "Resending {0} unsent books...".format(len(unsent_books))
            unsent_dropbox_ids = set(book.user.dropbox_id for book in unsent_books)
            for dropbox_id in unsent_dropbox_ids:
                resend_books.delay(dropbox_id)


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
