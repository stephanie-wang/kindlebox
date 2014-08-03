import binascii
import os


def get_random_string(size=32):
    return binascii.b2a_hex(os.urandom(size / 2))
