import hashlib
import logging
import mimetypes
import os
import time

from dropbox.client import DropboxClient

from app import analytics
from app import celery
from app import db
from app import emailer
from app import redis
from app.models import User, Book


log = logging.getLogger()

# Lock expires in 5 minutes.
LOCK_EXPIRE = 60 * 5

BASE_DIR = '/tmp/kindlebox'
try:
    os.makedirs(BASE_DIR)
except OSError:
    pass

# Supported filetypes.
# According to:
# http://www.amazon.com/gp/help/customer/display.html?nodeId=200375630
mimetypes.add_type('application/x-mobipocket-ebook', '.mobi')
mimetypes.add_type('application/x-mobipocket-ebook', '.prc')
mimetypes.add_type('application/vnd.amazon.ebook', '.azw')
mimetypes.add_type('application/vnd.amazon.ebook', '.azw1')
# Amazon doesn't allow epub :(
#mimetypes.add_type('application/epub+zip', '.epub')
BOOK_MIMETYPES = {
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
                                active=True,
                                uploaded_welcome_pdf=False).first()
    if user is None:
        return False

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


@celery.task(ignore_result=True)
def kindlebox(dropbox_id):
    # Lock per user.
    lock_id = '{0}-lock-{1}'.format(kindlebox.__name__, dropbox_id)
    lock = redis.lock(lock_id, timeout=LOCK_EXPIRE)

    # If unable to acquire lock, wait a bit and then add to the queue again.
    if not lock.acquire(blocking=False):
        log.debug("Couldn't acquire lock {0}.".format(lock_id))
        time.sleep(5)
        kindlebox.delay(dropbox_id)
        return False

    log.debug("Lock {0} acquired.".format(lock_id))

    # Only process Dropbox changes for active users.
    user = User.query.filter_by(dropbox_id=dropbox_id, active=True).first()
    if user is None:
        return False

    client = DropboxClient(user.access_token)
    delta = client.delta(user.cursor)

    added_books = get_added_books(delta['entries'], client)
    removed_books = get_removed_books(delta['entries'])

    # Download the changed files and get the hashes.
    # Also record the paths of any newly added books.
    hashes = []
    new_book_paths = []
    new_hashes = set()
    for book_path in added_books:
        book_hash = download_book(client, book_path)
        hashes.append((book_path, book_hash))

        # Make sure that the book is not a duplicate of either a previously
        # added book or a book added on this round.
        if (user.books.filter_by(book_hash=book_hash).count() == 0 and
                book_hash not in new_hashes):
            new_hashes.add(book_hash)
            new_book_paths.append(get_tmp_path(book_path))

    # Email ze books.
    email_from = user.emailer
    email_to = [row.kindle_name + '@kindle.com' for row in user.kindle_names.all()]
    for i in range(0, len(new_book_paths), BOOK_CHUNK):
        books = new_book_paths[i : i + BOOK_CHUNK]
        emailer.send_mail(email_from, email_to, 'convert', '', books)

    # Clean up the temporary files.
    if len(added_books) > 0:
        clear_tmp_directory()

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

    for book_path in removed_books:
        book = user.books.filter_by(pathname=book_path).first()
        if book is not None:
            db.session.delete(book)
    db.session.commit()

    lock.release()

    analytics.track(str(user.id), 'Kindleboxed')

    return True


def filter_supported_types(paths):
    return [path for path in paths if mimetypes.guess_type(path)[0] in
            BOOK_MIMETYPES]


def get_added_books(delta_entries, client):
    added_entries = [canonicalize(entry[0]) for entry in delta_entries if
                     entry[1] is not None and not entry[1]['is_dir']]
    return filter_supported_types(added_entries)


def get_removed_books(delta_entries):
    removed_entries = [canonicalize(entry[0]) for entry in delta_entries if
                       entry[1] is None]
    return filter_supported_types(removed_entries)


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

    book_hash = md5.hexdigest()

    return book_hash


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


def main():
    pass


if __name__ == '__main__':
    main()
