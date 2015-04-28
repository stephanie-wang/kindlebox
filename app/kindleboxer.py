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
# after encoding to email text, so more like 15. Mailgun is about 25MB?  And
# can only email 25 books at a time.
ATTACHMENTS_LIMIT = 25
ATTACHMENTS_SIZE_LIMIT = 25 * (10**6)
AMAZON_SIZE_LIMIT = 50 * (10**6)

# Try to send a file this many times before giving up. Sending a file means
# successful Dropbox download, file conversion, and correct response from
# SendGrid or Mailgun.
MAX_SEND_ATTEMPTS = 10

# Amazon doesn't support these formats, but BookDrop does!
EPUB_MIMETYPE = 'application/epub+zip'
AZW3_MIMETYPE = 'application/bookdrop-azw3'  # not a real mimetype, but we need to recognize it.
CBR_MIMETYPE = 'application/x-cbr'
CBZ_MIMETYPE = 'application/x-cbz'
CONVERTIBLE_MIMETYPES = {EPUB_MIMETYPE,
                         CBR_MIMETYPE,
                         CBZ_MIMETYPE,
                         AZW3_MIMETYPE}

# Supported filetypes.
# According to:
# http://www.amazon.com/gp/help/customer/display.html?nodeId=200375630
mimetypes.add_type('application/x-mobipocket-ebook', '.mobi')
mimetypes.add_type('application/x-mobipocket-ebook', '.prc')
mimetypes.add_type('application/vnd.amazon.ebook', '.azw')
mimetypes.add_type('application/vnd.amazon.ebook', '.azw1')
mimetypes.add_type(EPUB_MIMETYPE, '.epub')
mimetypes.add_type(AZW3_MIMETYPE, '.azw3')

BOOK_MIMETYPES = CONVERTIBLE_MIMETYPES.union({
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
    })
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
        with open('app/static/bookdrop_welcome.pdf', 'rb') as f:
            response = client.put_file('Welcome to BookDrop.pdf', f, overwrite=True)
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


def _acquire_lock(method_name, dropbox_id, blocking=True):
    # Lock per user.
    lock_id = '{0}-lock-{1}'.format(method_name, dropbox_id)
    lock = redis.lock(lock_id, timeout=LOCK_EXPIRE)

    # If non-blocking and unable to acquire lock, discard the task and hope
    # that another worker finishes it.
    if not lock.acquire(blocking=blocking):
        log.debug("Couldn't acquire lock {0}.".format(lock_id))
        return None

    log.debug("Lock {0} acquired.".format(lock_id))
    return lock


def _kindlebox(dropbox_id, user, client):
    """
    The main body of a `kindlebox` task. Processes a single Dropbox delta for
    the given Dropbox ID. For any newly added books that satisfy the
    requirements (under size limit, etc.), attempts to email as many of them as
    possible. For any removed books, delete them from the database. Finally,
    update the user's Dropbox API cursor.
    """
    delta = client.delta(user.cursor)

    # Process delta to get added and removed books. Also download any newly
    # added books and get the hashes.
    added_books = get_added_books(delta['entries'], user.id, client)
    removed_books = get_removed_books(delta['entries'], user.id)
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
    for book in removed_books:
        db.session.delete(book)

    # Send the first batch of books and queue the other batches.
    db.session.flush()
    if len(added_books) > 0:
        send_books(user.id, min(book.id for book in added_books),
                     downloaded=True)

    # Update the Dropbox delta cursor in database.
    user.cursor = delta['cursor']
    db.session.merge(user)
    db.session.commit()

    return False


@celery.task(ignore_result=True)
def kindlebox(dropbox_id):
    """
    Task that continually processes any Dropbox changes for the user associated
    with the given dropbox ID until there are no more changes. Any books
    removed from Dropbox are also deleted from the database. The first
    `ATTACHMENTS_LIMIT` books out of the books added to Dropbox are sent. The
    rest of the books are queued.
    """
    kindlebox_lock = _acquire_lock(kindlebox.__name__, dropbox_id)
    # Another worker is taking care of it, so I'm done.
    if kindlebox_lock is None:
        return False

    # Only process Dropbox changes for active users.
    user = User.query.filter_by(dropbox_id=dropbox_id, active=True).first()
    if user is None:
        kindlebox_lock.release()
        return

    log.info("Processing dropbox webhook for user id {0}".format(user.id))
    # Loop until there is no delta.
    # NOTE: There is a slight chance of a race condition between dropbox
    # webhook and two celery workers that would result in a delta getting
    # dropped, but hopefully this is better than cluttering the task queues.
    client = DropboxClient(user.access_token)
    while True:
        log.debug("Processing one kindlebox iteration for user id "
                  "{0}".format(user.id))
        try:
            done = _kindlebox(dropbox_id, user, client)
            if done:
                break
        except:
            log.error(("Failed to process dropbox webhook for user id "
                       "{0}.").format(user.id), exc_info=True)
            break

    kindlebox_lock.release()


def _send_books(user, books, downloaded):
    """
    Helper function for the `send_books` celery task. Download, if necessary,
    and email all the given user's books. Mark each book as `unsent` or not in
    the database.
    """
    client = DropboxClient(user.access_token)
    email_from = user.emailer
    email_to = get_to_emails(user)
    attachments = []
    attachment_size = 0
    for book in books:
        # If there's an error downloading or converting the book, don't try
        # to send it.
        book_hash = book.book_hash
        if not downloaded:
            book_hash = download_book(client, book.pathname, user.id)
        if book_hash is None:
            continue
        error = convert_book(get_tmp_path(book.pathname), user.id)
        if error:
            log.error("Failed to ebook-convert {book} for user id {user_id}\n"
                      "STDERR: {stderr}\n".format(book=book.pathname,
                                                  user_id=user.id,
                                                  stderr=error))
            continue

        # If the next book added will put us over the attachment size limit,
        # send this batch.
        # NOTE: An individual book with size over the limit will still get sent
        # using this code. We want to do this in case it actually is possible
        # to send the file (who knows what sendgrid's limits are?).
        if (attachment_size + book.get_size() > ATTACHMENTS_SIZE_LIMIT and
                len(attachments) > 0):
            email_attachments(email_from, email_to, attachments, user.id)
            attachments = []
            attachment_size = 0

        attachments.append(book)
        attachment_size += book.get_size()

    if len(attachments) > 0:
        email_attachments(email_from, email_to, attachments, user.id)


@celery.task(ignore_result=True)
def send_books(user_id, min_book_id=0, downloaded=False):
    """
    Task to send any books associated with the given user ID that are marked as
    `unsent`. Sends a batch of at most `ATTACHMENTS_LIMIT` books, all with
    Book.id greater than or equal to the given `min_book_id`. If `downloaded`
    is false, also downloads the books from the Dropbox API. Files that need
    conversion are converted before sending.

    Before finishing, the task queues another `send_books` task for the next
    batch of (distinct) books.
    """
    send_lock = _acquire_lock(send_books.__name__, user_id, blocking=True)
    if send_lock is None:
        return

    # Only resend books for active users.
    user = User.query.filter_by(id=user_id, active=True).first()
    if user is None:
        return

    log.info("Processing book resend for user id {0}".format(user_id))

    # Get the next batch of books that haven't been sent yet and are still
    # under the maximum number of send attempts.
    unsent_books_query = (user.books.filter_by(unsent=True)
                                    .filter(Book.num_attempts < MAX_SEND_ATTEMPTS)
                                    .order_by(Book.id))
    unsent_books = (unsent_books_query.filter(Book.id >= min_book_id)
                                      .limit(ATTACHMENTS_LIMIT).all())
    if len(unsent_books) == 0:
        send_lock.release()
        return

    # Re-download and convert books that failed to send before. Check that
    # hashes match.
    try:
        _send_books(user, unsent_books, downloaded)
        for book in unsent_books:
            book.num_attempts += 1
        db.session.commit()
    except:
        log.error("Failed to resend books for user id {0}".format(user_id),
                  exc_info=True)
    finally:
        # If there are any more books to send after this batch, requeue them.
        next_unsent_book = unsent_books_query.filter(Book.id > unsent_books[-1].id).first()
        if next_unsent_book > 0:
            send_books.delay(user_id, next_unsent_book.id)

        clear_tmp_directory()
        send_lock.release()


def get_added_books(delta_entries, user_id, client):
    """
    Return a list of Books. All books in this list have the correct mimetype,
    are under the size limit, and don't have a duplicate hash in the database
    (i.e. not a filepath rename).
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
        if (metadata['is_dir'] or not mimetypes_filter(pathname) or
                metadata['bytes'] > AMAZON_SIZE_LIMIT):
            continue

        book = Book(user_id,
                    pathname,
                    download_book(client, pathname, user_id),
                    metadata['bytes'])
        # NOTE: It's possible that the book failed to download here, in which
        # case `book_hash` is None. We still add it to the database in case it
        # can be downloaded later.
        db.session.add(book)

        # Make sure that the book is not a duplicate of a previously added book
        # (probably a renamed file).
        duplicate = (Book.query.filter_by(user_id=user_id)
                               .filter_by(book_hash=book.book_hash).first())
        if (duplicate is not None):
            book.unsent = duplicate.unsent
            continue

        added_entries.append(book)

    return added_entries


def get_removed_books(delta_entries, user_id):
    """
    Return a list of Books whose paths were deleted during this delta.
    """
    removed_entries = [canonicalize(entry[0]) for entry in delta_entries if
                       entry[1] is None]
    if len(removed_entries) > 0:
        return (Book.query.filter_by(user_id=user_id)
                          .filter(Book.pathname.in_(removed_entries)).all())
    else:
        return []


def convert_book(tmp_path, user_id):
    """
    Attempt to convert any books of type in `CONVERTIBLE_MIMETYPES` to .mobi,
    in the same folder as the given temporary path.
    """
    mobi_tmp_path = convert_to_mobi_path(tmp_path)
    if mobi_tmp_path is None:
        return None

    log.info("Converting book for user id {0}".format(user_id))
    p = subprocess.Popen(['ebook-convert', tmp_path, mobi_tmp_path],
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    _, stderr = p.communicate()
    return stderr


def download_book(client, book_path, user_id):
    """
    Download the given book path, for the given user ID, from the Dropbox
    client to a temporary path. Make all the directories in the given book path
    at the temporary root folder if they don't already exist. If the book is an
    epub, convert it to mobi.

    Return the hash of the downloaded (and converted) file.
    """
    # Make all the necessary nested directories in the temporary directory.
    tmp_path = get_tmp_path(book_path)
    try:
        book_dir = os.path.dirname(tmp_path)
        if not os.path.exists(book_dir):
            os.makedirs(book_dir)
    except OSError:
        log.error("Error creating directories for book {0}".format(book_path),
                  exc_info=True)

    try:
        md5 = hashlib.md5()
        with open(tmp_path, 'w') as tmp_book:
            with client.get_file(book_path) as book:
                data = book.read()
                tmp_book.write(data)
                md5.update(data)

        book_hash = md5.hexdigest()

        return book_hash
    except:
        log.error("Failed to download book {book_path} for user id "
                  "{user_id}".format(book_path=book_path,
                                     user_id=user_id), exc_info=True)
        return None


def email_attachments(email_from, email_to, attachments, user_id):
    """
    Given a 'from' email address and a list of 'to' email addresses, try to
    email as many of the attachments in the given list as possible. For each
    attachment, add the book to the user associated with the given ID and mark
    whether it was successfully emailed or not.
    """
    attachment_paths = get_attachment_paths(book.pathname for book in attachments)
    log.debug("Sending email to " + ' '.join(email_to) + " " + ' '.join(attachment_paths))

    try:
        # First try to batch email.
        _email_attachments(email_from, email_to, attachment_paths)
        for book in attachments:
            book.mark_unsent(False)
    except:
        log.error("Failed to send books for user id {0}".format(user_id),
                  exc_info=True)

        # If fail to batch email, try sending individually instead.
        for book in attachments:
            try:
                _email_attachments(email_from, email_to, get_attachment_paths([book.pathname]))
                book.mark_unsent(False)
            except:
                log.error("Failed to resend book for user id {0}".format(user_id),
                          exc_info=True)
                book.mark_unsent(True)


def _email_attachments(email_from, email_to, attachment_paths):
    status, message = emailer.send_mail(email_from, email_to,
                                        attachment_paths)
    if status != 200:
        raise KindleboxException(message)


def convert_to_mobi_path(path):
    if mimetypes.guess_type(path)[0] in CONVERTIBLE_MIMETYPES:
        stripped_path = os.path.splitext(path)[0].encode('ascii', 'ignore')
        return '{path}.mobi'.format(path=stripped_path)


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
        log.debug("Failed to clear tmp directory", exc_info=True)


def get_tmp_path(book_path):
    return os.path.join(BASE_DIR, str(os.getpid()), book_path.strip('/'))


def get_attachment_paths(book_paths):
    attachment_paths = []
    for book_path in book_paths:
        tmp_path = get_tmp_path(book_path)

        # If this book got converted, get the .mobi path instead.
        mobi_tmp_path = convert_to_mobi_path(tmp_path)
        if mobi_tmp_path is not None:
            tmp_path = mobi_tmp_path

        attachment_paths.append(tmp_path)

    return attachment_paths


def canonicalize(pathname):
    return pathname.lower()


def get_to_emails(user):
    return [k.kindle_name + '@kindle.com' for k in user.kindle_names.all()]


def mimetypes_filter(path):
    return mimetypes.guess_type(path)[0] in BOOK_MIMETYPES


class KindleboxException(Exception):
    pass
