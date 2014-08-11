import hashlib
import mimetypes
import os

from dropbox.client import DropboxClient

from app import db
from app import emailer
from app import log
from app.models import User, Book
from app.queue import queuefunc


BASE_DIR = '/tmp/kindlebox'
BOOK_MIMETYPES = {
    'application/pdf',
    'application/x-mobipocket-ebook',
    'application/epub+zip',
    'application/vnd.amazon.ebook',
    'text/plain',
    }
BOOK_CHUNK = 5


@queuefunc
def kindlebox(dropbox_id):
    user = User.query.filter_by(dropbox_id=dropbox_id, active=True).first()
    if user is None:
        return

    client = DropboxClient(user.access_token)
    delta = client.delta(user.cursor)

    added_books = get_added_books(delta['entries'], client)
    removed_books = get_removed_books(delta['entries'])

    # Download and get hashes for books added to the directory.
    emailed_books = []
    for book_path, book_hash in added_books:
        duplicates = user.books.filter_by(book_hash=book_hash)
        if duplicates.count() == 0:
            emailed_books.append(get_tmp_path(book_path))

    # Email ze books.
    email_from = user.emailer
    email_to = user.kindle_name + '@kindle.com'
    for i in range(0, len(emailed_books), BOOK_CHUNK):
        books = emailed_books[i : i + BOOK_CHUNK]
        emailer.send_mail(email_from, email_to, 'convert', '', books)

    # Update the Dropbox delta cursor in database.
    user.cursor = delta['cursor']
    # Save all books to the database.
    for book_path, book_hash in added_books:
        book = Book(user.id, book_path, book_hash)
        db.session.add(book)
        try:
            os.unlink(get_tmp_path(book_path))
        except OSError:
            log.error("Womp womp. Couldn't delete book %s. Not a file?" %
                      book_path)
    for book_path in removed_books:
        book = user.books.filter_by(pathname=book_path).first()
        db.session.delete(book)
    db.session.commit()


def get_added_books(delta_entries, client):
    # Get all entries that were added and are not a directory.
    added_books = []
    for entry in delta_entries:
        if entry[1] is None:
            continue
        if entry[1]['is_dir']:
            continue
        book_path = canonicalize(entry[0])
        added_books.append(book_path)

    # Download the books and get the hashes
    hashes = []
    for book_path in added_books:
        if (mimetypes.guess_type(book_path)[0] not in BOOK_MIMETYPES):
            continue
        hashes.append((book_path, download_book(client, book_path)))

    return hashes


def get_removed_books(delta_entries):
    return [entry[0] for entry in delta_entries if entry[1] is None]


def download_book(client, book_path):
    try:
        book_dir = os.path.dirname(book_path)
        os.makedirs(book_dir)
    except OSError:
        pass

    md5 = hashlib.md5()
    with open(get_tmp_path(book_path), 'w') as tmp_book:
        with client.get_file(book_path) as book:
            data = book.read()
            tmp_book.write(data)
            md5.update(data)

    book_hash = md5.digest().decode('iso-8859-1')

    return book_hash


def get_tmp_path(book_path):
    return os.path.join(BASE_DIR, book_path.strip('/'))


def canonicalize(pathname):
    return pathname.lower()


def main():
    pass


if __name__ == '__main__':
    main()
