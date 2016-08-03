import logging
import os

from app import app


log = logging.getLogger()

def get_user_directory(user_id, *tags):
    return os.path.join(app.config.get('BASE_DIR', ''),
                        unicode(user_id),
                        *tags)


def clear_directory(directory):
    """
    Remove all possible directories and files from a given directory.
    """
    try:
        for path in os.listdir(directory):
            subdirectory = os.path.join(directory, path)
            if os.path.isdir(subdirectory):
                clear_directory(subdirectory)
            else:
                os.unlink(subdirectory)
        os.rmdir(directory)
    except OSError:
        if os.path.exists(directory):
            log.info("Failed to clear tmp directory", exc_info=True)


def clear_empty_directory(directory):
    try:
        if len(os.listdir(directory)) == 0:
            os.rmdir(directory)
    except OSError:
        if os.path.exists(directory):
            log.info("Failed to clear tmp directory", exc_info=True)


def clear_calibre_files():
    try:
        for path in os.listdir('/tmp'):
            if path.startswith('calibre'):
                subdirectory = os.path.join('/tmp', path)
                clear_directory(subdirectory)
    except OSError:
        log.info("Failed to clear calibre files", exc_info=True)
