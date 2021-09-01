import sys
from collections import namedtuple
from contextlib import contextmanager
from io import StringIO


class Missing(object):
    def __bool__(self):
        return False

    def __str__(self):
        return "-"

    __repr__ = __str__


MISSING = Missing()


@contextmanager
def get_stdout():
    backup = sys.stdout
    sys.stdout = StringIO()
    try:
        yield lambda: string
        string = sys.stdout.getvalue()
    finally:
        sys.stdout.close()
        sys.stdout = backup
