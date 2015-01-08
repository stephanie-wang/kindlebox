import hashlib
import logging
import mimetypes
import os

from dropbox.client import DropboxClient

from app import celery
from app import db
from app import emailer
from app.models import User, Book
#from app.queue import queuefunc


log = logging.getLogger()

BASE_DIR = '/tmp/kindlebox'
try:
    os.makedirs(BASE_DIR)
except OSError:
    pass

mimetypes.add_type('application/x-mobipocket-ebook', '.mobi')
mimetypes.add_type('application/epub+zip', '.epub')
BOOK_MIMETYPES = {
    'application/pdf',
    'application/x-mobipocket-ebook',
    'application/epub+zip',
    'application/vnd.amazon.ebook',
    'text/plain',
    }
BOOK_CHUNK = 5


#@queuefunc
@celery.task(ignore_result=True)
def kindlebox(dropbox_id):
    user = User.query.filter_by(dropbox_id=dropbox_id, active=True).first()
    if user is None:
        return False

    client = DropboxClient(user.access_token)
    delta = client.delta(user.cursor)

    added_books = get_added_books(delta['entries'], client)
    removed_books = get_removed_books(delta['entries'])

    # Download the books and get the hashes
    hashes = []
    for book_path in added_books:
        #if mimetypes.guess_type(book_path)[0] in BOOK_MIMETYPES:
        hashes.append(
                (get_tmp_path(book_path), download_book(client, book_path))
                )

    # Download and get hashes for books added to the directory.
    new_books = [book_path for book_path, book_hash in hashes if
            user.books.filter_by(book_hash=book_hash).count() == 0]

    # Email ze books.
    email_from = user.emailer
    email_to = [row.kindle_name + '@kindle.com' for row in user.kindle_names.all()]
    # TODO: GET RID OF THIS
    email_to.append('wang.stephanie93@gmail.com')
    for i in range(0, len(new_books), BOOK_CHUNK):
        books = new_books[i : i + BOOK_CHUNK]
        emailer.send_mail(email_from, email_to, 'convert', '', books)

    # Clean up the temporary files.
    clear_tmp_directory()

    # Update the Dropbox delta cursor in database.
    user.cursor = delta['cursor']
    # Save all books to the database.
    for book_path, book_hash in hashes:
        book = Book(user.id, book_path, book_hash)
        db.session.add(book)

    for book_path in removed_books:
        book = user.books.filter_by(pathname=get_tmp_path(book_path)).first()
        if book is not None:
            db.session.delete(book)
    db.session.commit()

    return True


def get_added_books(delta_entries, client):
    return [canonicalize(entry[0]) for entry in delta_entries if entry[1] is
            not None and not entry[1]['is_dir']]


def get_removed_books(delta_entries):
    return [canonicalize(entry[0]) for entry in delta_entries if entry[1] is
            None]


def download_book(client, book_path):
    tmp_path = get_tmp_path(book_path)
    try:
        book_dir = os.path.dirname(tmp_path)
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

    book_hash = md5.digest().decode('iso-8859-1')

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
    _clear_directory(BASE_DIR)


def get_tmp_path(book_path):
    return os.path.join(BASE_DIR, book_path.strip('/'))


def canonicalize(pathname):
    return pathname.lower()


def main():
    pass


if __name__ == '__main__':
    main()
