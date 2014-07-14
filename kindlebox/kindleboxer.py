from dropbox.client import DropboxClient
import md5
import mimetypes
import os.path

from kindlebox import emailer
from kindlebox.database import db
from kindlebox.models import User, Book

BOOK_MIMETYPES = set([
    'application/pdf',
    'application/x-mobipocket-ebook',
    'application/epub+zip',
    'application/vnd.amazon.ebook',
    'text/plain',
    ])


def process_user(dropbox_id):
    user = User.query.filter_by(dropbox_id=dropbox_id).first()
    if not user.active:
        return

    client = DropboxClient(user.access_token)
    delta = client.delta(user.cursor)

    added_books = get_added_books(delta['entries'], client)
    removed_books = get_removed_books(delta['entries'])

    # Download and get hashes for books added to the directory.
    emailed_books = []
    for book_path, book_hash in added_books:
        duplicates = user.books.filter_by(hash=book_hash)
        if duplicates.count() > 1:
            continue
        emailed_books.append(book_path)

    # Email ze books.
    email_from = user.emailer
    #email_to = user.kindle_name + '@kindle.com'
    email_to = user.email
    for i in range(len(emailed_books) / 25):
        books = emailed_books[i * 25:(i+1) * 25]
        emailer.send_email(email_from, email_to, 'convert', '', books)

    # Update the Dropbox delta cursor in database.
    user.cursor = delta['cursor']
    # Save all books to the database.
    for book_path, book_hash in added_books:
        book = Book(user.id, book_path, book_hash)
        db.add(book)
        try:
            os.unlink(book_path)
        except OSError:
            log.error("Womp womp. Couldn't delete book %s. Not a file?" %
                      book_path)
    for book_path in removed_books:
        book = user.books.filter_by(pathname=book_path).first()
        db.delete(book)
    db.commit()


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
        if book_path not in BOOK_MIMETYPES:
            continue
        hashes.append((book_path, download_book(client, book_path)))

    return hashes


def get_removed_books(delta_entries):
    return [entry[0] for entry in delta_entries if entry[1] is None]


def download_book(client, book_path):
    try:
        os.makedirs(book_path)
    except OSError:
        pass

    md5 = hashlib.md5()
    with open(book_path, 'w') as tmp_book:
        with client.get_file(book) as book:
            data = book.read()
            tmp_book.write(data)
            md5.update(data)

    book_hash = md5.digest().decode('iso-8859-1')

    return book_hash


def canonicalize(pathname):
    return pathname.lower()


def main():
    pass


if __name__ == '__main__':
    main()
