import os

from app import app


def get_user_directory(user_id):
    return os.path.join(app.config.get('BASE_DIR', ''),
                        str(user_id))


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
        log.debug("Failed to clear tmp directory", exc_info=True)


