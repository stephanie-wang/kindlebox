from collections import namedtuple
import hashlib
import logging
import mimetypes
import os
import subprocess
import time

from dropbox.client import DropboxClient

from app import analytics
from app import celery
from app import db
from app import emailer
from app import redis
from app.models import User, Book


log = logging.getLogger()

# Lock expires in 30 minutes, in case there are lots of epubs to convert.
LOCK_EXPIRE = 60 * 30

BASE_DIR = '/tmp/kindlebox'
try:
    os.makedirs(BASE_DIR)
except OSError:
    pass

# And can only email 25 books at a time. Sendgrid only allows 20MB at a time,
# after encoding to email text, so more like 15.
ATTACHMENTS_LIMIT = 25
ATTACHMENTS_SIZE_LIMIT = 20 * (10**6)

# Supported filetypes.
# According to:
# http://www.amazon.com/gp/help/customer/display.html?nodeId=200375630
mimetypes.add_type('application/x-mobipocket-ebook', '.mobi')
mimetypes.add_type('application/x-mobipocket-ebook', '.prc')
mimetypes.add_type('application/vnd.amazon.ebook', '.azw')
mimetypes.add_type('application/vnd.amazon.ebook', '.azw1')

# Amazon doesn't support epub, but we do!
mimetypes.add_type('application/epub+zip', '.epub')
EPUB_MIMETYPE = 'application/epub+zip'

BOOK_MIMETYPES = {
    'application/epub+zip',
    'application/vnd.amazon.ebook',
    'text/plain',
    'application/x-mobipocket-ebook',
    'application/pdf',

    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/rtf',
    'text/html',

    'image/jpeg',
    'image/gif',
    'image/x-ms-bmp',
    'image/png',
    }
BOOK_CHUNK = 5


@celery.task(ignore_result=True)
def upload_welcome_pdf(dropbox_id):
    user = User.query.filter_by(dropbox_id=dropbox_id,
                                active=True).first()
    if user is None:
        return False

    # If we've already sent the welcome PDF before, Dropbox webhook went
    # trigger, so do it here.
    if user.uploaded_welcome_pdf:
        return kindlebox(dropbox_id)

    analytics.track(str(user.id), 'Sent welcome pdf')

    client = DropboxClient(user.access_token)
    try:
        with open('app/static/kindlebox_welcome.pdf', 'rb') as f:
            response = client.put_file('Welcome to Kindlebox.pdf', f)
            if response:
                log.info("Welcome PDF sent to user ID {0}.".format(user.id))
            else:
                raise Exception("No response received after sending welcome PDF")

        user.set_uploaded_welcome_pdf()
        db.session.commit()

    except:
        log.error(("Welcome PDF failed for user ID "
                   "{0}.").format(user.id), exc_info=True)
        return False

    return True


def _kindlebox(dropbox_id, user, client):
    delta = client.delta(user.cursor)

    # Process delta to get added and removed books. Also download any newly
    # added books and get the hashes.
    # `added_books` is a named tuple of ['pathname', 'book_hash', 'size'].
    added_books = get_added_books(delta['entries'], client, user.id)
    removed_books = get_removed_books(delta['entries'])
    log.debug("Delta contains {0} added books, {1} removed "
              "books".format(len(added_books), len(removed_books)))

    # If there are no more changes to process, update the cursor and we are
    # done.
    if len(added_books) == 0 and len(removed_books) == 0:
        user.cursor = delta['cursor']
        db.session.commit()
        return True

    # Remove deleted books before adding new ones to avoid deleting files where
    # only the content has changed.
    remove_books(user.id, removed_books)

    # Email ze books.
    # Add all books that were supposed to be emailed. If email was
    # unsuccessful, mark book as unsent.
    email_from = user.emailer
    email_to = get_to_emails(user)
    attachments = []
    attachment_size = 0
    for book in added_books:
        # If the next book added will put us over the attachment size limit
        # (and there are attachments to send), or if we've reached the maximum
        # number of attachments, send this batch.
        if ((attachment_size + book.size > ATTACHMENTS_SIZE_LIMIT and len(attachments > 0))
                or len(attachments) == ATTACHMENTS_LIMIT):
            email_attachments(email_from, email_to, attachments, user.id)
            attachments = []
            attachment_size = 0

        attachments.append(book)
        attachment_size += book.size

    if len(attachments) > 0:
        email_attachments(email_from, email_to, attachments, user.id)

    # Update the Dropbox delta cursor in database.
    user.cursor = delta['cursor']

    # Clean up the temporary files.
    if len(added_books) > 0:
        clear_tmp_directory()

    db.session.commit()

    return False


@celery.task(ignore_result=True)
def kindlebox(dropbox_id):
    # Lock per user.
    lock_id = '{0}-lock-{1}'.format(kindlebox.__name__, dropbox_id)
    lock = redis.lock(lock_id, timeout=LOCK_EXPIRE)

    # If unable to acquire lock, discard the task and hope that another worker
    # finishes (see note below).
    if not lock.acquire(blocking=False):
        log.debug("Couldn't acquire lock {0}.".format(lock_id))
        return False

    log.debug("Lock {0} acquired.".format(lock_id))

    # Only process Dropbox changes for active users.
    user = User.query.filter_by(dropbox_id=dropbox_id, active=True).first()
    if user is None:
        lock.release()
        return

    log.info("Processing dropbox webhook for user id {0}".format(user.id))
    # Loop until there is no delta.
    # NOTE: There is a slight chance of a race condition between dropbox
    # webhook and two celery workers that would result in a delta getting
    # dropped, but hopefully this is better than cluttering the task queues.
    client = DropboxClient(user.access_token)
    while True:
        log.debug("Processing one kindlebox iteration for dropbox id "
                  "{0}".format(dropbox_id))
        try:
            done = _kindlebox(dropbox_id, user, client)
            if done:
                break
        except:
            log.error(("Failed to process dropbox webhook for user id "
                       "{0}.").format(user.id), exc_info=True)
            break

    lock.release()


@celery.task(ignore_result=True)
def resend_books(dropbox_id):
    # Lock per user.
    lock_id = '{0}-lock-{1}'.format(resend_books.__name__, dropbox_id)
    lock = redis.lock(lock_id, timeout=LOCK_EXPIRE)

    # If unable to acquire lock, discard the task.
    if not lock.acquire(blocking=False):
        log.debug("Couldn't acquire lock {0}.".format(lock_id))
        return False

    log.debug("Lock {0} acquired.".format(lock_id))

    # Only resend books for active users.
    user = User.query.filter_by(dropbox_id=dropbox_id, active=True).first()
    if user is None:
        lock.release()
        return

    log.info("Processing book resend for user id {0}".format(user.id))

    # Set the books to have the upper attachment limit as their size to ensure
    # that they send individually.
    unsent_books = [BookTuple(pathname=book.pathname,
                              book_hash=book.book_hash,
                              size=ATTACHMENTS_SIZE_LIMIT)
                    for book in user.books.filter_by(unsent=True).all()]

    # Re-download all the books that failed to send before. Make sure the
    # hashes match.
    client = DropboxClient(user.access_token)
    for book in unsent_books:
        dropbox_book_hash = download_book(client, book.pathname)
        if dropbox_book_hash != book.book_hash:
            log.warning("Downloaded book {book_path} doesn't match unsent book "
                        "for user id {user_id}".format(book_path=book.pathname,
                                                       user_id=user.id))

    # Resend the books and clean up the temporary files.
    if len(unsent_books) > 0:
        email_attachments(user.emailer, get_to_emails(user), unsent_books, user.id)
        clear_tmp_directory()

    db.session.commit()

    lock.release()


def mimetypes_filter(path):
    return mimetypes.guess_type(path)[0] in BOOK_MIMETYPES


BookTuple = namedtuple('Book', ['pathname', 'book_hash', 'size'])
def get_added_books(delta_entries, client, user_id):
    """
    Return a list of Book tuples of the form ['pathname', 'book_hash', 'size'].
    All books in this list have the correct mimetype, are under the size limit,
    and don't have a duplicate hash in the database (i.e. not a filepath
    rename).
    """
    added_entries = []
    for entry in delta_entries:
        pathname, metadata = entry
        pathname = canonicalize(pathname)

        # First check that it's not a removed pathname.
        if metadata is None:
            continue
        # Check that pathname is a file, has an okay mimetype and is under the
        # size limit.
        if (metadata['is_dir'] or mimetypes_filter(pathname) is None or
                metadata['bytes'] > ATTACHMENTS_SIZE_LIMIT):
            continue

        book_hash = download_book(client, pathname)

        # Make sure that the book is not a duplicate of a previously added book
        # (probably a renamed file).
        if (Book.query.filter_by(user_id=user_id)
                      .filter_by(book_hash=book_hash).count() == 0):
            added_entries.append(BookTuple(pathname=pathname,
                                           book_hash=book_hash,
                                           size=metadata['bytes']))

    return added_entries


def get_removed_books(delta_entries):
    """
    Return a list of book paths that were deleted during this delta.
    """
    removed_entries = [canonicalize(entry[0]) for entry in delta_entries if
                       entry[1] is None]
    return [entry for entry in removed_entries if mimetypes_filter(entry)]


def download_book(client, book_path):
    # Make all the necessary nested directories in the temporary directory.
    tmp_path = get_tmp_path(book_path)
    try:
        book_dir = os.path.dirname(tmp_path)
        if not os.path.exists(book_dir):
            os.makedirs(book_dir)
    except OSError:
        log.error("Error creating directories for book {0}".format(book_path),
                  exc_info=True)

    md5 = hashlib.md5()
    with open(tmp_path, 'w') as tmp_book:
        with client.get_file(book_path) as book:
            data = book.read()
            tmp_book.write(data)
            md5.update(data)

    mobi_tmp_path = epub_to_mobi_path(tmp_path)
    if mobi_tmp_path is not None:
        subprocess.check_call(['ebook-convert', tmp_path, mobi_tmp_path])

    book_hash = md5.hexdigest()

    return book_hash


def remove_books(user_id, removed_books):
    for book_path in removed_books:
        book = Book.query.filter_by(user_id=user_id).filter_by(pathname=book_path).first()
        if book is not None:
            db.session.delete(book)


def add_book(user_id, book, unsent):
    book_row = Book.query.filter_by(user_id=user_id,
                                    book_hash=book.book_hash,
                                    pathname=book.pathname).first()
    if book_row is None:
        book_row = Book(user_id, book.pathname, book.book_hash, unsent=unsent)
        db.session.add(book_row)

    book_row.unsent = unsent


def email_attachments(email_from, email_to, attachments, user_id):
    attachment_paths = get_attachment_paths(book.pathname for book in attachments)
    log.debug("Sending email to " + ' '.join(email_to) + " " + ' '.join(attachment_paths))

    try:
        # First try to batch email.
        _email_attachments(email_from, email_to, attachment_paths)
        for book in attachments:
            add_book(user_id, book, False)
    except Exception:
        log.error("Failed to send books for user id {0}".format(user_id),
                  exc_info=True)

        # If fail to batch email, try sending individually instead.
        for book in attachments:
            try:
                _email_attachments(email_from, email_to, get_attachment_paths([book.pathname]))
                add_book(user_id, book, False)
            except Exception:
                log.error("Failed to resend book for user id {0}".format(user_id),
                          exc_info=True)
                add_book(user_id, book, True)


def _email_attachments(email_from, email_to, attachment_paths):
    status, message = emailer.send_mail(email_from, email_to,
                                        attachment_paths)
    if status != 200:
        raise KindleboxException(message)


def epub_to_mobi_path(epub_path):
    if mimetypes.guess_type(epub_path)[0] == EPUB_MIMETYPE:
        return epub_path[:-len('epub')] + 'mobi'


def _clear_directory(directory):
    """
    Remove all possible directories and files from a given directory.
    """
    for path in os.listdir(directory):
        subdirectory = os.path.join(directory, path)
        if os.path.isdir(subdirectory):
            _clear_directory(subdirectory)
            os.rmdir(subdirectory)
        else:
            os.unlink(subdirectory)


def clear_tmp_directory():
    """
    Remove all possible directories and files from the temporary directory.
    """
    try:
        _clear_directory(os.path.join(BASE_DIR, str(os.getpid())))
        os.rmdir(os.path.join(BASE_DIR, str(os.getpid())))
    except OSError:
        log.error("Failed to clear tmp directory", exc_info=True)


def get_tmp_path(book_path):
    return os.path.join(BASE_DIR, str(os.getpid()), book_path.strip('/'))


def get_attachment_paths(book_paths):
    attachment_paths = []
    for book_path in book_paths:
        tmp_path = get_tmp_path(book_path)
        mobi_tmp_path = epub_to_mobi_path(tmp_path)
        if mobi_tmp_path is not None:
            tmp_path = mobi_tmp_path
        attachment_paths.append(tmp_path)
    return attachment_paths


def canonicalize(pathname):
    return pathname.lower()


def get_to_emails(user):
    return [k.kindle_name + '@kindle.com' for k in user.kindle_names.all()]


class KindleboxException(Exception):
    pass
