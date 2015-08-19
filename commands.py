from dropbox.client import DropboxClient
from flask.ext.script import Command
from flask.ext.script import Option

from app import db
from app import emailer
from app.kindleboxer import kindlebox
from app.kindleboxer import send_books
from app.models import User
from app.models import Book


class CeleryTasksCommand(Command):
    """
    Sets off the `kindlebox` celery task for all active users, which resends
    any unsent books.
    """
    def run(self, no_kindlebox, no_resend_books):
        # Kindleboxing active users.
        active_users = User.query.filter_by(active=True).all()
        print "Kindleboxing {0} active users...".format(len(active_users))
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
