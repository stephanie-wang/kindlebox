from dropbox.client import DropboxClient
import md5
import mimetypes
import os.path

from kindlebox import emailer
from kindlebox.database import db
from kindlebox.database import User, Book

BOOK_MIMETYPES = set(
    'application/pdf',
    'application/x-mobipocket-ebook',
    'application/epub+zip',
    'application/vnd.amazon.ebook',
    'text/plain')


def process_user(user_id):
    user = User.query.filter_by(user_id=user_id).first()

    email_from = user.emailer
    email_to = kindle_name + '@kindle.com'

    client = get_client(user.access_token)
    tmp_paths = download_books(client, cursor=user.cursor)
    
    # TODO: send books in chunks of <=25, <=50MB each (maybe zip?)
    emailer.send_mail(emailer, email, 'convert', '', tmp_paths)

    # TODO: save to database, delete tmp files

def get_client(access_token):
    '''
    Get the Dropbox client from cache or create it.
    '''
    return DropboxClient(access_token)

def download_books(client, cursor=None):
    # TODO: catch 401 error
    delta = client.delta(cursor)

    changed = delta['entries']
    added = [entry for entry in changed if entry[1] != None]
    removed = [entry for entry in changed if entry[1] == None]

    # Get all entries that were added and are not a directory.
    books_added = [entry[0] for entry in added if not entry[1]['is_dir']] 
    # TODO: check books for file renames
    # TODO: check books for correct file extensions
    hashes = {}
    for i, book_path in enumerate(books_added):
        if book_path not in BOOK_MIMETYPES:
            continue
        hashes[book_path] = download_book(client, book_path)

    # TODO: what happens if emailing fails midway through hashes? need some sort
    # of saved flag in database. should probably save books one at a time in case
    # of failure
 
    books_removed = [entry[0] for entry in removed]
    books_removed = zip(books_removed, [None] * len(book_removed))
    hashes.update(books_removed)

    return hashes 


def download_book(client, book_path):
    try:
        os.makedirs(book_path)
    except OSError:
        continue

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
