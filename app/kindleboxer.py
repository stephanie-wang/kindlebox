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
BOOK_ATTACHMENTS_LIMIT = 25
ATTACHMENTS_SIZE_LIMIT = 15 * (10**6)

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
                log.info("Welcome PDF sent to Dropbox ID {0}.".format(dropbox_id))
            else:
                raise Exception("No response received after sending welcome PDF")

        user.set_uploaded_welcome_pdf()
        db.session.commit()

    except:
        log.error(("Welcome PDF failed for Dropbox ID "
                   "{0}.").format(dropbox_id), exc_info=True)
        return False

    return True


@celery.task(ignore_result=True)
def kindlebox(dropbox_id):
    # Lock per user.
    lock_id = '{0}-lock-{1}'.format(kindlebox.__name__, dropbox_id)
    lock = redis.lock(lock_id, timeout=LOCK_EXPIRE)

    # If unable to acquire lock, wait a bit and then add to the queue again.
    if not lock.acquire(blocking=False):
        log.debug("Couldn't acquire lock {0}.".format(lock_id))
        time.sleep(1)
        kindlebox.delay(dropbox_id)
        return False

    log.debug("Lock {0} acquired.".format(lock_id))

    try:
        # Only process Dropbox changes for active users.
        user = User.query.filter_by(dropbox_id=dropbox_id, active=True).first()
        if user is None:
            return False

        client = DropboxClient(user.access_token)
        delta = client.delta(user.cursor)

        added_book_sizes = dict(get_added_book_sizes(delta['entries'], client))
        removed_books = get_removed_books(delta['entries'])
        log.debug("Delta contains {0} added books, {1} removed "
                  "books".format(len(added_book_sizes), len(removed_books)))

        # Download the changed files and get the hashes.
        # Also record the paths of any newly added books.
        hashes = []
        new_books = []
        new_hashes = set()
        for book_path, book_byte_size in added_book_sizes.iteritems():
            book_hash = download_book(client, book_path)
            hashes.append((book_path, book_hash))

            # Make sure that the book is not a duplicate of either a previously
            # added book or a book added on this round.
            if (user.books.filter_by(book_hash=book_hash).count() == 0 and
                    book_hash not in new_hashes):
                new_hashes.add(book_hash)
                new_books.append(book_path)

        # Email ze books.
        email_from = user.emailer
        email_to = [row.kindle_name + '@kindle.com' for row in user.kindle_names.all()]
        for book in new_books:
            tmp_path = get_tmp_path(book)
            mobi_tmp_path = epub_to_mobi_path(tmp_path)
            if mobi_tmp_path is not None:
                tmp_path = mobi_tmp_path

            status, msg = emailer.send_mail(email_from, email_to, [tmp_path])
            if status != 200:
                raise Exception("Failed to email for dropbox id {id}, message: "
                                "{message}".format(id=dropbox_id, message=msg))

        # Update the Dropbox delta cursor in database.
        user.cursor = delta['cursor']

        # Save all books, added/updated and removed, to the database.
        for book_path, book_hash in hashes:
            book = user.books.filter_by(pathname=book_path).first()
            if book is None:
                book = Book(user.id, book_path, book_hash)
                db.session.add(book)
            else:
                book.book_hash = book_hash

        num_books_deleted = 0
        for book_path in removed_books:
            book = user.books.filter_by(pathname=book_path).first()
            if book is not None:
                db.session.delete(book)
                num_books_deleted += 1
        db.session.commit()

        return True

    except:
        log.error(("Failed to process dropbox webhook for dropbox id "
                   "{0}.").format(dropbox_id), exc_info=True)
    finally:
        lock.release()

        # Clean up the temporary files.
        if len(added_book_sizes) > 0:
            clear_tmp_directory()


def mimetypes_filter(path):
    return mimetypes.guess_type(path)[0] in BOOK_MIMETYPES


def get_added_book_sizes(delta_entries, client):
    """
    Return a list of tuples of (book path, book size) representing books added
    during this delta. Book path must be of one of the accepted mimetypes and
    book size is under the BOOK_SIZE_LIMIT.
    """
    added_entries = [(canonicalize(entry[0]), entry[1]['bytes']) for entry in delta_entries if
                     entry[1] is not None and not entry[1]['is_dir']]
    return [entry for entry in added_entries if (mimetypes_filter(entry[0]) and
            entry[1] < ATTACHMENTS_SIZE_LIMIT)]


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


def canonicalize(pathname):
    return pathname.lower()
