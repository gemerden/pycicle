import sys
from collections import namedtuple
from functools import wraps
from io import StringIO
from contextlib import contextmanager


class Missing(object):
    def __bool__(self):
        return False

    def __str__(self):
        return "MISSING"

    __repr__ = __str__


MISSING = Missing()
@contextmanager
def get_stdout():
    backup = sys.stdout
    sys.stdout = StringIO()
    yield lambda: string
    string = sys.stdout.getvalue()
    sys.stdout.close()
    sys.stdout = backup


Codec = namedtuple('Codec', ['encode', 'decode'])

