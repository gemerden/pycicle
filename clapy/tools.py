import sys
from collections import namedtuple
from io import StringIO
from contextlib import contextmanager


@contextmanager
def get_stdout():
    backup = sys.stdout
    sys.stdout = StringIO()
    yield lambda: string
    string = sys.stdout.getvalue()
    sys.stdout.close()
    sys.stdout = backup


Codec = namedtuple('Codec', ['encode', 'decode'])

if __name__ == '__main__':
    pass


class Missing(object):
    def __bool__(self):
        return False

    def __str__(self):
        return "MISSING"

    __repr__ = __str__


MISSING = Missing()