import emailer


def process_user(client, cursor, email, emailer):
    delta = client.delta(cursor)
    files = get_books_from_delta(delta) 
    emailer.send_mail(emailer, email, 'convert', '', files)

def get_client(access_token):
    '''
    Get the Dropbox client from cache or create it.
    '''
    pass

def get_books_from_delta(client, cursor):
    # TODO: implement
    pass
    ## Get all entries that were added and are not a directory.
    #booksToSave = filter(lambda entry: (not entry[1]['is_dir']) if entry[1] !=
    #        None else False, delta['entries'])
    #books_saved = [ book[0] for book in booksToSave ]
    ## Also filter by current books in case last save failed
    #cur_books = db.get_books_from_db(kindle_name)
    #books_saved = filter(lambda book: book not in cur_books, books_saved)
    ## TODO: check books for file renames
    ## TODO: check books for correct file extensions
    #book_ids = db.save_books(kindle_name, books_saved)
    #hashes = download_and_email_books(client, kindle_name, books_saved)
    ## TODO: what happens if emailing fails midway through hashes? need some sort
    ## of saved flag in database. should probably save books one at a time in case
    ## of failure
    #db.save_book_hashes(book_ids, hashes)
    #
    #booksToDelete = filter(lambda entry: entry[1] == None and len(entry[0].split('.')) > 1,
    #    delta['entries'])
    #books_removed = [ book[0] for book in booksToDelete ]
    #db.delete_books(kindle_name, books_removed)

    #db.write('UPDATE users SET delta_cursor = ? WHERE kindle_name = ?', [delta['cursor'], kindle_name])
    #return books_saved

def download_and_email_books(client, kindle_name, books):
    hashes = []
    md5 = hashlib.md5()

    email_from = db.get_emailer(kindle_name)
    email_to = kindle_name + '@kindle.com'

    for book in books:
        tmp_path = constants.LOCAL_FOLDER + book.split('/')[-1]
        with open(tmp_path, 'w') as tmp_book:
            with client.get_file(book) as book:
                data = book.read()
                tmp_book.write(data)
                md5.update(data)

        book_hash = md5.digest().decode("iso-8859-1")
        print "book hash is " + book_hash
        hashes.append(book_hash)

        # TODO: Error catching on the email?
        emailer.send_mail(email_from, email_to, 'convert','sending a book',
                [tmp_book])

        os.remove(tmp_path)
    return hashes

def main():
    pass

if __name__ == '__main__':
    main()
