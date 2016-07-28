from collections import namedtuple
import hashlib
import logging
import mimetypes
import os
import subprocess32 as subprocess
import time

from dropbox.client import DropboxClient
from dropbox.rest import ErrorResponse

from app import analytics
from app import celery
from app import db
from app import emailer
from app import filesystem
from app import redis
from app.models import User, Book


log = logging.getLogger()

# Lock expires in 30 minutes, in case there are lots of epubs to convert.
LOCK_EXPIRE = 60 * 30

# And can only email 25 books at a time. Sendgrid only allows 20MB at a time,
# after encoding to email text, so more like 15. Mailgun is about 25MB?  And
# can only email 25 books at a time.
# Lower ATTACHMENTS_LIMIT to prevent users from hogging the celery workers.
ATTACHMENTS_LIMIT = 5
CONVERTIBLE_ATTACHMENTS_LIMIT = 1
ATTACHMENTS_SIZE_LIMIT = 25 * (10**6)
AMAZON_SIZE_LIMIT = 50 * (10**6)

# Try to send a file this many times before giving up. Sending a file means
# successful Dropbox download, file conversion, and correct response from
# SendGrid or Mailgun.
MAX_SEND_ATTEMPTS = 10

# Number of seconds to wait before timing out calibre conversion
CONVERSION_TIMEOUT = 1200

################################
# Book mimetypes
################################
# Amazon doesn't support these formats, but BookDrop does!
EPUB_MIMETYPE = 'application/epub+zip'
CBR_MIMETYPE = 'application/x-cbr'
CBZ_MIMETYPE = 'application/x-cbz'
AZW_MIMETYPE = 'application/vnd.amazon.ebook'  # not a real mimetype, but we need to recognize it.
CONVERTIBLE_MIMETYPES = {EPUB_MIMETYPE,
                         CBR_MIMETYPE,
                         CBZ_MIMETYPE,
                         AZW_MIMETYPE,
                         }

MOBI_MIMETYPE = 'application/x-mobipocket-ebook'

# Supported filetypes.
# According to:
# http://www.amazon.com/gp/help/customer/display.html?nodeId=200375630
BOOK_MIMETYPES = CONVERTIBLE_MIMETYPES.union({
    MOBI_MIMETYPE,
    'text/plain',
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

mimetypes.add_type(MOBI_MIMETYPE, '.mobi')
mimetypes.add_type(MOBI_MIMETYPE, '.prc')
mimetypes.add_type(AZW_MIMETYPE, '.azw')
mimetypes.add_type(AZW_MIMETYPE, '.azw1')
mimetypes.add_type(AZW_MIMETYPE, '.azw3')
mimetypes.add_type(EPUB_MIMETYPE, '.epub')

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
                log.info(u"Welcome PDF sent to user ID {0}.".format(user.id))
            else:
                raise Exception("No response received after sending welcome PDF")

        user.set_uploaded_welcome_pdf()
        db.session.commit()

    except:
        log.error((u"Welcome PDF failed for user ID "
                   "{0}.").format(user.id), exc_info=True)
        return False

    return True


def _kindlebox(dropbox_id, user, client):
    """
    The main body of a `kindlebox` task. Processes a single Dropbox delta for
    the given Dropbox ID. For any newly added books that satisfy the
    requirements (under size limit, etc.), attempts to email as many of them as
    possible. For any removed books, delete them from the database. Finally,
    update the user's Dropbox API cursor.
    """
    try:
        delta = client.delta(user.cursor)
    except ErrorResponse as e:
        log.info(u"Marking user id {0} inactive due to {1}".format(user.id, e.error_msg))
        user.active = False
        db.session.commit()
        return True

    # Process delta to get added and removed books. Also download any newly
    # added books and get the hashes.
    # NOTE: It's possible that the book failed to download here, in which case
    # each book in `added_books` has `book_hash` None. We still add it to the
    # database in case it can be downloaded later.
    added_books = get_added_books(delta['entries'], user.id, client)
    removed_books = get_removed_books(delta['entries'], user.id)
    log.debug(u"Delta contains {0} added books, {1} removed "
              "books".format(len(added_books), len(removed_books)))

    # If there are no more changes to process, update the cursor and we are
    # done.
    if len(added_books) == 0 and len(removed_books) == 0:
        user.cursor = delta['cursor']
        db.session.commit()
        return True

    # Add and delete books from the database.
    for book in added_books:
        db.session.add(book)
    for book in removed_books:
        db.session.delete(book)

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
    kindlebox_lock = acquire_kindlebox_lock(dropbox_id)
    # Another worker is taking care of it, so I'm done.
    if kindlebox_lock is None:
        log.debug(u"Unable to acquire kindlebox lock for dropbox id "
                  "{0}".format(dropbox_id))
        return

    # Only process Dropbox changes for active users.
    user = User.query.filter_by(dropbox_id=dropbox_id, active=True).first()
    if user is None:
        kindlebox_lock.release()
        return

    log.info(u"Processing dropbox webhook for user id {0}".format(user.id))
    # Loop until there is no delta.
    # NOTE: There is a slight chance of a race condition between dropbox
    # webhook and two celery workers that would result in a delta getting
    # dropped, but hopefully this is better than cluttering the task queues.
    client = DropboxClient(user.access_token)
    try:
        while True:
            log.debug(u"Processing one kindlebox iteration for user id "
                      "{0}".format(user.id))
            done = _kindlebox(dropbox_id, user, client)
            if done:
                break
    except:
        log.error((u"Failed to process dropbox webhook for user id "
                   "{0}.").format(user.id), exc_info=True)

    kindlebox_lock.release()
    if user.active:
        send_books(user.id)


def _send_books(user, books):
    """
    Helper function for the `send_books` celery task. Download, if necessary,
    and email all the given user's books. Mark each book as `unsent` or not in
    the database.
    """
    client = DropboxClient(user.access_token)
    email_from = user.emailer
    email_to = [row.kindle_name for row in user.kindle_names.all()]
    attachments = []
    attachment_size = 0
    for book in books:
        # If there's an error downloading or converting the book, don't try
        # to send it.
        if not os.path.exists(book.get_tmp_pathname()):
            download_book(client, book)
        if book.book_hash is None:
            continue
        error = convert_book(book)
        if error:
            log.error(u"Failed to ebook-convert {book} for user id {user_id}\n"
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
def send_books(user_id, min_book_id=0, convert=False):
    """
    Task to send any books associated with the given user ID that are marked as
    `unsent`. Sends a batch of at most `ATTACHMENTS_LIMIT` books, all with
    Book.id greater than or equal to the given `min_book_id`. Books are
    downloaded if necessary. Download (and convert) books that need conversion
    if and only if `convert` is True.

    Before finishing, the task queues another `send_books` task for the next
    batch of (distinct) books.
    """
    send_lock = acquire_send_books_lock(user_id)
    if send_lock is None:
        return

    # Only resend books for active users.
    user = User.query.filter_by(id=user_id, active=True).first()
    if user is None:
        return

    # Get the next batch of books that haven't been sent yet and are still
    # under the maximum number of send attempts.
    unsent_books_query = (user.books.filter_by(unsent=True)
                                    .filter(Book.num_attempts < MAX_SEND_ATTEMPTS)
                                    .order_by(Book.id))
    unsent_books = unsent_books_query.filter(Book.id >= min_book_id).all()

    # Only short-circuit if there are no new books at all to send, not just
    # ones that don't need conversion.
    if len(unsent_books) == 0 and min_book_id == 0:
        send_lock.release()
        return

    # Send either books that need conversion or books that don't.
    compatible_books, convertible_books = [], []
    for book in unsent_books:
        if convert_to_mobi_path(book.pathname) is None:
            compatible_books.append(book)
        else:
            convertible_books.append(book)
    if convert:
        unsent_books = convertible_books[:CONVERTIBLE_ATTACHMENTS_LIMIT]
    else:
        unsent_books = compatible_books[:ATTACHMENTS_LIMIT]

    log_string = ['{' + str(i) + '}' for i in range(len(unsent_books))]
    if len(unsent_books) > 0:
        log_string = ' '.join(log_string).format(*[book.id for book in unsent_books])
        if convert:
            log_string += ', with conversion'
    log.info(u"Processing book resend for user id {0}, book ids {1}".format(user_id, log_string))

    # Re-download and convert books that failed to send before.
    try:
        _send_books(user, unsent_books)
        # TODO: Reset all attempts to 0 before release.
        for book in unsent_books:
            book.num_attempts += 1
        db.session.commit()
    except:
        log.error(u"Failed to resend books for user id {0}".format(user_id),
                  exc_info=True)

    next_unsent_book = None
    if len(unsent_books) > 0:
        # If there are any more books to send after this batch, requeue them.
        next_unsent_book = unsent_books_query.filter(Book.id > unsent_books[-1].id).first()

    send_lock.release()

    # For some reason, calibre is leaving a lot of garbage files...
    filesystem.clear_calibre_files()

    if next_unsent_book is None:
        # If we've finished sending all books, including ones that need
        # conversion, clear all the books from the filesystem and finish
        # the task.
        if convert:
            kindlebox_lock = acquire_kindlebox_lock(user.dropbox_id)
            # Dropbox may have registered more books, so don't clear them yet.
            if kindlebox_lock is None:
                return
            filesystem.clear_directory(user.get_directory())
            kindlebox_lock.release()
        # Else, start sending the books that need conversion.
        else:
            send_books.apply_async((user_id, ),
                                   {'convert': True},
                                   queue='conversion')
    else:
        queue_kwarg = {}
        if convert:
            queue_kwarg['queue'] = 'conversion'
        send_books.apply_async((user_id, ),
                               {
                                   'min_book_id': next_unsent_book.id,
                                   'convert': convert,
                               },
                               **queue_kwarg)


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
                    metadata['bytes'])

        download_book(client, book)

        # Make sure that the book is not a duplicate of a previously added book
        # (probably a renamed file).
        duplicate = (Book.query.filter_by(user_id=user_id)
                               .filter_by(book_hash=book.book_hash).first())
        if (duplicate is not None):
            book.unsent = duplicate.unsent

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


def convert_book(book):
    """
    Attempt to convert any books of type in `CONVERTIBLE_MIMETYPES` to .mobi,
    in the same folder as the given temporary path.
    """
    tmp_path = book.get_tmp_pathname()
    mobi_tmp_path = convert_to_mobi_path(tmp_path)
    if mobi_tmp_path is None:
        return None

    log.info(u"Converting book for user id {0}".format(book.user_id))
    try:
        subprocess.check_output(['ebook-convert', tmp_path, mobi_tmp_path],
                                timeout=CONVERSION_TIMEOUT)
    except subprocess.CalledProcessError as e:
        return e.output
    except subprocess.TimeoutExpired as e:
        return "Timed out converting book"
    except Exception as e:
        return e.message


def download_book(client, book):
    """
    Download the given book from the Dropbox client to a temporary path. Make
    all the directories in the given book path at the temporary root folder if
    they don't already exist.

    Set the book's hash of the downloaded file.
    """
    # Make all the necessary nested directories in the temporary directory.
    tmp_path = book.get_tmp_pathname()
    try:
        book_dir = os.path.dirname(tmp_path)
        if not os.path.exists(book_dir):
            os.makedirs(book_dir)
    except OSError:
        log.error(u"Error creating directories for book {0}".format(book.pathname),
                  exc_info=True)

    try:
        md5 = hashlib.md5()
        with open(tmp_path, 'w') as tmp_book:
            with client.get_file(book.pathname) as book_file:
                data = book_file.read()
                tmp_book.write(data)
                md5.update(data)

        book.book_hash = md5.hexdigest()
    except:
        log.error(u"Failed to download book {book_path} for user id "
                  "{user_id}".format(book_path=book.pathname,
                                     user_id=book.user_id), exc_info=True)
        return None


def email_attachments(email_from, email_to, attachments, user_id):
    """
    Given a 'from' email address and a list of 'to' email addresses, try to
    email as many of the attachments in the given list as possible. For each
    attachment, add the book to the user associated with the given ID and mark
    whether it was successfully emailed or not.
    """
    attachment_paths = get_attachment_paths(attachments)
    log.debug(u"Sending email to " + ' '.join(email_to) + " " + ' '.join(attachment_paths))

    try:
        # First try to batch email.
        _email_attachments(email_from, email_to, attachment_paths)
        for book in attachments:
            book.mark_unsent(False)
    except:
        log.error(u"Failed to send books for user id {0}".format(user_id),
                  exc_info=True)

        # If fail to batch email, try sending individually instead.
        for book in attachments:
            try:
                _email_attachments(email_from, email_to, get_attachment_paths([book]))
                book.mark_unsent(False)
            except:
                log.error(u"Failed to resend book for user id {0}".format(user_id),
                          exc_info=True)
                book.mark_unsent(True)


def _email_attachments(email_from, email_to, attachment_paths):
    status, message = emailer.send_mail(email_from, email_to,
                                        attachment_paths)
    if status != 200:
        raise KindleboxException(message)


def convert_to_mobi_path(path):
    if mimetypes.guess_type(path)[0] in CONVERTIBLE_MIMETYPES:
        stripped_path = os.path.splitext(path)[0]
        return u'{path}.mobi'.format(path=stripped_path)


def get_attachment_paths(books):
    attachment_paths = []
    for book in books:
        tmp_path = book.get_tmp_pathname()

        # If this book got converted, get the .mobi path instead.
        mobi_tmp_path = convert_to_mobi_path(tmp_path)
        if mobi_tmp_path is not None:
            tmp_path = mobi_tmp_path

        attachment_paths.append(tmp_path)

    return attachment_paths


def canonicalize(pathname):
    return pathname.lower()


def mimetypes_filter(path):
    return mimetypes.guess_type(path)[0] in BOOK_MIMETYPES


def _acquire_lock(method_name, dropbox_id):
    # Lock per user.
    lock_id = '{0}-lock-{1}'.format(method_name, dropbox_id)
    lock = redis.lock(lock_id, timeout=LOCK_EXPIRE)

    # If non-blocking and unable to acquire lock, discard the task and hope
    # that another worker finishes it.
    if not lock.acquire(blocking=False):
        log.debug(u"Couldn't acquire lock {0}.".format(lock_id))
        return None

    log.debug(u"Lock {0} acquired.".format(lock_id))
    return lock


def acquire_kindlebox_lock(dropbox_id):
    """
    """
    return _acquire_lock(kindlebox.__name__,
                         dropbox_id)


def acquire_send_books_lock(user_id):
    """
    """
    return _acquire_lock(send_books.__name__,
                         user_id)


class KindleboxException(Exception):
    pass
